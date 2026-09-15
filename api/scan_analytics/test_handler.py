"""Tests for scan_analytics handler Lambda."""

import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import scan_analytics.handler as handler  # noqa: E402

VALID_EVENT = {
    'body': json.dumps({
        'userId': 'user-123',
        'bbl': '1000477501',
        'latitude': 40.7128,
        'longitude': -74.0060,
        'heading': 180.0,
        'matchMethod': 'CLIP',
        'confidence': 0.92,
        'durationMs': 1500,
        'tabsViewed': ['overview', 'violations'],
    })
}


@patch('scan_analytics.handler.get_table')
def test_put_item_called_for_scan_event(mock_get_table):
    """Verifies that a SCAN record is written to DynamoDB."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler(VALID_EVENT, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['recorded'] is True
    assert 'scanId' in body

    assert table_mock.put_item.call_count == 1
    put_call_kwargs = table_mock.put_item.call_args[1]
    item = put_call_kwargs['Item']

    assert item['SK'] == 'SCAN'
    assert item['userId'] == 'user-123'
    assert item['bbl'] == '1000477501'
    assert item['matchMethod'] == 'CLIP'
    assert item['tabsViewed'] == ['overview', 'violations']
    # PK must follow SCAN#{userId}#{timestamp} pattern
    assert item['PK'].startswith('SCAN#user-123#')


@patch('scan_analytics.handler.get_table')
def test_update_item_called_with_atomic_increment(mock_get_table):
    """Verifies that the heat counter is atomically incremented via update_item ADD."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    handler.lambda_handler(VALID_EVENT, None)

    assert table_mock.update_item.call_count == 1
    update_kwargs = table_mock.update_item.call_args[1]

    key = update_kwargs['Key']
    assert key['PK'].startswith('HEAT#')
    assert key['SK'] == 'BLDG#1000477501'

    assert 'ADD' in update_kwargs['UpdateExpression']
    assert 'scanCount' in update_kwargs['UpdateExpression']
    assert 'uniqueUsers' in update_kwargs['UpdateExpression']

    attr_vals = update_kwargs['ExpressionAttributeValues']
    assert attr_vals[':one'] == Decimal('1')
    assert 'user-123' in attr_vals[':users']


@patch('scan_analytics.handler.get_table')
def test_missing_required_fields_returns_400(mock_get_table):
    """Verifies 400 is returned when required fields are absent."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    event = {'body': json.dumps({'userId': 'user-123'})}
    result = handler.lambda_handler(event, None)

    assert result['statusCode'] == 400
    body = json.loads(result['body'])
    assert 'error' in body
    table_mock.put_item.assert_not_called()
    table_mock.update_item.assert_not_called()


@patch('scan_analytics.handler.get_table')
def test_invalid_json_body_returns_400(mock_get_table):
    """Verifies 400 is returned for malformed JSON."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    event = {'body': 'not-json'}
    result = handler.lambda_handler(event, None)

    assert result['statusCode'] == 400


@patch('scan_analytics.handler.get_table')
def test_empty_body_returns_400(mock_get_table):
    """Verifies 400 is returned when body is absent."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler({}, None)
    assert result['statusCode'] == 400


@patch('scan_analytics.handler.get_table')
def test_scan_id_is_unique_per_call(mock_get_table):
    """Verifies each invocation produces a distinct scanId."""
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    r1 = json.loads(handler.lambda_handler(VALID_EVENT, None)['body'])
    r2 = json.loads(handler.lambda_handler(VALID_EVENT, None)['body'])

    assert r1['scanId'] != r2['scanId']
