"""Tests for GET /search/address Lambda handler."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')
os.environ.setdefault('GEOCLIENT_APP_KEY', 'test-key-abc123')

import search_address.handler as handler  # noqa: E402


def _event(query: str | None) -> dict:
    params = {"q": query} if query is not None else {}
    return {
        "httpMethod": "GET",
        "queryStringParameters": params or None,
        "requestContext": {
            "authorizer": {
                "claims": {"sub": "user-123"}
            }
        },
    }


GEOCLIENT_RESPONSE = {
    "results": [
        {
            "request": "350 5th ave manhattan",
            "response": {
                "bbl": "1005430021",
                "houseNumber": "350",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.748817",
                "longitude": "-73.985428",
            },
        },
        {
            "request": "352 5th ave manhattan",
            "response": {
                "bbl": "1005430022",
                "houseNumber": "352",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.748900",
                "longitude": "-73.985300",
            },
        },
        {
            "request": "354 5th ave manhattan",
            "response": {
                "bbl": "1005430023",
                "houseNumber": "354",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.748950",
                "longitude": "-73.985250",
            },
        },
        {
            "request": "356 5th ave manhattan",
            "response": {
                "bbl": "1005430024",
                "houseNumber": "356",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.749000",
                "longitude": "-73.985200",
            },
        },
        {
            "request": "358 5th ave manhattan",
            "response": {
                "bbl": "1005430025",
                "houseNumber": "358",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.749050",
                "longitude": "-73.985150",
            },
        },
        # 6th result — should be trimmed to top 5
        {
            "request": "360 5th ave manhattan",
            "response": {
                "bbl": "1005430026",
                "houseNumber": "360",
                "firstStreetNameNormalized": "5 AVENUE",
                "firstBoroughName": "MANHATTAN",
                "zipCode": "10118",
                "latitude": "40.749100",
                "longitude": "-73.985100",
            },
        },
    ]
}


@patch('search_address.handler.requests.get')
def test_returns_results(mock_get):
    """Returns 200 with up to 5 normalised results."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = GEOCLIENT_RESPONSE
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = handler.lambda_handler(_event("350 5th ave"), {})

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert "results" in body
    # Must be capped at 5
    assert len(body["results"]) == 5
    # First result should have the expected fields
    first = body["results"][0]
    assert first["bbl"] == "1005430021"
    assert first["address"] == "350 5 AVENUE"
    assert first["borough"] == "MANHATTAN"
    assert first["zipCode"] == "10118"
    assert first["latitude"] == 40.748817
    assert first["longitude"] == -73.985428


@patch('search_address.handler.requests.get')
def test_empty_query_returns_400(mock_get):
    """Empty or missing q param returns 400 without calling Geoclient."""
    result = handler.lambda_handler(_event(""), {})
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "error" in body
    mock_get.assert_not_called()

    # Also test with no queryStringParameters at all
    event_no_params = {
        "httpMethod": "GET",
        "queryStringParameters": None,
        "requestContext": {"authorizer": {"claims": {"sub": "u1"}}},
    }
    result2 = handler.lambda_handler(event_no_params, {})
    assert result2["statusCode"] == 400


@patch('search_address.handler.requests.get')
def test_no_results_returns_empty_list(mock_get):
    """Geoclient returning an empty results list yields an empty array."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    result = handler.lambda_handler(_event("xyz nonexistent place"), {})

    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["results"] == []
