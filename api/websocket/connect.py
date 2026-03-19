"""WebSocket $connect handler — stores connection ID in DynamoDB."""

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.dynamo import get_table
from shared.models import connection_pk


def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    table = get_table()
    table.put_item(Item={
        'PK': connection_pk(connection_id),
        'SK': 'META',
        'ttl': int(time.time()) + 86400,  # 24h expiry
    })
    return {'statusCode': 200}
