"""Tests for search Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import search.handler as handler  # noqa: E402


def _search_event(params: dict) -> dict:
    return {
        'queryStringParameters': params,
    }


@patch('search.handler.get_table')
def test_prefix_search(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    table_mock.scan.return_value = {
        'Items': [
            {
                'PK': 'PLATE#ABC1234',
                'SK': 'SIGHTING#2026-03-19T12:00:00Z',
                'plate': 'ABC1234',
                'timestamp': '2026-03-19T12:00:00Z',
                'confidence': '0.95',
            },
            {
                'PK': 'PLATE#ABC1234',
                'SK': 'SIGHTING#2026-03-19T11:00:00Z',
                'plate': 'ABC1234',
                'timestamp': '2026-03-19T11:00:00Z',
                'confidence': '0.90',
            },
        ]
    }

    result = handler.lambda_handler(_search_event({'q': 'ABC'}), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    # Deduplicated: 2 sightings for same plate → 1 result
    assert body['count'] == 1
    assert body['results'][0]['plate'] == 'ABC1234'


def test_missing_query_returns_400():
    result = handler.lambda_handler({'queryStringParameters': None}, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 400
    assert 'error' in body
