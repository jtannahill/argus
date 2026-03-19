"""Tests for POST /identify Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import identify.handler as handler  # noqa: E402


def _identify_event(body: dict) -> dict:
    return {
        'resource': '/identify',
        'httpMethod': 'POST',
        'body': json.dumps(body),
    }


SAMPLE_CANDIDATES = [
    {
        'bbl': '1005430021',
        'address': '350 5TH AVE',
        'ownername': 'EMPIRE STATE BUILDING',
        'latitude': '40.748817',
        'longitude': '-73.985428',
        'yearbuilt': '1931',
        'numfloors': '102',
    },
    {
        'bbl': '1005430022',
        'address': '320 5TH AVE',
        'ownername': 'SOME OWNER',
        'latitude': '40.748500',
        'longitude': '-73.985200',
        'yearbuilt': '1960',
        'numfloors': '20',
    },
]


@patch('identify.handler.NYCDataProvider')
@patch('identify.handler.get_table')
def test_identify_returns_candidates(mock_get_table, mock_provider_cls):
    """Returns 200 with candidates list when provider finds buildings."""
    provider_instance = MagicMock()
    provider_instance.resolve_location.return_value = SAMPLE_CANDIDATES
    mock_provider_cls.return_value = provider_instance

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    # No cached profile or story
    table_mock.get_item.return_value = {}

    event = _identify_event({'latitude': 40.748817, 'longitude': -73.985428, 'heading': 180.0})
    result = handler.lambda_handler(event, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert 'candidates' in body
    assert len(body['candidates']) == 2
    assert body['candidates'][0]['bbl'] == '1005430021'
    provider_instance.resolve_location.assert_called_once_with(40.748817, -73.985428, 180.0)


@patch('identify.handler.NYCDataProvider')
@patch('identify.handler.get_table')
def test_identify_requires_lat_lon_heading(mock_get_table, mock_provider_cls):
    """Returns 400 when any of latitude, longitude, or heading is missing."""
    missing_cases = [
        {'longitude': -73.985428, 'heading': 90.0},   # no latitude
        {'latitude': 40.748817, 'heading': 90.0},      # no longitude
        {'latitude': 40.748817, 'longitude': -73.985428},  # no heading
        {},                                             # all missing
    ]

    for body in missing_cases:
        event = _identify_event(body)
        result = handler.lambda_handler(event, None)
        assert result['statusCode'] == 400, f"Expected 400 for body: {body}"
        resp_body = json.loads(result['body'])
        assert 'error' in resp_body

    # Provider should never be called for invalid inputs
    mock_provider_cls.assert_not_called()


@patch('identify.handler.NYCDataProvider')
@patch('identify.handler.get_table')
def test_identify_checks_cache(mock_get_table, mock_provider_cls):
    """Attaches cached_profile and cached_story from DynamoDB when present."""
    provider_instance = MagicMock()
    provider_instance.resolve_location.return_value = [SAMPLE_CANDIDATES[0]]
    mock_provider_cls.return_value = provider_instance

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    cached_profile = {
        'PK': 'BLDG#1005430021',
        'SK': 'PROFILE',
        'address': '350 5TH AVE',
        'floors': 102,
        'owner': 'EMPIRE STATE REALTY',
    }
    cached_story = {
        'PK': 'BLDG#1005430021',
        'SK': 'STORY',
        'narrative': 'The Empire State Building was completed in 1931.',
        'generated_at': '2026-03-19T10:00:00Z',
    }

    def get_item_side_effect(Key):
        sk = Key.get('SK')
        if sk == 'PROFILE':
            return {'Item': cached_profile}
        if sk == 'STORY':
            return {'Item': cached_story}
        return {}

    table_mock.get_item.side_effect = get_item_side_effect

    event = _identify_event({'latitude': 40.748817, 'longitude': -73.985428, 'heading': 180.0})
    result = handler.lambda_handler(event, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    candidate = body['candidates'][0]
    assert 'cached_profile' in candidate
    assert candidate['cached_profile']['owner'] == 'EMPIRE STATE REALTY'
    assert 'cached_story' in candidate
    assert 'Empire State Building' in candidate['cached_story']['narrative']

    # DynamoDB should have been called twice: once for PROFILE, once for STORY
    assert table_mock.get_item.call_count == 2
    call_keys = [c.kwargs['Key'] for c in table_mock.get_item.call_args_list]
    assert {'PK': 'BLDG#1005430021', 'SK': 'PROFILE'} in call_keys
    assert {'PK': 'BLDG#1005430021', 'SK': 'STORY'} in call_keys


@patch('identify.handler.NYCDataProvider')
@patch('identify.handler.get_table')
def test_identify_candidate_without_bbl_skips_cache(mock_get_table, mock_provider_cls):
    """Candidates without a BBL are returned without a DynamoDB lookup."""
    no_bbl_candidate = {
        'address': '123 UNKNOWN ST',
        'latitude': '40.748000',
        'longitude': '-73.984000',
    }
    provider_instance = MagicMock()
    provider_instance.resolve_location.return_value = [no_bbl_candidate]
    mock_provider_cls.return_value = provider_instance

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    event = _identify_event({'latitude': 40.748, 'longitude': -73.984, 'heading': 0.0})
    result = handler.lambda_handler(event, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert len(body['candidates']) == 1
    assert 'cached_profile' not in body['candidates'][0]
    table_mock.get_item.assert_not_called()


@patch('identify.handler.NYCDataProvider')
@patch('identify.handler.get_table')
def test_identify_returns_empty_candidates_when_none_found(mock_get_table, mock_provider_cls):
    """Returns 200 with empty candidates list when provider finds nothing."""
    provider_instance = MagicMock()
    provider_instance.resolve_location.return_value = []
    mock_provider_cls.return_value = provider_instance

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    event = _identify_event({'latitude': 40.0, 'longitude': -74.0, 'heading': 45.0})
    result = handler.lambda_handler(event, None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['candidates'] == []
    table_mock.get_item.assert_not_called()
