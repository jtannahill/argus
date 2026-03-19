"""GET /alerts — paginated list of alert records."""

import json
import os
import sys
import base64
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from boto3.dynamodb.conditions import Attr

from shared.dynamo import get_table


def lambda_handler(event, context):
    params = event.get('queryStringParameters') or {}
    limit = int(params.get('limit', 50))
    next_token = params.get('nextToken')

    table = get_table()

    scan_kwargs = {
        'FilterExpression': Attr('PK').begins_with('ALERT#'),
        'Limit': limit,
    }

    if next_token:
        try:
            exclusive_start = json.loads(base64.b64decode(next_token).decode('utf-8'))
            scan_kwargs['ExclusiveStartKey'] = exclusive_start
        except Exception:
            return _response(400, {'error': 'Invalid nextToken'})

    resp = table.scan(**scan_kwargs)
    items = resp.get('Items', [])
    last_key = resp.get('LastEvaluatedKey')

    alerts = []
    for item in items:
        alert_id = item.get('alertId') or item.get('PK', '').replace('ALERT#', '')
        alerts.append({
            'alertId': alert_id,
            'timestamp': item.get('timestamp'),
            'type': item.get('type'),
            'plate': item.get('plate'),
            'message': item.get('message'),
            'geofenceId': item.get('geofenceId'),
        })

    result = {
        'alerts': _convert_decimals(alerts),
        'count': len(alerts),
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
