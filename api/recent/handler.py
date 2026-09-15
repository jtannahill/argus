"""Recent scans endpoint — returns latest building scans for the dashboard heat map."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import heat_pk, building_pk
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    """Return recent building scans from today and yesterday via GSI2."""
    table = get_table()
    params = event.get('queryStringParameters') or {}
    limit = min(int(params.get('limit', '200')), 500)

    buildings = []
    now = datetime.now(timezone.utc)

    # Query last 7 days of HEAT# counters
    for days_ago in range(7):
        date = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        try:
            resp = table.query(
                KeyConditionExpression=Key('PK').eq(heat_pk(date)),
                Limit=limit,
            )
            for item in resp.get('Items', []):
                bbl = item.get('bbl', '')
                if not bbl:
                    continue

                # Try to get cached profile for lat/lon
                try:
                    from shared.models import profile_sk
                    profile_resp = table.get_item(
                        Key={'PK': building_pk(bbl), 'SK': profile_sk()}
                    )
                    profile = profile_resp.get('Item', {})
                except Exception:
                    profile = {}

                buildings.append({
                    'bbl': bbl,
                    'address': profile.get('address', ''),
                    'latitude': float(profile.get('latitude', 0) or 0),
                    'longitude': float(profile.get('longitude', 0) or 0),
                    'scanCount': int(item.get('scanCount', 0)),
                    'date': date,
                })
        except Exception:
            continue

        if len(buildings) >= limit:
            break

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({'buildings': buildings[:limit]}, default=_decimal_default),
    }


def _decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError
