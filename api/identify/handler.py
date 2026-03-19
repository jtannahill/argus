"""POST /identify — resolve GPS + heading to building candidates."""

import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import building_pk, profile_sk, story_sk
from shared.nyc_data import NYCDataProvider


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON body'})

    lat = body.get('latitude')
    lon = body.get('longitude')
    heading = body.get('heading')

    if lat is None or lon is None or heading is None:
        return _response(400, {'error': 'Missing required fields: latitude, longitude, heading'})

    try:
        lat = float(lat)
        lon = float(lon)
        heading = float(heading)
    except (TypeError, ValueError):
        return _response(400, {'error': 'latitude, longitude, and heading must be numeric'})

    provider = NYCDataProvider()
    try:
        candidates = provider.resolve_location(lat, lon, heading)
    except Exception as exc:
        return _response(502, {'error': f'NYC data provider error: {str(exc)}'})

    table = get_table()
    enriched = []
    for candidate in candidates:
        raw_bbl = candidate.get('bbl', '').strip()
        # PLUTO returns BBL as decimal string like "1004830001.00000000"
        bbl = raw_bbl.split('.')[0] if '.' in raw_bbl else raw_bbl

        # Normalize to match iOS BuildingCandidate model
        try:
            blat = float(candidate.get('latitude', 0))
            blon = float(candidate.get('longitude', 0))
            dist = provider._haversine(lat, lon, blat, blon)
        except (TypeError, ValueError):
            dist = 0

        entry = {
            'id': bbl,
            'bbl': bbl,
            'address': candidate.get('address', ''),
            'distance': round(dist, 1),
            'score': 0.0,
            'profile': {
                'yearBuilt': candidate.get('yearbuilt', ''),
                'stories': candidate.get('numfloors', ''),
                'units': candidate.get('unitstotal', ''),
                'residentialUnits': candidate.get('unitsres', ''),
                'lotArea': candidate.get('lotarea', ''),
                'buildingClass': candidate.get('bldgclass', ''),
                'zoneDist': candidate.get('zonedist1', ''),
                'far': candidate.get('builtfar', ''),
                'maxFar': candidate.get('residfar', ''),
                'landmark': candidate.get('landmark', ''),
                'landmarkName': candidate.get('landmkname', ''),
                'architect': None,
                'architecturalStyle': None,
                'assessedLand': candidate.get('assessland', ''),
                'assessedTotal': candidate.get('assesstot', ''),
                'taxClass': candidate.get('taxclass', ''),
                'latitude': blat,
                'longitude': blon,
            },
        }

        # Check DynamoDB cache for story
        if bbl:
            pk = building_pk(bbl)
            try:
                story_resp = table.get_item(Key={'PK': pk, 'SK': story_sk()})
                story_item = story_resp.get('Item')
                if story_item:
                    entry['story'] = {
                        'headline': story_item.get('headline', ''),
                        'narrative': story_item.get('narrative', ''),
                        'funFacts': story_item.get('funFacts', []),
                        'generatedAt': story_item.get('generatedAt', ''),
                    }
            except Exception:
                pass

        enriched.append(entry)

    return _response(200, {'candidates': enriched})


def _convert_decimals(obj):
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body),
    }
