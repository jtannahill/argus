"""EventBridge scheduled Lambda (2am daily) — aggregates yesterday's heat counters."""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from boto3.dynamodb.conditions import Key

from shared.dynamo import get_table
from shared.models import heat_pk, analytics_pk

TRENDING_THRESHOLD = 5


def lambda_handler(event, context):
    now = datetime.now(timezone.utc)
    yesterday = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    table = get_table()

    # Query all HEAT#{date} records for yesterday
    resp = table.query(
        KeyConditionExpression=Key('PK').eq(heat_pk(yesterday)),
    )
    items = resp.get('Items', [])

    # Paginate if necessary
    while 'LastEvaluatedKey' in resp:
        resp = table.query(
            KeyConditionExpression=Key('PK').eq(heat_pk(yesterday)),
            ExclusiveStartKey=resp['LastEvaluatedKey'],
        )
        items.extend(resp.get('Items', []))

    # Roll up totals
    total_scans = 0
    buildings_scanned = 0
    trending_buildings = []

    for item in items:
        scan_count = int(item.get('scanCount', 0))
        bbl = item.get('SK', '').replace('BLDG#', '')
        total_scans += scan_count
        buildings_scanned += 1
        if scan_count >= TRENDING_THRESHOLD:
            trending_buildings.append({
                'bbl': bbl,
                'scanCount': scan_count,
                'uniqueUsers': len(item.get('uniqueUsers', set())),
            })

    trending_count = len(trending_buildings)

    # Write daily analytics summary
    # PK: ANALYTICS#daily  SK: {date}
    table.put_item(Item={
        'PK': analytics_pk('daily'),
        'SK': yesterday,
        'date': yesterday,
        'totalScans': Decimal(str(total_scans)),
        'buildingsScanned': Decimal(str(buildings_scanned)),
        'trendingCount': Decimal(str(trending_count)),
        'trendingBuildings': trending_buildings,
        'generatedAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
    })

    return {
        'date': yesterday,
        'totalScans': total_scans,
        'buildingsScanned': buildings_scanned,
        'trendingCount': trending_count,
    }
