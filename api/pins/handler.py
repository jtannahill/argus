"""Pins endpoint — save/list/delete pinned buildings per user."""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from dynamo import get_table  # noqa: E402

CORS_HEADERS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type,Authorization',
    'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS',
}


def _user_id(event):
    try:
        return event['requestContext']['authorizer']['claims']['sub']
    except (KeyError, TypeError):
        return None


def _ok(body):
    return {'statusCode': 200, 'headers': CORS_HEADERS, 'body': json.dumps(body)}


def _err(status, message):
    return {'statusCode': status, 'headers': CORS_HEADERS, 'body': json.dumps({'error': message})}


def lambda_handler(event, context):
    method = event.get('httpMethod', '')

    if method == 'OPTIONS':
        return {'statusCode': 204, 'headers': CORS_HEADERS, 'body': ''}

    user_id = _user_id(event)
    if not user_id:
        return _err(401, 'Unauthorized')

    if method == 'POST':
        return pin_building(event, user_id)
    elif method == 'GET':
        return list_pins(user_id)
    elif method == 'DELETE':
        return unpin_building(event, user_id)
    else:
        return _err(405, 'Method not allowed')


def pin_building(event, user_id):
    try:
        body = json.loads(event.get('body') or '{}')
    except json.JSONDecodeError:
        return _err(400, 'Invalid JSON body')

    bbl = body.get('bbl', '').strip()
    address = body.get('address', '').strip()
    if not bbl:
        return _err(400, 'bbl is required')

    table = get_table()
    item = {
        'PK': f'USER#{user_id}',
        'SK': f'PIN#{bbl}',
        'bbl': bbl,
        'address': address,
        'pinnedAt': datetime.now(timezone.utc).isoformat(),
    }

    profile = body.get('profile')
    if isinstance(profile, dict):
        # Store a useful subset of the profile
        subset_keys = [
            'latitude', 'longitude', 'yearBuilt', 'stories', 'unitsRes',
            'landmark', 'landmarkName', 'bldgClass', 'ownername',
        ]
        item['profile'] = {k: profile[k] for k in subset_keys if k in profile}

    table.put_item(Item=item)
    return _ok({'pinned': True, 'bbl': bbl})


def list_pins(user_id):
    from boto3.dynamodb.conditions import Key

    table = get_table()
    result = table.query(
        KeyConditionExpression=Key('PK').eq(f'USER#{user_id}') & Key('SK').begins_with('PIN#'),
    )
    items = result.get('Items', [])

    buildings = []
    for item in items:
        candidate = {
            'bbl': item.get('bbl', ''),
            'address': item.get('address', ''),
            'pinnedAt': item.get('pinnedAt', ''),
        }
        if 'profile' in item:
            candidate['profile'] = item['profile']
        buildings.append(candidate)

    # Sort newest first
    buildings.sort(key=lambda x: x.get('pinnedAt', ''), reverse=True)
    return _ok({'buildings': buildings})


def unpin_building(event, user_id):
    path_params = event.get('pathParameters') or {}
    bbl = path_params.get('bbl', '').strip()
    if not bbl:
        return _err(400, 'bbl path parameter is required')

    table = get_table()
    table.delete_item(Key={'PK': f'USER#{user_id}', 'SK': f'PIN#{bbl}'})
    return _ok({'pinned': False, 'bbl': bbl})
