"""Buildings endpoint - retrieve building details by BBL."""
import json


def lambda_handler(event, context):
    """Return building data for a given BBL (Borough-Block-Lot)."""
    bbl = event.get("pathParameters", {}).get("bbl", "")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({"bbl": bbl, "message": "stub"}),
    }
