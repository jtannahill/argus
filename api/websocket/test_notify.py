"""Tests for WebSocket notification Lambda."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))
os.environ['TABLE_NAME'] = 'test-table'
os.environ['WEBSOCKET_ENDPOINT'] = 'https://ws.example.com/prod'


@patch('notify.boto3')
@patch('notify.get_table')
def test_notify_sends_to_all_connections(mock_table, mock_boto):
    table_mock = MagicMock()
    table_mock.scan.return_value = {
        'Items': [
            {'PK': 'CONNECTION#conn1', 'SK': 'META'},
            {'PK': 'CONNECTION#conn2', 'SK': 'META'},
        ]
    }
    mock_table.return_value = table_mock

    api_mock = MagicMock()
    mock_boto.client.return_value = api_mock

    from notify import lambda_handler
    lambda_handler({
        'plate': 'ABC1234',
        'sightingId': 'test',
        'alerts': [{'type': 'repeat_visit'}],
    }, None)

    assert api_mock.post_to_connection.call_count == 2
