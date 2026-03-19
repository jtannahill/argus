"""Tests for plates Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import plates.handler as handler  # noqa: E402


def _plate_detail_event(plate: str) -> dict:
    return {
        'resource': '/plates/{plate}',
        'pathParameters': {'plate': plate},
        'queryStringParameters': None,
    }


def _sightings_event(plate: str, limit: int = 25, next_token: str = None) -> dict:
    params = {'limit': str(limit)}
    if next_token:
        params['nextToken'] = next_token
    return {
        'resource': '/plates/{plate}/sightings',
        'pathParameters': {'plate': plate},
        'queryStringParameters': params,
    }


@patch('plates.handler.get_table')
def test_plate_detail(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    table_mock.get_item.return_value = {
        'Item': {
            'PK': 'PLATE#ABC1234',
            'SK': 'ENRICHMENT#latest',
            'makeModel': 'Toyota Camry',
            'color': 'Silver',
        }
    }
    table_mock.query.return_value = {
        'Items': [
            {
                'PK': 'PLATE#ABC1234',
                'SK': 'SIGHTING#2026-03-19T12:00:00Z',
                'plate': 'ABC1234',
                'timestamp': '2026-03-19T12:00:00Z',
                'confidence': '0.95',
            }
        ]
    }

    result = handler.lambda_handler(_plate_detail_event('ABC1234'), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['plate'] == 'ABC1234'
    assert body['enrichment'] is not None
    assert body['enrichment']['makeModel'] == 'Toyota Camry'
    assert len(body['recentSightings']) == 1


@patch('plates.handler.get_table')
def test_paginated_sightings(mock_get_table):
    import base64
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    last_key = {'PK': 'PLATE#ABC1234', 'SK': 'SIGHTING#2026-03-19T10:00:00Z'}
    table_mock.query.return_value = {
        'Items': [
            {
                'PK': 'PLATE#ABC1234',
                'SK': 'SIGHTING#2026-03-19T12:00:00Z',
                'plate': 'ABC1234',
                'timestamp': '2026-03-19T12:00:00Z',
            }
        ],
        'LastEvaluatedKey': last_key,
    }

    result = handler.lambda_handler(_sightings_event('ABC1234', limit=1), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['count'] == 1
    assert 'nextToken' in body
    decoded = json.loads(base64.b64decode(body['nextToken']).decode('utf-8'))
    assert decoded == last_key
