"""POST/GET/DELETE /geofences."""

import json
import os
import sys
import uuid
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from boto3.dynamodb.conditions import Attr

from shared.dynamo import get_table
from shared.models import geofence_pk


def lambda_handler(event, context):
    method = event.get('httpMethod', 'GET')

    if method == 'POST':
        return _create_geofence(event)
    if method == 'DELETE':
        return _delete_geofence(event)
    return _list_geofences(event)


def _create_geofence(event):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})

    label = body.get('label')
    polygon = body.get('polygon')

    if not label:
        return _response(400, {'error': 'Missing required field: label'})
    if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
        return _response(400, {'error': 'polygon must be a list of at least 3 coordinate pairs'})

    geofence_id = str(uuid.uuid4())
    pk = geofence_pk(geofence_id)

    table = get_table()
    table.put_item(Item={
        'PK': pk,
        'SK': pk,
        'geofenceId': geofence_id,
        'label': label,
        'polygon': json.dumps(polygon),
        'active': True,
    })

    return _response(201, {
        'geofenceId': geofence_id,
        'label': label,
        'polygon': polygon,
        'active': True,
    })


def _list_geofences(event):
    table = get_table()
    resp = table.scan(
        FilterExpression=Attr('PK').begins_with('GEOFENCE#') & Attr('SK').begins_with('GEOFENCE#'),
    )
    items = resp.get('Items', [])

    geofences = []
    for item in items:
        polygon_raw = item.get('polygon', '[]')
        try:
            polygon = json.loads(polygon_raw) if isinstance(polygon_raw, str) else polygon_raw
        except (json.JSONDecodeError, TypeError):
            polygon = []

        geofences.append({
            'geofenceId': item.get('geofenceId'),
            'label': item.get('label'),
            'polygon': polygon,
            'active': item.get('active', True),
        })

    return _response(200, {'geofences': geofences, 'count': len(geofences)})


def _delete_geofence(event):
    geofence_id = (event.get('pathParameters') or {}).get('id')
    if not geofence_id:
        return _response(400, {'error': 'Missing geofence id'})

    pk = geofence_pk(geofence_id)
    table = get_table()
    table.delete_item(Key={'PK': pk, 'SK': pk})

    return _response(200, {'deleted': geofence_id})


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body),
    }
