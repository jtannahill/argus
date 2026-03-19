"""Merge enrichment results + cross-validate classifier vs registration."""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import sighting_pk, sighting_sk, enrichment_sk


def _cross_validate(classifier: dict, registration: dict) -> list[str]:
    """Compare vehicle classifier output against DMV registration data."""
    mismatches = []

    # Compare make
    cls_make = (classifier.get('make') or '').strip().lower()
    reg_make = (registration.get('make') or '').strip().lower()
    if cls_make and reg_make and cls_make != reg_make:
        mismatches.append(f"make mismatch: classifier={cls_make!r} vs registration={reg_make!r}")

    # Compare model
    cls_model = (classifier.get('model') or '').strip().lower()
    reg_model = (registration.get('model') or '').strip().lower()
    if cls_model and reg_model and cls_model != reg_model:
        mismatches.append(f"model mismatch: classifier={cls_model!r} vs registration={reg_model!r}")

    # Compare year (allow ±1 tolerance for model-year ambiguity)
    cls_year = classifier.get('year')
    reg_year = registration.get('year')
    if cls_year and reg_year:
        try:
            if abs(int(cls_year) - int(reg_year)) > 1:
                mismatches.append(f"year mismatch: classifier={cls_year} vs registration={reg_year}")
        except (TypeError, ValueError):
            pass

    # Compare color
    cls_color = (classifier.get('color') or '').strip().lower()
    reg_color = (registration.get('color') or '').strip().lower()
    if cls_color and reg_color and cls_color != reg_color:
        mismatches.append(f"color mismatch: classifier={cls_color!r} vs registration={reg_color!r}")

    return mismatches


def lambda_handler(event, context):
    plate = event.get('plate', '')
    sighting_id = event.get('sightingId', '')
    timestamp = event.get('timestamp', '')
    confidence = event.get('confidence', 0)
    bucket = event.get('bucket', '')
    plate_image_key = event.get('plateImageKey', '')
    vehicle_image_key = event.get('vehicleImageKey', '')

    plate_lookup = event.get('plateLookup', {})
    vehicle_classifier = event.get('vehicleClassifier', {})
    plate_read = event.get('plateRead', {})

    registration = plate_lookup.get('registration', {})
    mismatches = _cross_validate(vehicle_classifier, registration)

    diplomatic = {}

    enrichment = {
        'PK': sighting_pk(plate),
        'SK': enrichment_sk(),
        'sightingId': sighting_id,
        'plate': plate,
        'timestamp': timestamp,
        'enrichedAt': datetime.now(timezone.utc).isoformat(),
        'plateLookup': plate_lookup,
        'vehicleClassifier': vehicle_classifier,
        'plateRead': plate_read,
        'mismatches': mismatches,
        'hasMismatch': len(mismatches) > 0,
        'diplomatic': diplomatic,
    }

    table = get_table()

    # Write enrichment record
    table.put_item(Item=enrichment)

    # Update sighting status to 'complete'
    table.update_item(
        Key={
            'PK': sighting_pk(plate),
            'SK': sighting_sk(timestamp),
        },
        UpdateExpression='SET #status = :status, enrichedAt = :enrichedAt',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={
            ':status': 'complete',
            ':enrichedAt': enrichment['enrichedAt'],
        },
    )

    return {
        'plate': plate,
        'sightingId': sighting_id,
        'timestamp': timestamp,
        'latitude': event.get('latitude', 0),
        'longitude': event.get('longitude', 0),
        'hasMismatch': enrichment['hasMismatch'],
        'mismatches': mismatches,
        'enrichedAt': enrichment['enrichedAt'],
        'diplomatic': diplomatic,
    }
