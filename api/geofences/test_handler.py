"""Tests for geofences Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import geofences.handler as handler  # noqa: E402

_POLYGON = [[25.77, -80.19], [25.78, -80.19], [25.78, -80.18], [25.77, -80.18]]


def _post_event(body: dict) -> dict:
    return {'httpMethod': 'POST', 'body': json.dumps(body), 'pathParameters': None}


def _get_event() -> dict:
    return {'httpMethod': 'GET', 'body': None, 'pathParameters': None}


def _delete_event(geofence_id: str) -> dict:
    return {'httpMethod': 'DELETE', 'body': None, 'pathParameters': {'id': geofence_id}}


@patch('geofences.handler.get_table')
def test_create_geofence(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler(_post_event({'label': 'Zone A', 'polygon': _POLYGON}), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 201
    assert 'geofenceId' in body
    assert body['label'] == 'Zone A'
    assert body['polygon'] == _POLYGON
    table_mock.put_item.assert_called_once()


@patch('geofences.handler.get_table')
def test_list_geofences(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    table_mock.scan.return_value = {
        'Items': [
            {
                'PK': 'GEOFENCE#abc-123',
                'SK': 'GEOFENCE#abc-123',
                'geofenceId': 'abc-123',
                'label': 'Zone A',
                'polygon': json.dumps(_POLYGON),
                'active': True,
            }
        ]
    }

    result = handler.lambda_handler(_get_event(), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['count'] == 1
    assert body['geofences'][0]['label'] == 'Zone A'
    assert body['geofences'][0]['polygon'] == _POLYGON


@patch('geofences.handler.get_table')
def test_delete_geofence(mock_get_table):
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    geofence_id = 'abc-123'
    result = handler.lambda_handler(_delete_event(geofence_id), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['deleted'] == geofence_id
    table_mock.delete_item.assert_called_once()
