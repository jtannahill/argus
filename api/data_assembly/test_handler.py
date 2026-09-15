"""Tests for data_assembly Lambda handler."""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import data_assembly.handler as handler  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

SAMPLE_BBL = '1005430021'

SAMPLE_PROFILE = {
    'bbl': SAMPLE_BBL,
    'address': '350 5TH AVE',
    'yearbuilt': '1931',
    'numfloors': '102',
    'bldgclass': 'O5',
    'zonedist1': 'C5-3',
    'latitude': '40.748440',
    'longitude': '-73.985664',
}

SAMPLE_OWNERSHIP = [
    {
        'name': 'EMPIRE STATE REALTY TRUST',
        'recorded_datetime': '2013-10-07T00:00:00.000',
        'doctype': 'DEED',
    }
]

SAMPLE_VIOLATIONS = {
    'dob': [
        {
            'violationid': 'DOB001',
            'description': 'Illegal conversion',
            'issuedate': '2024-01-15',
        }
    ],
    'hpd': [
        {
            'violationid': 'HPD001',
            'novdescription': 'Heat/hot water',
            'inspectiondate': '2024-02-01',
        }
    ],
}

SAMPLE_PERMITS = [
    {
        'job__': 'JOB123456',
        'jobtype': 'A1',
        'filing_date': '2023-05-10',
        'permittypedescription': 'Alteration',
    }
]

SAMPLE_LANDMARKS = [
    {
        'lpNumber': 'LP-1265',
        'buildingName': 'Empire State Building',
        'designatedDate': '1981-05-19T00:00:00.000',
    }
]

SAMPLE_ASSESSED = {
    'parid': SAMPLE_BBL,
    'avland': '10000000',
    'avtot': '85000000',
}


def _make_provider_mock():
    m = MagicMock()
    m.get_profile.return_value = dict(SAMPLE_PROFILE)
    m.get_ownership.return_value = list(SAMPLE_OWNERSHIP)
    m.get_violations.return_value = dict(SAMPLE_VIOLATIONS)
    m.get_permits.return_value = list(SAMPLE_PERMITS)
    m.get_landmarks.return_value = list(SAMPLE_LANDMARKS)
    m.get_assessed_value.return_value = dict(SAMPLE_ASSESSED)
    return m


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_happy_path_returns_summary(mock_provider_cls, mock_get_table):
    mock_provider_cls.return_value = _make_provider_mock()
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    assert result['bbl'] == SAMPLE_BBL
    assert result['ownershipCount'] == 1
    assert result['violationCount'] == 2   # 1 DOB + 1 HPD
    assert result['permitCount'] == 1
    assert result['hasLandmark'] is True
    assert 'assembledAt' in result


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_dynamo_writes_correct_number_of_items(mock_provider_cls, mock_get_table):
    mock_provider_cls.return_value = _make_provider_mock()
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    # 1 PROFILE + 1 OWNER + 2 VIOLATIONS + 1 PERMIT = 5 put_item calls
    assert table_mock.put_item.call_count == 5


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_profile_item_has_correct_keys(mock_provider_cls, mock_get_table):
    mock_provider_cls.return_value = _make_provider_mock()
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    # First call should be the PROFILE write
    first_call_kwargs = table_mock.put_item.call_args_list[0][1]
    item = first_call_kwargs['Item']
    assert item['PK'] == f'BLDG#{SAMPLE_BBL}'
    assert item['SK'] == 'PROFILE'
    assert item['bbl'] == SAMPLE_BBL
    assert 'assembledAt' in item
    # landmark should be merged in
    assert 'landmark' in item
    assert item['hasLandmark'] is True


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_violation_items_include_source(mock_provider_cls, mock_get_table):
    mock_provider_cls.return_value = _make_provider_mock()
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    calls = table_mock.put_item.call_args_list
    # Violations are calls 2 and 3 (0=profile, 1=owner, 2=dob viol, 3=hpd viol, 4=permit)
    dob_item = calls[2][1]['Item']
    hpd_item = calls[3][1]['Item']

    assert dob_item['_source'] == 'dob'
    assert dob_item['SK'].startswith('VIOLATION#')
    assert hpd_item['_source'] == 'hpd'
    assert hpd_item['SK'].startswith('VIOLATION#')


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_no_landmark_sets_has_landmark_false(mock_provider_cls, mock_get_table):
    provider_mock = _make_provider_mock()
    provider_mock.get_landmarks.return_value = []
    mock_provider_cls.return_value = provider_mock
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    assert result['hasLandmark'] is False

    first_call_item = table_mock.put_item.call_args_list[0][1]['Item']
    assert first_call_item['hasLandmark'] is False
    assert 'landmark' not in first_call_item


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_none_profile_is_handled(mock_provider_cls, mock_get_table):
    provider_mock = _make_provider_mock()
    provider_mock.get_profile.return_value = None
    mock_provider_cls.return_value = provider_mock
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    result = handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    assert result['bbl'] == SAMPLE_BBL
    assert isinstance(result['profile'], dict)


def test_missing_bbl_raises():
    with pytest.raises(ValueError, match='bbl'):
        handler.lambda_handler({}, None)


def test_sanitize_removes_none_and_empty_string():
    raw = {'a': 'hello', 'b': None, 'c': '', 'd': 0, 'e': False}
    cleaned = handler._sanitize(raw)
    assert 'b' not in cleaned
    assert 'c' not in cleaned
    assert cleaned['a'] == 'hello'
    assert cleaned['d'] == 0
    assert cleaned['e'] is False


def test_sanitize_converts_float_to_decimal():
    raw = {'lat': 40.7484, 'lon': -73.9856}
    cleaned = handler._sanitize(raw)
    assert isinstance(cleaned['lat'], Decimal)
    assert isinstance(cleaned['lon'], Decimal)


def test_sanitize_nested_dict():
    raw = {'outer': {'inner': 3.14, 'null': None}}
    cleaned = handler._sanitize(raw)
    assert isinstance(cleaned['outer']['inner'], Decimal)
    assert 'null' not in cleaned['outer']


@patch('data_assembly.handler.get_table')
@patch('data_assembly.handler.NYCDataProvider')
def test_floats_in_profile_become_decimals_in_dynamo(mock_provider_cls, mock_get_table):
    provider_mock = _make_provider_mock()
    provider_mock.get_profile.return_value = {
        'bbl': SAMPLE_BBL,
        'latitude': 40.748440,   # native float
        'longitude': -73.985664, # native float
    }
    mock_provider_cls.return_value = provider_mock
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    profile_item = table_mock.put_item.call_args_list[0][1]['Item']
    assert isinstance(profile_item['latitude'], Decimal)
    assert isinstance(profile_item['longitude'], Decimal)
