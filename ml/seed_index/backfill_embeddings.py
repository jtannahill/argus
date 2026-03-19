"""Backfill CLIP embeddings for all seeded Street View images.

Reads images from S3 index bucket, generates embeddings via the
SageMaker CLIP endpoint, and updates DynamoDB records.

Usage: python3 backfill_embeddings.py [--endpoint argus-clip] [--dry-run]
"""
import argparse
import json
import os

import boto3


def backfill(table_name, bucket, endpoint, dry_run=False):
    s3 = boto3.client('s3')
    sagemaker = boto3.client('sagemaker-runtime')
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(table_name)

    # List all images in the index bucket
    paginator = s3.get_paginator('list_objects_v2')
    images = []
    for page in paginator.paginate(Bucket=bucket, Prefix='buildings/'):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if key.endswith('.jpg'):
                images.append(key)

    print(f"Found {len(images)} images to process")

    processed = 0
    errors = 0
    for i, key in enumerate(images):
        # Parse BBL and heading from key: buildings/{bbl}/streetview_{heading}.jpg
        parts = key.split('/')
        if len(parts) < 3:
            continue
        bbl = parts[1]
        filename = parts[2].replace('.jpg', '')
        heading = filename.replace('streetview_', '')

        pk = f"BLDG#{bbl}"
        sk = f"IMAGE#seed-{heading}"

        if dry_run:
            print(f"  [{i+1}/{len(images)}] Would process {key} → {pk}/{sk}")
            continue

        try:
            # Download image
            img_obj = s3.get_object(Bucket=bucket, Key=key)
            img_bytes = img_obj['Body'].read()

            if len(img_bytes) < 5000:
                print(f"  [{i+1}/{len(images)}] Skipping {key} (too small: {len(img_bytes)} bytes)")
                continue

            # Generate embedding via SageMaker
            resp = sagemaker.invoke_endpoint(
                EndpointName=endpoint,
                ContentType='image/jpeg',
                Body=img_bytes,
            )
            result = json.loads(resp['Body'].read())
            embedding = result.get('embedding', [])

            if not embedding or len(embedding) < 512:
                print(f"  [{i+1}/{len(images)}] Bad embedding for {key}: len={len(embedding)}")
                errors += 1
                continue

            # Update DynamoDB with real embedding
            table.update_item(
                Key={'PK': pk, 'SK': sk},
                UpdateExpression='SET embedding = :e',
                ExpressionAttributeValues={':e': json.dumps(embedding)},
            )

            processed += 1
            if processed % 50 == 0:
                print(f"  [{i+1}/{len(images)}] Processed {processed} images...")

        except Exception as e:
            print(f"  [{i+1}/{len(images)}] Error on {key}: {e}")
            errors += 1

    print(f"\nDone! Processed: {processed}, Errors: {errors}, Total: {len(images)}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--table', default='ArgusData-ArgusTable68E6AF15-1SZWD17MIJ0OB')
    parser.add_argument('--bucket', default='argusdata-indexbucketa89c8461-fe7qbqgrv6pu')
    parser.add_argument('--endpoint', default='argus-clip')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    backfill(args.table, args.bucket, args.endpoint, args.dry_run)
