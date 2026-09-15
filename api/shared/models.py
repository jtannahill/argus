"""DynamoDB key patterns for Argus Building Intelligence.

Single-table design. BBL (Borough/Block/Lot) is the universal building identifier.
"""

def building_pk(bbl: str) -> str:
    return f"BLDG#{bbl.strip()}"

def profile_sk() -> str:
    return "PROFILE"

def story_sk() -> str:
    return "STORY"

def owner_sk(date: str) -> str:
    return f"OWNER#{date}"

def violation_sk(violation_id: str) -> str:
    return f"VIOLATION#{violation_id}"

def permit_sk(permit_id: str) -> str:
    return f"PERMIT#{permit_id}"

def image_sk(timestamp: str) -> str:
    return f"IMAGE#{timestamp}"

def scan_pk(user_id: str, timestamp: str) -> str:
    return f"SCAN#{user_id}#{timestamp}"

def scan_sk() -> str:
    return "SCAN"

def geo_pk(lat: float, lon: float) -> str:
    return f"GEO#{geohash6(lat, lon)}"

def heat_pk(date: str) -> str:
    return f"HEAT#{date}"

def analytics_pk(period: str) -> str:
    return f"ANALYTICS#{period}"

# Base32 geohash encoding
_BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz"

def geohash6(lat: float, lon: float) -> str:
    """Encode lat/lon to 6-character geohash (~600m precision)."""
    lat_range = [-90.0, 90.0]
    lon_range = [-180.0, 180.0]
    is_lon = True
    bit = 0
    ch = 0
    result = []

    while len(result) < 6:
        if is_lon:
            mid = (lon_range[0] + lon_range[1]) / 2
            if lon >= mid:
                ch |= (1 << (4 - bit))
                lon_range[0] = mid
            else:
                lon_range[1] = mid
        else:
            mid = (lat_range[0] + lat_range[1]) / 2
            if lat >= mid:
                ch |= (1 << (4 - bit))
                lat_range[0] = mid
            else:
                lat_range[1] = mid
        is_lon = not is_lon
        bit += 1
        if bit == 5:
            result.append(_BASE32[ch])
            bit = 0
            ch = 0

    return "".join(result)
