"""DynamoDB helpers for Argus."""

import os
import boto3
from botocore.config import Config

_table = None


def get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource(
            'dynamodb',
            config=Config(retries={'max_attempts': 3, 'mode': 'adaptive'}),
        )
        _table = dynamodb.Table(os.environ['TABLE_NAME'])
    return _table
