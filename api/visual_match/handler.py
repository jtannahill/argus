"""POST /visual-match — compare user photo against GPS candidate buildings.

Receives:
    {
        "s3Key": "uploads/user-photo.jpg",
        "bucket": "argus-images",
        "candidates": [{"bbl": "3012340001"}, ...]
    }

Returns:
    {
        "matchedBbl": "3012340001",
        "confidence": 0.91,
        "method": "visual",   # or "geo_fallback"
        "gpsBbl": "3012340001",
        "corrected": false
    }

Flow:
  1. Fetch the user photo from S3.
  2. Send it to the CLIP SageMaker endpoint → 512-dim embedding.
  3. For each candidate BBL, query DynamoDB for IMAGE# records that have a
     stored embedding.
  4. Compute cosine similarity between user photo and each reference embedding.
  5. Pick the best match above CONFIDENCE_THRESHOLD; fall back to the first
     GPS candidate if nothing clears the bar.
  6. Store the user photo embedding back in the building image index so future
     scans benefit from it.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import building_pk, image_sk

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIDENCE_THRESHOLD = 0.75

_sagemaker_runtime = None
_s3_client = None


def _get_sagemaker():
    global _sagemaker_runtime
    if _sagemaker_runtime is None:
        _sagemaker_runtime = boto3.client('sagemaker-runtime')
    return _sagemaker_runtime


def _get_s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client('s3')
    return _s3_client


# ---------------------------------------------------------------------------
# Cosine similarity — pure Python, no numpy in Lambda
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list, b: list) -> float:
    """Compute cosine similarity between two equal-length float lists.

    Returns a value in [-1, 1].  Returns 0.0 if either vector is zero.
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


# ---------------------------------------------------------------------------
# Lambda entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}') if isinstance(event.get('body'), str) else event
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON body'})

    s3_key = body.get('s3Key')
    candidates = body.get('candidates', [])
    bucket = body.get('bucket') or os.environ.get('IMAGE_BUCKET', '')

    if not s3_key:
        return _response(400, {'error': 'Missing required field: s3Key'})
    if not bucket:
        return _response(400, {'error': 'Missing required field: bucket (or IMAGE_BUCKET env var)'})
    if not candidates:
        return _response(400, {'error': 'Missing required field: candidates'})

    # 1. Fetch user photo from S3
    try:
        photo_bytes = _fetch_s3_object(bucket, s3_key)
    except Exception as exc:
        return _response(502, {'error': f'S3 fetch failed: {str(exc)}'})

    # 2. Get CLIP embedding from SageMaker
    try:
        user_embedding = _get_clip_embedding(photo_bytes)
    except Exception as exc:
        return _response(502, {'error': f'SageMaker inference failed: {str(exc)}'})

    # 3. & 4. Compare against reference embeddings per candidate
    gps_bbl = candidates[0].get('bbl') if candidates else None
    best_bbl = None
    best_score = -1.0

    for candidate in candidates:
        bbl = candidate.get('bbl', '').strip()
        if not bbl:
            continue

        ref_embeddings = _fetch_reference_embeddings(bbl)
        for ref_emb in ref_embeddings:
            score = _cosine_similarity(user_embedding, ref_emb)
            if score > best_score:
                best_score = score
                best_bbl = bbl

    # 5. Decide method
    if best_bbl and best_score >= CONFIDENCE_THRESHOLD:
        matched_bbl = best_bbl
        method = 'visual'
        confidence = round(best_score, 4)
        corrected = (matched_bbl != gps_bbl)
    else:
        matched_bbl = gps_bbl
        method = 'geo_fallback'
        confidence = round(max(best_score, 0.0), 4) if best_score >= 0 else 0.0
        corrected = False

    # 6. Store user embedding in building image index
    if matched_bbl:
        try:
            _store_image_embedding(matched_bbl, s3_key, user_embedding)
        except Exception:
            # Non-fatal — log but don't fail the response
            pass

    return _response(200, {
        'matchedBbl': matched_bbl,
        'confidence': confidence,
        'method': method,
        'gpsBbl': gps_bbl,
        'corrected': corrected,
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_s3_object(bucket: str, key: str) -> bytes:
    s3 = _get_s3()
    obj = s3.get_object(Bucket=bucket, Key=key)
    return obj['Body'].read()


def _get_clip_embedding(image_bytes: bytes) -> list:
    """Invoke the CLIP SageMaker endpoint and return the 512-dim embedding."""
    endpoint_name = os.environ.get('CLIP_ENDPOINT_NAME', 'argus-clip-embedding')
    runtime = _get_sagemaker()

    response = runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType='image/jpeg',
        Body=image_bytes,
    )
    result = json.loads(response['Body'].read())
    return result['embedding']


def _fetch_reference_embeddings(bbl: str) -> list:
    """Query DynamoDB for IMAGE# records for the given BBL that have embeddings.

    Returns a list of embedding lists (each 512 floats).
    """
    table = get_table()
    pk = building_pk(bbl)

    resp = table.query(
        KeyConditionExpression=Key('PK').eq(pk) & Key('SK').begins_with('IMAGE#'),
    )

    embeddings = []
    for item in resp.get('Items', []):
        raw = item.get('embedding')
        if raw is None:
            continue
        # DynamoDB stores as list of Decimal; convert to float
        try:
            emb = [float(v) for v in raw]
            if len(emb) == 512:
                embeddings.append(emb)
        except (TypeError, ValueError):
            continue

    return embeddings


def _store_image_embedding(bbl: str, s3_key: str, embedding: list) -> None:
    """Write the user photo embedding into the building image index."""
    table = get_table()
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

    table.put_item(Item={
        'PK': building_pk(bbl),
        'SK': image_sk(timestamp),
        's3Key': s3_key,
        'embedding': [Decimal(str(round(v, 8))) for v in embedding],
        'createdAt': timestamp,
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
