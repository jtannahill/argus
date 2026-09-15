"""Step Functions task — assemble NYC building data and persist to DynamoDB.

Receives an event with {bbl}, fetches data from all NYC public APIs via
NYCDataProvider, and writes normalized records to the single DynamoDB table.
Returns a summary dict that Step Functions passes to the next state.
"""

import os
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import building_pk, profile_sk, owner_sk, violation_sk, permit_sk
from shared.nyc_data import NYCDataProvider


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    bbl = event.get('bbl', '').strip()
    if not bbl:
        raise ValueError('Event must include a non-empty "bbl" field')

    provider = NYCDataProvider()
    table = get_table()

    # -- Fetch all data sources -------------------------------------------------
    profile = provider.get_profile(bbl) or {}
    ownership = provider.get_ownership(bbl)
    violations_data = provider.get_violations(bbl)
    permits = provider.get_permits(bbl)
    landmarks = provider.get_landmarks(bbl)
    assessed = provider.get_assessed_value(bbl)

    # -- Merge supplementary data into profile ----------------------------------
    if landmarks:
        profile['landmark'] = landmarks[0]
        profile['hasLandmark'] = True
    else:
        profile['hasLandmark'] = False

    if assessed:
        profile['assessedValue'] = assessed

    # -- Flatten violations list ------------------------------------------------
    dob_violations = violations_data.get('dob', [])
    hpd_violations = violations_data.get('hpd', [])
    all_violations = [
        {**v, '_source': 'dob'} for v in dob_violations
    ] + [
        {**v, '_source': 'hpd'} for v in hpd_violations
    ]

    assembled_at = datetime.now(timezone.utc).isoformat()
    pk = building_pk(bbl)

    # -- Write PROFILE record ---------------------------------------------------
    profile_item = _sanitize({
        'PK': pk,
        'SK': profile_sk(),
        'bbl': bbl,
        'assembledAt': assembled_at,
        **profile,
    })
    table.put_item(Item=profile_item)

    # -- Write OWNER records ----------------------------------------------------
    for record in ownership:
        date_raw = record.get('recorded_datetime', assembled_at)
        # Truncate to date-only for the sort key to avoid special-char issues
        date_str = date_raw[:10] if date_raw else assembled_at[:10]
        item = _sanitize({
            'PK': pk,
            'SK': owner_sk(date_str),
            'bbl': bbl,
            **record,
        })
        table.put_item(Item=item)

    # -- Write VIOLATION records ------------------------------------------------
    for violation in all_violations:
        vid = (
            violation.get('violationid')
            or violation.get('violation_id')
            or violation.get('violationnumber')
            or violation.get('issuancenumber')
            or 'UNKNOWN'
        )
        item = _sanitize({
            'PK': pk,
            'SK': violation_sk(str(vid)),
            'bbl': bbl,
            **violation,
        })
        table.put_item(Item=item)

    # -- Write PERMIT records ---------------------------------------------------
    for permit in permits:
        pid = (
            permit.get('job__')
            or permit.get('jobnum')
            or permit.get('job_filing_number')
            or permit.get('permit_si_no')
            or 'UNKNOWN'
        )
        item = _sanitize({
            'PK': pk,
            'SK': permit_sk(str(pid)),
            'bbl': bbl,
            **permit,
        })
        table.put_item(Item=item)

    return {
        'bbl': bbl,
        'profile': profile,
        'ownershipCount': len(ownership),
        'violationCount': len(all_violations),
        'permitCount': len(permits),
        'hasLandmark': bool(landmarks),
        'assembledAt': assembled_at,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sanitize(item: dict) -> dict:
    """Return a copy of *item* safe for DynamoDB.

    - Removes keys whose value is None or empty string.
    - Converts float values to Decimal (DynamoDB rejects native floats).
    """
    result = {}
    for key, value in item.items():
        if value is None or value == '':
            continue
        result[key] = _convert_value(value)
    return result


def _convert_value(value):
    if isinstance(value, float):
        return _float_to_decimal(value)
    if isinstance(value, dict):
        return _sanitize(value)
    if isinstance(value, list):
        return [_convert_value(v) for v in value if v is not None and v != '']
    return value


def _float_to_decimal(value: float) -> Decimal:
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal('0')
