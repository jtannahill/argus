"""Tests for presign Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TABLE_NAME'] = 'test-table'
os.environ['CAPTURES_BUCKET'] = 'test-bucket'


def _make_event(body: dict) -> dict:
    return {'body': json.dumps(body)}


def _valid_body() -> dict:
    return {
        'plate': 'ABC1234',
        'confidence': 0.95,
        'latitude': 25.7617,
        'longitude': -80.1918,
        'timestamp': '2026-03-19T12:00:00Z',
        'mode': 'drive',
    }


@patch('handler.s3_client')
@patch('handler.get_table')
def test_presign_returns_urls(mock_table, mock_s3):
    mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/signed'
    mock_table.return_value = MagicMock()

    from handler import lambda_handler

    result = lambda_handler(_make_event(_valid_body()), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert 'sightingId' in body
    assert 'plateUploadUrl' in body
    assert 'vehicleUploadUrl' in body


@patch('handler.s3_client')
@patch('handler.get_table')
def test_presign_normalizes_plate(mock_table, mock_s3):
    mock_s3.generate_presigned_url.return_value = 'https://s3.example.com/signed'
    table_mock = MagicMock()
    mock_table.return_value = table_mock

    from handler import lambda_handler

    body = _valid_body()
    body['plate'] = 'abc 1234'
    lambda_handler(_make_event(body), None)

    put_call = table_mock.put_item.call_args
    assert put_call[1]['Item']['plate'] == 'ABC1234'


def test_presign_rejects_missing_fields():
    from handler import lambda_handler

    result = lambda_handler(_make_event({'plate': 'ABC1234'}), None)
    assert result['statusCode'] == 400
    body = json.loads(result['body'])
    assert 'Missing fields' in body['error']


def test_presign_rejects_invalid_json():
    from handler import lambda_handler

    result = lambda_handler({'body': 'not json'}, None)
    assert result['statusCode'] == 400
