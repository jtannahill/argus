"""Tests for alerts Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import alerts.handler as handler  # noqa: E402


@patch('alerts.handler.get_table')
def test_list_alerts(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    table_mock.scan.return_value = {
        'Items': [
            {
                'PK': 'ALERT#alert-001',
                'SK': 'ALERT#alert-001',
                'alertId': 'alert-001',
                'timestamp': '2026-03-19T12:00:00Z',
                'type': 'geofence_entry',
                'plate': 'ABC1234',
                'message': 'Plate ABC1234 entered Zone A',
                'geofenceId': 'geo-001',
            }
        ]
    }

    result = handler.lambda_handler({'queryStringParameters': None}, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['count'] == 1
    alert = body['alerts'][0]
    assert alert['alertId'] == 'alert-001'
    assert alert['plate'] == 'ABC1234'
    assert alert['type'] == 'geofence_entry'
    assert alert['geofenceId'] == 'geo-001'
