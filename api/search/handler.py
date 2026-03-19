"""GET /search — search buildings by location."""

import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import geohash6, geo_pk
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    """Search buildings near a location."""
    params = event.get('queryStringParameters') or {}
    lat = params.get('lat')
    lon = params.get('lon')
    radius = params.get('radiusM', '100')

    if not lat or not lon:
        return _response(400, {'error': 'lat and lon required'})

    try:
        lat = float(lat)
        lon = float(lon)
        radius = float(radius)
    except ValueError:
        return _response(400, {'error': 'lat, lon, radiusM must be numeric'})

    table = get_table()
    gh = geohash6(lat, lon)

    # Query nearby buildings by geohash
    try:
        resp = table.query(
            KeyConditionExpression=Key('PK').eq(geo_pk(lat, lon)),
            Limit=20,
        )
        buildings = []
        for item in resp.get('Items', []):
            buildings.append({
                'bbl': item.get('bbl', ''),
                'address': item.get('address', ''),
                'latitude': float(item.get('latitude', 0) or 0),
                'longitude': float(item.get('longitude', 0) or 0),
            })
        return _response(200, {'buildings': buildings})
    except Exception as e:
        return _response(502, {'error': str(e)})


def _response(code, body):
    return {
        'statusCode': code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body, default=lambda o: float(o) if isinstance(o, Decimal) else None),
    }
