"""GET /search/address?q={query} — typeahead address search via NYC Geoclient v2."""

import json
import os
import sys

import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

GEOCLIENT_API_URL = "https://api.nyc.gov/geoclient/v2/search"
GEOCLIENT_APP_KEY = os.environ.get("GEOCLIENT_APP_KEY", "")
TABLE_NAME = os.environ.get("TABLE_NAME", "")

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Content-Type": "application/json",
}


def lambda_handler(event, context):
    # Handle preflight
    if event.get("httpMethod") == "OPTIONS":
        return _response(200, {})

    # Extract userId from Cognito claims (informational — not required for search)
    claims = (
        event.get("requestContext", {})
        .get("authorizer", {})
        .get("claims", {})
    )
    user_id = claims.get("sub", "anonymous")  # noqa: F841

    # Query param
    params = event.get("queryStringParameters") or {}
    query = (params.get("q") or "").strip()

    if not query:
        return _response(400, {"error": "Missing required query parameter: q"})

    if not GEOCLIENT_APP_KEY:
        return _response(500, {"error": "GEOCLIENT_APP_KEY not configured"})

    try:
        resp = requests.get(
            GEOCLIENT_API_URL,
            params={"input": query},
            headers={"Ocp-Apim-Subscription-Key": GEOCLIENT_APP_KEY},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        return _response(504, {"error": "Geoclient API timed out"})
    except requests.exceptions.RequestException as exc:
        return _response(502, {"error": f"Geoclient API error: {str(exc)}"})
    except ValueError:
        return _response(502, {"error": "Invalid JSON from Geoclient API"})

    results = _parse_results(data)
    return _response(200, {"results": results[:5]})


def _parse_results(data: dict) -> list:
    """Extract normalised result dicts from a Geoclient v2 search response."""
    results = []

    # Geoclient v2 search returns a top-level "results" list; each entry has a
    # "response" object whose shape depends on the result type (address, place,
    # intersection, …).  We pull the fields we care about from whichever keys
    # are present.
    raw_list = data.get("results") or []

    for item in raw_list:
        response = item.get("response") or {}

        # BBL — present on address / BIN responses
        bbl = (
            response.get("bbl")
            or response.get("buildingIdentificationNumber")
            or ""
        )

        # Human-readable address
        house_number = response.get("houseNumber") or response.get("houseNumberIn") or ""
        street = (
            response.get("firstStreetNameNormalized")
            or response.get("streetName1In")
            or response.get("streetName")
            or ""
        )
        address = f"{house_number} {street}".strip() if (house_number or street) else ""
        if not address:
            address = response.get("inputAddress") or item.get("request", "") or ""

        borough = response.get("firstBoroughName") or response.get("boroughCode1In") or ""
        zip_code = response.get("zipCode") or response.get("uspsPreferredZip") or None

        # Coordinates
        try:
            latitude = float(response["latitude"]) if response.get("latitude") else None
        except (TypeError, ValueError):
            latitude = None

        try:
            longitude = float(response["longitude"]) if response.get("longitude") else None
        except (TypeError, ValueError):
            longitude = None

        # Skip results that have neither a usable address nor a BBL
        if not address and not bbl:
            continue

        results.append({
            "bbl": str(bbl),
            "address": address,
            "borough": str(borough) if borough else None,
            "zipCode": str(zip_code) if zip_code else None,
            "latitude": latitude,
            "longitude": longitude,
        })

    return results


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps(body),
    }
