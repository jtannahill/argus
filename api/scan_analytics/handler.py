"""POST /scan-analytics — records a scan event and atomically increments daily heat counters."""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import scan_pk, scan_sk, heat_pk


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON body'})

    # Validate required fields
    required = ['userId', 'bbl', 'latitude', 'longitude', 'heading',
                'matchMethod', 'confidence', 'durationMs']
    missing = [f for f in required if f not in body]
    if missing:
        return _response(400, {'error': f'Missing required fields: {missing}'})

    user_id = body['userId']
    bbl = body['bbl']
    now = datetime.now(timezone.utc)
    timestamp = now.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'
    date_str = now.strftime('%Y-%m-%d')
    scan_id = str(uuid.uuid4())

    table = get_table()

    # Write individual scan event record
    table.put_item(Item={
        'PK': scan_pk(user_id, timestamp),
        'SK': scan_sk(),
        'scanId': scan_id,
        'userId': user_id,
        'bbl': bbl,
        'latitude': Decimal(str(body['latitude'])),
        'longitude': Decimal(str(body['longitude'])),
        'heading': Decimal(str(body['heading'])),
        'matchMethod': body['matchMethod'],
        'confidence': Decimal(str(body['confidence'])),
        'durationMs': Decimal(str(body['durationMs'])),
        'tabsViewed': body.get('tabsViewed', []),
        'timestamp': timestamp,
        'date': date_str,
    })

    # Atomically increment daily heat counter for the building
    # PK: HEAT#{YYYY-MM-DD}  SK: BLDG#{bbl}
    # ADD scanCount by 1 and add userId to uniqueUsers set
    table.update_item(
        Key={
            'PK': heat_pk(date_str),
            'SK': f'BLDG#{bbl}',
        },
        UpdateExpression='ADD scanCount :one, uniqueUsers :users',
        ExpressionAttributeValues={
            ':one': Decimal('1'),
            ':users': {user_id},
        },
    )

    return _response(200, {'recorded': True, 'scanId': scan_id})


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body),
    }
