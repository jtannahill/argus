"""Push enrichment results + alerts to all connected WebSocket clients."""

import json
import os
import sys

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.dynamo import get_table
from boto3.dynamodb.conditions import Attr

ENDPOINT = os.environ.get('WEBSOCKET_ENDPOINT', '')


def lambda_handler(event, context):
    table = get_table()
    connections = table.scan(
        FilterExpression=Attr('PK').begins_with('CONNECTION#') & Attr('SK').eq('META'),
    )['Items']

    api = boto3.client('apigatewaymanagementapi', endpoint_url=ENDPOINT)
    message = json.dumps(event).encode()

    for conn in connections:
        connection_id = conn['PK'].replace('CONNECTION#', '')
        try:
            api.post_to_connection(ConnectionId=connection_id, Data=message)
        except api.exceptions.GoneException:
            table.delete_item(Key={'PK': conn['PK'], 'SK': 'META'})

    return {'statusCode': 200}
