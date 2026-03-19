"""DynamoDB entity key patterns for Argus single-table design."""

from datetime import datetime, timezone
import hashlib


def sighting_pk(plate: str) -> str:
    return f"PLATE#{plate.upper().replace(' ', '')}"


def sighting_sk(timestamp: str) -> str:
    return f"SIGHTING#{timestamp}"


def enrichment_sk() -> str:
    return "ENRICHMENT#latest"


def geofence_pk(geofence_id: str) -> str:
    return f"GEOFENCE#{geofence_id}"


def connection_pk(connection_id: str) -> str:
    return f"CONNECTION#{connection_id}"


def alert_pk(alert_id: str) -> str:
    return f"ALERT#{alert_id}"


def geohash6(lat: float, lon: float) -> str:
    """Compute a 6-character geohash (~1.2km precision)."""
    base32 = '0123456789bcdefghjkmnpqrstuvwxyz'
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    bits = [16, 8, 4, 2, 1]
    hash_str = []
    is_lon = True
    bit = 0
    ch = 0

    while len(hash_str) < 6:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon > mid:
                ch |= bits[bit]
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat > mid:
                ch |= bits[bit]
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        is_lon = not is_lon
        if bit < 4:
            bit += 1
        else:
            hash_str.append(base32[ch])
            bit = 0
            ch = 0

    return ''.join(hash_str)


def gsi1_pk(lat: float, lon: float) -> str:
    return f"GPS_HASH#{geohash6(lat, lon)}"


def gsi2_pk(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    return f"DATE#{dt.strftime('%Y-%m-%d')}"
