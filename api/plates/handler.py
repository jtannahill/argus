"""GET /plates/{plate} and GET /plates/{plate}/sightings."""

import json
import os
import sys
import base64
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from boto3.dynamodb.conditions import Key

from shared.dynamo import get_table
from shared.models import sighting_pk, enrichment_sk, sighting_sk


def lambda_handler(event, context):
    resource = event.get('resource', '')
    if 'sightings' in resource:
        return _get_sightings(event)
    return _get_plate_detail(event)


def _get_plate_detail(event):
    plate = event.get('pathParameters', {}).get('plate', '')
    if not plate:
        return _response(400, {'error': 'Missing plate parameter'})

    table = get_table()
    pk = sighting_pk(plate)

    # Fetch enrichment record
    enrichment_resp = table.get_item(Key={'PK': pk, 'SK': enrichment_sk()})
    enrichment = enrichment_resp.get('Item')

    # Fetch last 5 sightings
    sightings_resp = table.query(
        KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with('SIGHTING#'),
        ScanIndexForward=False,
        Limit=5,
    )
    sightings = sightings_resp.get('Items', [])

    return _response(200, {
        'plate': plate.upper().replace(' ', ''),
        'enrichment': _convert_decimals(enrichment) if enrichment else None,
        'recentSightings': _convert_decimals(sightings),
    })


def _get_sightings(event):
    plate = event.get('pathParameters', {}).get('plate', '')
    if not plate:
        return _response(400, {'error': 'Missing plate parameter'})

    params = event.get('queryStringParameters') or {}
    limit = int(params.get('limit', 25))
    next_token = params.get('nextToken')

    table = get_table()
    pk = sighting_pk(plate)

    query_kwargs = {
        'KeyConditionExpression': Key('PK').eq(pk) & Key('SK').begins_with('SIGHTING#'),
        'ScanIndexForward': False,
        'Limit': limit,
    }

    if next_token:
        try:
            exclusive_start = json.loads(base64.b64decode(next_token).decode('utf-8'))
            query_kwargs['ExclusiveStartKey'] = exclusive_start
        except Exception:
            return _response(400, {'error': 'Invalid nextToken'})

    resp = table.query(**query_kwargs)
    items = resp.get('Items', [])
    last_key = resp.get('LastEvaluatedKey')

    result = {
        'plate': plate.upper().replace(' ', ''),
        'sightings': _convert_decimals(items),
        'count': len(items),
    }
    if last_key:
        result['nextToken'] = base64.b64encode(
            json.dumps(last_key).encode('utf-8')
        ).decode('utf-8')

    return _response(200, result)


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
