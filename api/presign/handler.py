"""POST /captures/presign — Generate pre-signed S3 URLs for building photo uploads."""

import json
import os
import uuid
from datetime import datetime, timezone

import boto3

from shared.dynamo import get_table
from shared.models import building_pk, image_sk

s3_client = boto3.client('s3')
BUCKET = os.environ.get('CAPTURES_BUCKET', '')


def lambda_handler(event, context):
    """Generate a pre-signed PUT URL for uploading a building photo."""
    try:
        body = json.loads(event.get('body') or '{}')
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON body'})

    bbl = body.get('bbl', '')
    latitude = body.get('latitude')
    longitude = body.get('longitude')

    if not bbl:
        return _response(400, {'error': 'bbl is required'})

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    photo_key = f"captures/{bbl}/{timestamp}.jpg"

    try:
        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={'Bucket': BUCKET, 'Key': photo_key, 'ContentType': 'image/jpeg'},
            ExpiresIn=300,
        )
    except Exception as e:
        return _response(502, {'error': f'S3 presign error: {str(e)}'})

    return _response(200, {
        'uploadUrl': upload_url,
        'photoKey': photo_key,
        'bbl': bbl,
    })


def _response(code, body):
    return {
        'statusCode': code,
        'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
        'body': json.dumps(body),
    }
