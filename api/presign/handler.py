"""POST /captures/presign — Generate pre-signed S3 URLs and create sighting record."""

import json
import os
import uuid
import time
from datetime import datetime, timezone

import boto3

from shared.dynamo import get_table
from shared.models import sighting_pk, sighting_sk, gsi1_pk, gsi2_pk

s3_client = boto3.client('s3')
BUCKET = os.environ.get('CAPTURES_BUCKET', '')


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})

    required = ['plate', 'confidence', 'latitude', 'longitude', 'timestamp', 'mode']
    missing = [f for f in required if f not in body]
    if missing:
        return _response(400, {'error': f'Missing fields: {", ".join(missing)}'})

    plate = body['plate'].upper().replace(' ', '')
    confidence = float(body['confidence'])
    lat = float(body['latitude'])
    lon = float(body['longitude'])
    timestamp = body['timestamp']
    mode = body['mode']
    sighting_id = str(uuid.uuid4())
    date_str = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).strftime('%Y-%m-%d')

    plate_key = f"captures/{date_str}/{plate}/{timestamp}-plate.jpg"
    vehicle_key = f"captures/{date_str}/{plate}/{timestamp}-vehicle.jpg"

    plate_url = s3_client.generate_presigned_url(
        'put_object',
        Params={'Bucket': BUCKET, 'Key': plate_key, 'ContentType': 'image/jpeg'},
        ExpiresIn=300,
    )
    vehicle_url = s3_client.generate_presigned_url(
        'put_object',
        Params={'Bucket': BUCKET, 'Key': vehicle_key, 'ContentType': 'image/jpeg'},
        ExpiresIn=300,
    )

    table = get_table()
    table.put_item(Item={
        'PK': sighting_pk(plate),
        'SK': sighting_sk(timestamp),
        'GSI1PK': gsi1_pk(lat, lon),
        'GSI1SK': sighting_sk(timestamp),
        'GSI2PK': gsi2_pk(timestamp),
        'GSI2SK': sighting_pk(plate),
        'sightingId': sighting_id,
        'plate': plate,
        'confidence': str(confidence),
        'latitude': str(lat),
        'longitude': str(lon),
        'timestamp': timestamp,
        'mode': mode,
        'plateImageKey': plate_key,
        'vehicleImageKey': vehicle_key,
        'enrichmentStatus': 'pending',
        'ttl': int(time.time()) + 365 * 86400,
    })

    return _response(200, {
        'sightingId': sighting_id,
        'plateUploadUrl': plate_url,
        'vehicleUploadUrl': vehicle_url,
    })


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body),
    }
