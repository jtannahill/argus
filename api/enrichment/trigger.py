"""S3 PutObject event → Step Functions trigger for enrichment pipeline."""
import json
import os
import re
import sys
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import sighting_pk, sighting_sk

# Pattern: captures/{date}/{plate}/{timestamp}-vehicle.jpg
KEY_PATTERN = re.compile(
    r'^captures/(?P<date>[^/]+)/(?P<plate>[^/]+)/(?P<timestamp>[^/]+)-vehicle\.jpg$'
)


def lambda_handler(event, context):
    sfn_client = boto3.client('stepfunctions')
    state_machine_arn = os.environ['STATE_MACHINE_ARN']

    results = []

    for record in event.get('Records', []):
        key = record['s3']['object']['key']
        # S3 event keys are URL-encoded — decode %3A back to :
        from urllib.parse import unquote_plus
        key = unquote_plus(key)

        match = KEY_PATTERN.match(key)
        if not match:
            print(f"Skipping non-matching key: {key}")
            continue

        plate = match.group('plate')
        timestamp = match.group('timestamp')
        bucket = record['s3']['bucket']['name']

        # Derive sibling plate image key
        plate_image_key = key.replace('-vehicle.jpg', '-plate.jpg')

        # Look up sightingId and confidence from DynamoDB
        table = get_table()
        resp = table.get_item(
            Key={
                'PK': sighting_pk(plate),
                'SK': sighting_sk(timestamp),
            }
        )
        item = resp.get('Item', {})
        sighting_id = item.get('sightingId', '')
        confidence = item.get('confidence', 0)
        latitude = item.get('latitude', 0)
        longitude = item.get('longitude', 0)

        execution_input = {
            'plate': plate,
            'timestamp': timestamp,
            'sightingId': sighting_id,
            'confidence': confidence,
            'latitude': latitude,
            'longitude': longitude,
            'bucket': bucket,
            'plateImageKey': plate_image_key,
            'vehicleImageKey': key,
        }

        execution_name = re.sub(r'[^a-zA-Z0-9_-]', '-', f"{plate}-{timestamp}")[:80]

        sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=execution_name,
            input=json.dumps(execution_input),
        )

        results.append({'plate': plate, 'timestamp': timestamp, 'executionName': execution_name})
        print(f"Started execution {execution_name} for plate {plate}")

    return {'started': results}
