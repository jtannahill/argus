"""Tests for story Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch
from io import BytesIO

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')
os.environ.setdefault('AWS_REGION', 'us-east-1')

import story.handler as handler  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_BBL = '1005430021'

SAMPLE_PROFILE_ITEM = {
    'PK': f'BLDG#{SAMPLE_BBL}',
    'SK': 'PROFILE',
    'bbl': SAMPLE_BBL,
    'address': '350 5TH AVE',
    'borough': '1',
    'yearbuilt': '1931',
    'numfloors': '102',
    'bldgclass': 'O5',
    'zonedist1': 'C5-3',
    'hasLandmark': True,
    'landmark': {
        'lpNumber': 'LP-1265',
        'buildingName': 'Empire State Building',
        'designatedDate': '1981-05-19T00:00:00.000',
    },
}

VALID_CLAUDE_RESPONSE = {
    'headline': 'The Art Deco Crown That Defined a Skyline',
    'narrative': (
        'Rising 102 stories above Midtown Manhattan, the Empire State Building '
        'stands as the quintessential expression of American ambition. '
        'Completed in 1931, its limestone and granite facade catches the dawn '
        'light in shades of gold. For over four decades it held the title of '
        "world's tallest building, an icon as much as a structure."
    ),
    'funFacts': [
        'Construction took only 410 days.',
        'The building has its own ZIP code: 10118.',
        'It was originally intended to moor dirigibles at its spire.',
    ],
}


def _make_bedrock_response(payload: dict) -> dict:
    """Build a mock bedrock invoke_model response."""
    body_str = json.dumps({
        'content': [{'text': json.dumps(payload)}],
    })
    return {'body': BytesIO(body_str.encode('utf-8'))}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@patch('story.handler._get_bedrock')
@patch('story.handler.get_table')
def test_happy_path_returns_narrative(mock_get_table, mock_get_bedrock):
    table_mock = MagicMock()
    table_mock.get_item.return_value = {'Item': dict(SAMPLE_PROFILE_ITEM)}
    mock_get_table.return_value = table_mock

    bedrock_mock = MagicMock()
    bedrock_mock.invoke_model.return_value = _make_bedrock_response(VALID_CLAUDE_RESPONSE)
    mock_get_bedrock.return_value = bedrock_mock

    result = handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    assert result['bbl'] == SAMPLE_BBL
    assert result['headline'] == VALID_CLAUDE_RESPONSE['headline']
    assert result['narrative'] == VALID_CLAUDE_RESPONSE['narrative']
    assert result['funFacts'] == VALID_CLAUDE_RESPONSE['funFacts']


@patch('story.handler._get_bedrock')
@patch('story.handler.get_table')
def test_story_written_to_dynamo(mock_get_table, mock_get_bedrock):
    table_mock = MagicMock()
    table_mock.get_item.return_value = {'Item': dict(SAMPLE_PROFILE_ITEM)}
    mock_get_table.return_value = table_mock

    bedrock_mock = MagicMock()
    bedrock_mock.invoke_model.return_value = _make_bedrock_response(VALID_CLAUDE_RESPONSE)
    mock_get_bedrock.return_value = bedrock_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    table_mock.put_item.assert_called_once()
    item = table_mock.put_item.call_args[1]['Item']
    assert item['PK'] == f'BLDG#{SAMPLE_BBL}'
    assert item['SK'] == 'STORY'
    assert item['headline'] == VALID_CLAUDE_RESPONSE['headline']
    assert 'generatedAt' in item
    assert 'modelId' in item


@patch('story.handler._get_bedrock')
@patch('story.handler.get_table')
def test_missing_profile_raises_lookup_error(mock_get_table, mock_get_bedrock):
    table_mock = MagicMock()
    table_mock.get_item.return_value = {}   # no 'Item' key
    mock_get_table.return_value = table_mock

    with pytest.raises(LookupError, match=SAMPLE_BBL):
        handler.lambda_handler({'bbl': SAMPLE_BBL}, None)


def test_missing_bbl_raises():
    with pytest.raises(ValueError, match='bbl'):
        handler.lambda_handler({}, None)


def test_parse_bedrock_response_clean_json():
    payload = {'headline': 'H', 'narrative': 'N', 'funFacts': ['f1', 'f2']}
    result = handler._parse_bedrock_response(json.dumps(payload))
    assert result['headline'] == 'H'
    assert result['funFacts'] == ['f1', 'f2']


def test_parse_bedrock_response_strips_markdown_fences():
    payload = {'headline': 'H', 'narrative': 'N', 'funFacts': []}
    fenced = f'```json\n{json.dumps(payload)}\n```'
    result = handler._parse_bedrock_response(fenced)
    assert result['headline'] == 'H'


def test_parse_bedrock_response_graceful_on_invalid_json():
    result = handler._parse_bedrock_response('this is not json')
    assert result['headline'] == 'A Building With Stories to Tell'
    assert 'this is not json' in result['narrative']
    assert result['funFacts'] == []


def test_build_prompt_includes_address():
    profile = dict(SAMPLE_PROFILE_ITEM)
    prompt = handler._build_prompt(SAMPLE_BBL, profile)
    assert '350 5TH AVE' in prompt
    assert 'Manhattan' in prompt
    assert '1931' in prompt
    assert '102' in prompt
    assert 'Empire State Building' in prompt


def test_build_prompt_no_landmark():
    profile = {
        'address': '1 MAIN ST',
        'borough': '3',
        'yearbuilt': '1955',
        'numfloors': '6',
        'bldgclass': 'D4',
        'zonedist1': 'R6',
        'hasLandmark': False,
    }
    prompt = handler._build_prompt('3012340001', profile)
    assert 'Brooklyn' in prompt
    assert 'Landmark designation: No' in prompt


def test_borough_name_mapping():
    assert handler._borough_name('1') == 'Manhattan'
    assert handler._borough_name('2') == 'Bronx'
    assert handler._borough_name('3') == 'Brooklyn'
    assert handler._borough_name('4') == 'Queens'
    assert handler._borough_name('5') == 'Staten Island'
    assert handler._borough_name('9') == 'New York City'


@patch('story.handler._get_bedrock')
@patch('story.handler.get_table')
def test_bedrock_invoked_with_correct_model(mock_get_table, mock_get_bedrock):
    table_mock = MagicMock()
    table_mock.get_item.return_value = {'Item': dict(SAMPLE_PROFILE_ITEM)}
    mock_get_table.return_value = table_mock

    bedrock_mock = MagicMock()
    bedrock_mock.invoke_model.return_value = _make_bedrock_response(VALID_CLAUDE_RESPONSE)
    mock_get_bedrock.return_value = bedrock_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    call_kwargs = bedrock_mock.invoke_model.call_args[1]
    assert call_kwargs['modelId'] == handler.BEDROCK_MODEL_ID
    assert call_kwargs['contentType'] == 'application/json'
    assert call_kwargs['accept'] == 'application/json'


@patch('story.handler._get_bedrock')
@patch('story.handler.get_table')
def test_bedrock_request_body_has_correct_shape(mock_get_table, mock_get_bedrock):
    table_mock = MagicMock()
    table_mock.get_item.return_value = {'Item': dict(SAMPLE_PROFILE_ITEM)}
    mock_get_table.return_value = table_mock

    bedrock_mock = MagicMock()
    bedrock_mock.invoke_model.return_value = _make_bedrock_response(VALID_CLAUDE_RESPONSE)
    mock_get_bedrock.return_value = bedrock_mock

    handler.lambda_handler({'bbl': SAMPLE_BBL}, None)

    call_kwargs = bedrock_mock.invoke_model.call_args[1]
    body = json.loads(call_kwargs['body'])
    assert body['max_tokens'] == 500
    assert body['messages'][0]['role'] == 'user'
    assert '350 5TH AVE' in body['messages'][0]['content']
