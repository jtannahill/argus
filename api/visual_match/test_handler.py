"""Tests for visual_match Lambda handler."""

import json
import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')
os.environ.setdefault('CLIP_ENDPOINT_NAME', 'argus-clip-embedding')
os.environ.setdefault('IMAGE_BUCKET', 'argus-images')

import visual_match.handler as handler  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_FAKE_EMBEDDING = [0.1] * 256 + [0.2] * 256  # 512 floats


def _event(s3_key: str = 'uploads/photo.jpg',
           candidates=None,
           bucket: str = 'argus-images') -> dict:
    return {
        's3Key': s3_key,
        'candidates': candidates or [{'bbl': '3012340001'}],
        'bucket': bucket,
    }


def _ref_item(bbl: str, embedding: list = None) -> dict:
    emb = embedding or _FAKE_EMBEDDING
    return {
        'PK': f'BLDG#{bbl}',
        'SK': 'IMAGE#2026-01-01T00:00:00.000Z',
        's3Key': 'seed/building.jpg',
        'embedding': [Decimal(str(v)) for v in emb],
        'createdAt': '2026-01-01T00:00:00.000Z',
    }


# ---------------------------------------------------------------------------
# _cosine_similarity unit tests (no mocking needed)
# ---------------------------------------------------------------------------

def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.0]
    score = handler._cosine_similarity(v, v)
    assert abs(score - 1.0) < 1e-9


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    score = handler._cosine_similarity(a, b)
    assert abs(score) < 1e-9


def test_cosine_similarity_opposite_vectors():
    a = [1.0, 0.0]
    b = [-1.0, 0.0]
    score = handler._cosine_similarity(a, b)
    assert abs(score - (-1.0)) < 1e-9


def test_cosine_similarity_zero_vector_returns_zero():
    a = [0.0, 0.0]
    b = [1.0, 1.0]
    score = handler._cosine_similarity(a, b)
    assert score == 0.0


# ---------------------------------------------------------------------------
# lambda_handler — happy path: visual match found
# ---------------------------------------------------------------------------

@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_visual_match_returns_matched_bbl(mock_sm, mock_s3, mock_get_table):
    # S3 returns photo bytes
    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    # SageMaker returns an embedding near-identical to the reference
    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': _FAKE_EMBEDDING})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    # DynamoDB returns one reference image for the candidate BBL
    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    table_mock.query.return_value = {'Items': [_ref_item('3012340001')]}
    table_mock.put_item.return_value = {}

    result = handler.lambda_handler(_event(), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['matchedBbl'] == '3012340001'
    assert body['method'] == 'visual'
    assert body['confidence'] >= handler.CONFIDENCE_THRESHOLD
    assert body['corrected'] is False
    assert body['gpsBbl'] == '3012340001'


@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_visual_match_detects_correction(mock_sm, mock_s3, mock_get_table):
    """GPS says BBL A, but visual match finds BBL B with high confidence."""
    embedding_a = [1.0] + [0.0] * 511
    embedding_b = [0.0, 1.0] + [0.0] * 510

    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    # User photo embedding matches BBL B
    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': embedding_b})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock

    # Two candidates → two query calls; return A's refs first, then B's refs
    table_mock.query.side_effect = [
        {'Items': [_ref_item('BBL_A', embedding_a)]},
        {'Items': [_ref_item('BBL_B', embedding_b)]},
    ]
    table_mock.put_item.return_value = {}

    candidates = [{'bbl': 'BBL_A'}, {'bbl': 'BBL_B'}]
    result = handler.lambda_handler(_event(candidates=candidates), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['matchedBbl'] == 'BBL_B'
    assert body['gpsBbl'] == 'BBL_A'
    assert body['corrected'] is True
    assert body['method'] == 'visual'


# ---------------------------------------------------------------------------
# lambda_handler — geo_fallback when no references exceed threshold
# ---------------------------------------------------------------------------

@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_geo_fallback_when_no_reference_images(mock_sm, mock_s3, mock_get_table):
    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': _FAKE_EMBEDDING})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    # No IMAGE# records
    table_mock.query.return_value = {'Items': []}
    table_mock.put_item.return_value = {}

    result = handler.lambda_handler(_event(), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['method'] == 'geo_fallback'
    assert body['matchedBbl'] == '3012340001'
    assert body['corrected'] is False


@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_geo_fallback_when_similarity_below_threshold(mock_sm, mock_s3, mock_get_table):
    user_emb = [1.0] + [0.0] * 511          # unit vector along dim 0
    ref_emb = [0.0, 1.0] + [0.0] * 510      # unit vector along dim 1 — orthogonal

    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': user_emb})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    table_mock.query.return_value = {'Items': [_ref_item('3012340001', ref_emb)]}
    table_mock.put_item.return_value = {}

    result = handler.lambda_handler(_event(), None)
    body = json.loads(result['body'])

    assert result['statusCode'] == 200
    assert body['method'] == 'geo_fallback'
    assert body['confidence'] < handler.CONFIDENCE_THRESHOLD


# ---------------------------------------------------------------------------
# lambda_handler — embedding storage
# ---------------------------------------------------------------------------

@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_stores_user_embedding_in_dynamo(mock_sm, mock_s3, mock_get_table):
    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': _FAKE_EMBEDDING})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    table_mock.query.return_value = {'Items': [_ref_item('3012340001')]}
    table_mock.put_item.return_value = {}

    handler.lambda_handler(_event(), None)

    assert table_mock.put_item.called
    call_kwargs = table_mock.put_item.call_args[1]
    item = call_kwargs['Item']
    assert item['PK'] == 'BLDG#3012340001'
    assert item['SK'].startswith('IMAGE#')
    assert item['s3Key'] == 'uploads/photo.jpg'
    assert len(item['embedding']) == 512


# ---------------------------------------------------------------------------
# lambda_handler — error handling
# ---------------------------------------------------------------------------

def test_missing_s3_key_returns_400():
    event = {'candidates': [{'bbl': '3012340001'}], 'bucket': 'argus-images'}
    result = handler.lambda_handler(event, None)
    assert result['statusCode'] == 400
    body = json.loads(result['body'])
    assert 's3Key' in body['error']


def test_missing_candidates_returns_400():
    event = {'s3Key': 'uploads/photo.jpg', 'bucket': 'argus-images', 'candidates': []}
    result = handler.lambda_handler(event, None)
    assert result['statusCode'] == 400


def test_missing_bucket_returns_400():
    # Temporarily unset env var
    original = os.environ.pop('IMAGE_BUCKET', None)
    try:
        event = {'s3Key': 'uploads/photo.jpg', 'candidates': [{'bbl': '1'}]}
        result = handler.lambda_handler(event, None)
        assert result['statusCode'] == 400
        body = json.loads(result['body'])
        assert 'bucket' in body['error']
    finally:
        if original is not None:
            os.environ['IMAGE_BUCKET'] = original


@patch('visual_match.handler._get_s3')
def test_s3_failure_returns_502(mock_s3):
    s3_mock = MagicMock()
    s3_mock.get_object.side_effect = Exception('S3 connection timeout')
    mock_s3.return_value = s3_mock

    result = handler.lambda_handler(_event(), None)
    assert result['statusCode'] == 502
    body = json.loads(result['body'])
    assert 'S3 fetch failed' in body['error']


@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_sagemaker_failure_returns_502(mock_sm, mock_s3):
    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    sm_mock = MagicMock()
    sm_mock.invoke_endpoint.side_effect = Exception('Endpoint not available')
    mock_sm.return_value = sm_mock

    result = handler.lambda_handler(_event(), None)
    assert result['statusCode'] == 502
    body = json.loads(result['body'])
    assert 'SageMaker inference failed' in body['error']


# ---------------------------------------------------------------------------
# lambda_handler — body parsing (API Gateway wraps in 'body' string)
# ---------------------------------------------------------------------------

@patch('visual_match.handler.get_table')
@patch('visual_match.handler._get_s3')
@patch('visual_match.handler._get_sagemaker')
def test_api_gateway_body_string_parsed(mock_sm, mock_s3, mock_get_table):
    """Verify handler accepts API Gateway events where body is a JSON string."""
    s3_mock = MagicMock()
    s3_mock.get_object.return_value = {'Body': MagicMock(read=MagicMock(return_value=b'JPEG'))}
    mock_s3.return_value = s3_mock

    sm_mock = MagicMock()
    sm_body = json.dumps({'embedding': _FAKE_EMBEDDING})
    sm_mock.invoke_endpoint.return_value = {
        'Body': MagicMock(read=MagicMock(return_value=sm_body.encode()))
    }
    mock_sm.return_value = sm_mock

    table_mock = MagicMock()
    mock_get_table.return_value = table_mock
    table_mock.query.return_value = {'Items': [_ref_item('3012340001')]}
    table_mock.put_item.return_value = {}

    apigw_event = {
        'body': json.dumps({
            's3Key': 'uploads/photo.jpg',
            'candidates': [{'bbl': '3012340001'}],
            'bucket': 'argus-images',
        })
    }

    result = handler.lambda_handler(apigw_event, None)
    assert result['statusCode'] == 200
