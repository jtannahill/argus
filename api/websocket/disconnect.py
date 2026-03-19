"""WebSocket $disconnect handler — removes connection ID."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.dynamo import get_table
from shared.models import connection_pk


def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    table = get_table()
    table.delete_item(Key={
        'PK': connection_pk(connection_id),
        'SK': 'META',
    })
    return {'statusCode': 200}
