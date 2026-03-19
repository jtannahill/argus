"""Plate lookup enrichment — queries NHTSA and FMCSA for vehicle data."""
import json
import os
import sys
import urllib.request
import urllib.parse
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def lambda_handler(event, context):
    plate = event.get('plate', '')

    # Try NHTSA decode (works if plate happens to be a VIN, or for future VIN lookup)
    # For now, use plate as-is — real plate-to-VIN requires commercial API
    nhtsa = _query_nhtsa(plate)
    fmcsa = _query_fmcsa(plate)

    registration = {
        'plate': plate,
        'make': nhtsa.get('Make') if nhtsa else None,
        'model': nhtsa.get('Model') if nhtsa else None,
        'year': nhtsa.get('ModelYear') if nhtsa else None,
        'vehicleType': nhtsa.get('VehicleType') if nhtsa else None,
        'bodyClass': nhtsa.get('BodyClass') if nhtsa else None,
        'fuelType': nhtsa.get('FuelTypePrimary') if nhtsa else None,
        'source': 'nhtsa' if nhtsa else 'none',
    }

    # Merge FMCSA data if found (commercial vehicles)
    if fmcsa:
        registration['carrier'] = fmcsa.get('legalName')
        registration['dotNumber'] = fmcsa.get('dotNumber')
        registration['mcNumber'] = fmcsa.get('mcNumber')
        registration['carrierOperation'] = fmcsa.get('carrierOperation')
        registration['safetyRating'] = fmcsa.get('safetyRating')
        registration['totalDrivers'] = fmcsa.get('totalDrivers')
        registration['totalPowerUnits'] = fmcsa.get('totalPowerUnits')
        registration['source'] = 'nhtsa+fmcsa' if nhtsa else 'fmcsa'

    return {
        'plate': plate,
        'registration': registration,
    }


def _query_nhtsa(vin_or_plate: str) -> dict | None:
    """Query NHTSA VIN Decoder API. Free, no key needed.
    Returns decoded vehicle info if input is a valid VIN (17 chars).
    For plates, returns None (need commercial plate-to-VIN service)."""
    # NHTSA only works with VINs, not plates
    # But we call it anyway in case a VIN is passed through
    if len(vin_or_plate) != 17:
        return None

    try:
        url = f"https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVinValues/{urllib.parse.quote(vin_or_plate)}?format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'Argus/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            results = data.get('Results', [{}])[0]
            # Check if decode was successful (ErrorCode 0 = success)
            if results.get('ErrorCode', '1') == '0' and results.get('Make'):
                return results
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        pass
    return None


def _query_fmcsa(identifier: str) -> dict | None:
    """Query FMCSA SAFER for commercial vehicle/carrier info.
    Searches by name or DOT number. Free API."""
    if not identifier:
        return None

    try:
        # Try as DOT number first
        if identifier.isdigit():
            url = f"https://mobile.fmcsa.dot.gov/qc/services/carriers/{identifier}?webKey=DEMO_KEY"
        else:
            # Search by name/plate — FMCSA doesn't support plate lookup directly
            # but we can search carriers by name for commercial vehicles
            return None

        req = urllib.request.Request(url, headers={'User-Agent': 'Argus/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
            content = data.get('content', {})
            carrier = content.get('carrier', {})
            if carrier.get('legalName'):
                return carrier
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        pass
    return None
