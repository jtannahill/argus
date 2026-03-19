"""GET /search — search plates by prefix, date, or lat/lon."""

import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from boto3.dynamodb.conditions import Key, Attr

from shared.dynamo import get_table
from shared.models import gsi2_pk, gsi1_pk, geohash6


def lambda_handler(event, context):
    params = event.get('queryStringParameters') or {}

    query = params.get('q')
    date = params.get('date')
    lat = params.get('lat')
    lon = params.get('lon')

    if not query and not date and not (lat and lon):
        return _response(400, {'error': 'Provide q (plate prefix), date (YYYY-MM-DD), or lat+lon params'})

    table = get_table()

    if query:
        return _search_by_prefix(table, query)
    if date:
        return _search_by_date(table, date)
    return _search_by_location(table, float(lat), float(lon))


def _search_by_prefix(table, query: str):
    prefix = 'PLATE#' + query.upper().replace(' ', '')
    resp = table.scan(
        FilterExpression=Attr('PK').begins_with(prefix) & Attr('SK').begins_with('SIGHTING#'),
    )
    items = resp.get('Items', [])

    # Deduplicate by plate
    seen = set()
    plates = []
    for item in items:
        pk = item.get('PK', '')
        if pk not in seen:
            seen.add(pk)
            plates.append({
                'plate': item.get('plate', pk.replace('PLATE#', '')),
                'lastSeen': item.get('timestamp'),
                'confidence': _to_float(item.get('confidence')),
            })

    return _response(200, {'results': _convert_decimals(plates), 'count': len(plates)})


def _search_by_date(table, date: str):
    gsi2_pk_val = f'DATE#{date}'
    resp = table.query(
        IndexName='GSI2',
        KeyConditionExpression=Key('GSI2PK').eq(gsi2_pk_val),
    )
    items = resp.get('Items', [])
    return _response(200, {'results': _convert_decimals(items), 'count': len(items)})


def _search_by_location(table, lat: float, lon: float):
    gh = geohash6(lat, lon)
    gsi1_pk_val = f'GPS_HASH#{gh}'
    resp = table.query(
        IndexName='GSI1',
        KeyConditionExpression=Key('GSI1PK').eq(gsi1_pk_val),
    )
    items = resp.get('Items', [])
    return _response(200, {'results': _convert_decimals(items), 'count': len(items)})


def _to_float(val):
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return val


def _convert_decimals(obj):
    from decimal import Decimal
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
