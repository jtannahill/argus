"""Recent sightings endpoint — returns latest sightings with GPS data."""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import gsi2_pk
from boto3.dynamodb.conditions import Key


def lambda_handler(event, context):
    """Return recent sightings from today and yesterday via GSI2."""
    table = get_table()
    params = event.get('queryStringParameters') or {}
    limit = min(int(params.get('limit', '100')), 500)

    sightings = []
    now = datetime.now(timezone.utc)

    # Query last 2 days via GSI2 (DATE#YYYY-MM-DD)
    for days_ago in range(2):
        date = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        resp = table.query(
            IndexName='GSI2',
            KeyConditionExpression=Key('GSI2PK').eq(f'DATE#{date}'),
            Limit=limit,
            ScanIndexForward=False,
        )
        for item in resp.get('Items', []):
            if item.get('latitude') and item.get('longitude'):
                sightings.append({
                    'plate': item.get('plate', ''),
                    'latitude': float(item['latitude']),
                    'longitude': float(item['longitude']),
                    'timestamp': item.get('timestamp', ''),
                    'confidence': float(item.get('confidence', 0)),
                })

        if len(sightings) >= limit:
            break

    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps({'sightings': sightings[:limit]}),
    }
