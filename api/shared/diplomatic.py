"""Diplomatic plate format detection and mission lookup."""

import json
import os
import re

_DATA = None

def _load_data():
    global _DATA
    if _DATA is None:
        data_path = os.path.join(os.path.dirname(__file__), 'diplomatic_data.json')
        with open(data_path) as f:
            _DATA = json.load(f)
    return _DATA


# US: D/C/S/A + 3-digit country code + up to 3-digit sequence
_US_PATTERN = re.compile(r'^([DCSA])(\d{3})(\d{0,3})$')
# Canada: CD (diplomatic) or CC (consular) + digits
_CA_PATTERN = re.compile(r'^(C[CD])(\d{3,5})$')
# Mexico: DMT prefix + digits
_MX_PATTERN = re.compile(r'^(DMT)(\d{3,5})$')

_US_PREFIX_TYPES = {
    'D': 'diplomat',
    'C': 'consul',
    'S': 'staff',
    'A': 'attache',
}


def detect_diplomatic_format(plate: str) -> dict | None:
    """Detect if a plate matches a diplomatic format. Returns info dict or None."""
    plate = plate.upper().replace(' ', '').replace('-', '')

    # US diplomatic
    m = _US_PATTERN.match(plate)
    if m:
        prefix = m.group(1)
        country_code = m.group(2)
        mission = lookup_us_mission(country_code)
        return {
            'isDiplomatic': True,
            'issuingCountry': 'US',
            'prefix': prefix,
            'plateType': _US_PREFIX_TYPES.get(prefix, 'unknown'),
            'countryCode': country_code,
            'mission': mission,
        }

    # Canadian diplomatic
    m = _CA_PATTERN.match(plate)
    if m:
        prefix = m.group(1)
        return {
            'isDiplomatic': True,
            'issuingCountry': 'CA',
            'prefix': prefix,
            'plateType': 'diplomat' if prefix == 'CD' else 'consul',
            'countryCode': None,
            'mission': None,
        }

    # Mexican diplomatic
    m = _MX_PATTERN.match(plate)
    if m:
        return {
            'isDiplomatic': True,
            'issuingCountry': 'MX',
            'prefix': 'DMT',
            'plateType': 'diplomat',
            'countryCode': None,
            'mission': None,
        }

    return None


def lookup_us_mission(country_code: str) -> dict | None:
    """Look up US State Department country code to mission info."""
    data = _load_data()
    missions = data.get('missions', {})
    mission = missions.get(country_code)
    if not mission:
        return None

    # Include consulate locations if available
    consulates = data.get('consulates', {}).get(country_code, [])
    result = {**mission}
    if consulates:
        result['consulates'] = consulates
    return result


def get_diplomatic_geofences(diplomatic_info: dict) -> list:
    """Get auto-geofence locations for a diplomatic plate's own mission/consulates."""
    if not diplomatic_info or not diplomatic_info.get('mission'):
        return []

    mission = diplomatic_info['mission']
    geofences = []

    # Embassy/mission HQ
    if mission.get('latitude') and mission.get('longitude'):
        geofences.append({
            'latitude': mission['latitude'],
            'longitude': mission['longitude'],
            'radiusM': mission.get('geofenceRadiusM', 200),
            'label': f"{mission.get('country', '')} {mission.get('missionType', 'mission')} - {mission.get('city', '')}",
        })

    # Consulates
    for consulate in mission.get('consulates', []):
        if consulate.get('latitude') and consulate.get('longitude'):
            geofences.append({
                'latitude': consulate['latitude'],
                'longitude': consulate['longitude'],
                'radiusM': 200,
                'label': f"{mission.get('country', '')} consulate - {consulate.get('city', '')}",
            })

    return geofences
