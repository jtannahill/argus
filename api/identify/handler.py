"""POST /identify — resolve GPS + heading to building candidates.

Enriches the top candidate with ownership, violations, and an AI-generated
story (via Bedrock). Subsequent candidates get profile only.
"""

import json
import os
import sys
from decimal import Decimal

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import building_pk, profile_sk, story_sk
from shared.nyc_data import NYCDataProvider
from shared.raycaster import BuildingRayCaster


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body') or '{}')
    except (json.JSONDecodeError, TypeError):
        return _response(400, {'error': 'Invalid JSON body'})

    lat = body.get('latitude')
    lon = body.get('longitude')
    heading = body.get('heading')

    if lat is None or lon is None or heading is None:
        return _response(400, {'error': 'Missing required fields: latitude, longitude, heading'})

    try:
        lat = float(lat)
        lon = float(lon)
        heading = float(heading)
    except (TypeError, ValueError):
        return _response(400, {'error': 'latitude, longitude, and heading must be numeric'})

    radius = float(body.get('radius', 100))  # Default 100m, good for general use

    # Optional elevation-aware targeting params
    altitude = body.get('altitude')  # metres above sea level (CLLocation.altitude)
    pitch = body.get('pitch')        # degrees: 0=horizontal, -90=straight down

    if altitude is not None:
        try:
            altitude = float(altitude)
        except (TypeError, ValueError):
            altitude = None

    if pitch is not None:
        try:
            pitch = float(pitch)
        except (TypeError, ValueError):
            pitch = None

    # When the user is elevated and pointing downward, project the camera ray
    # to ground level and shift the search origin to that intersection point.
    if altitude and pitch and pitch < -5:
        import math
        ground_distance = altitude / math.tan(abs(math.radians(pitch)))
        lat_offset = ground_distance * math.cos(math.radians(heading)) / 111320
        lon_offset = ground_distance * math.sin(math.radians(heading)) / (111320 * math.cos(math.radians(lat)))
        lat = lat + lat_offset
        lon = lon + lon_offset

    # Narrow the heading cone as distance grows so far-mode identifies
    # the specific building you're pointing at rather than everything in
    # a half-mile arc.
    #   30 m  → 90°  (wide, you're right next to it)
    #   100 m → 45°  (street level)
    #   300 m → 20°  (across the block)
    #   800 m → 8°   (skyline sniper mode)
    # A caller may override by sending an explicit `cone` parameter.
    if radius <= 30:
        default_cone = 90.0
    elif radius <= 100:
        default_cone = 45.0
    elif radius <= 300:
        default_cone = 20.0
    else:
        default_cone = 8.0
    cone = float(body.get('cone', default_cone))

    provider = NYCDataProvider()
    try:
        candidates = provider.resolve_location(lat, lon, heading, radius_m=radius, cone_degrees=cone)
    except Exception as exc:
        return _response(502, {'error': f'NYC data provider error: {str(exc)}'})

    # 3D ray casting: re-sort candidates by ray intersection when altitude
    # and pitch are available.  This replaces the heading-cone heuristic
    # with true occlusion-aware ordering.
    if altitude is not None or pitch is not None:
        # Fetch measured roof heights from the NYC 3D Building Footprints
        # dataset (u9wf-3gbt).  Use a radius large enough to cover all
        # candidates, capped at 300 m to keep the API call fast.
        building_heights = None
        try:
            height_radius = min(max(radius * 1.5, 100), 300)
            building_heights = provider.get_building_heights(lat, lon, radius_m=height_radius)
        except Exception:
            pass  # non-fatal: raycaster falls back to PLUTO numfloors

        raycaster = BuildingRayCaster()
        candidates = raycaster.cast(
            lat, lon,
            altitude if altitude is not None else 2.0,
            heading,
            pitch if pitch is not None else 0.0,
            candidates,
            building_heights=building_heights,
        )

    table = get_table()
    enriched = []
    for candidate in candidates:
        raw_bbl = candidate.get('bbl', '').strip()
        # PLUTO returns BBL as decimal string like "1004830001.00000000"
        bbl = raw_bbl.split('.')[0] if '.' in raw_bbl else raw_bbl

        # Normalize to match iOS BuildingCandidate model
        try:
            blat = float(candidate.get('latitude', 0))
            blon = float(candidate.get('longitude', 0))
            dist = provider._haversine(lat, lon, blat, blon)
        except (TypeError, ValueError):
            dist = 0

        # Calculate air rights (unused FAR)
        try:
            built_far = float(candidate.get('builtfar', 0) or 0)
            max_far = float(candidate.get('residfar', 0) or candidate.get('commfar', 0) or candidate.get('facilfar', 0) or 0)
            lot_area = float(candidate.get('lotarea', 0) or 0)
            unused_far = max(0, max_far - built_far)
            air_rights_sqft = int(unused_far * lot_area) if lot_area > 0 else 0
        except (TypeError, ValueError):
            unused_far = 0
            air_rights_sqft = 0

        # Detect diplomatic/government ownership
        owner_name = candidate.get('ownername', '') or ''
        exempt_total = candidate.get('exempttot', '0') or '0'
        try:
            is_tax_exempt = float(exempt_total) > 0
        except (TypeError, ValueError):
            is_tax_exempt = False

        diplomatic_signals = _detect_diplomatic(owner_name, is_tax_exempt)

        entry = {
            'id': bbl,
            'bbl': bbl,
            'address': candidate.get('address', ''),
            'distance': round(dist, 1),
            'score': 0.0,
            'profile': {
                'yearBuilt': candidate.get('yearbuilt', ''),
                'stories': candidate.get('numfloors', ''),
                'units': candidate.get('unitstotal', ''),
                'residentialUnits': candidate.get('unitsres', ''),
                'lotArea': candidate.get('lotarea', ''),
                'buildingClass': candidate.get('bldgclass', ''),
                'zoneDist': candidate.get('zonedist1', ''),
                'far': candidate.get('builtfar', ''),
                'maxFar': str(max_far) if max_far else candidate.get('residfar', ''),
                'landmark': candidate.get('landmark', ''),
                'landmarkName': candidate.get('landmkname', ''),
                'architect': None,
                'architecturalStyle': None,
                'assessedLand': candidate.get('assessland', ''),
                'assessedTotal': candidate.get('assesstot', ''),
                'taxClass': candidate.get('taxclass', ''),
                'latitude': blat,
                'longitude': blon,
                'ownerName': owner_name,
                'airRightsSqft': air_rights_sqft,
                'unusedFar': round(unused_far, 2),
                'isTaxExempt': is_tax_exempt,
                'diplomaticStatus': diplomatic_signals,
            },
        }

        # Enrich top candidate with ownership, violations, and story
        if bbl and len(enriched) == 0:
            # Ownership from ACRIS
            try:
                ownership_raw = provider.get_ownership(bbl)
                if ownership_raw:
                    entry['ownership'] = [{
                        'name': r.get('name', r.get('party_name', '')),
                        'type': r.get('doc_type', r.get('docType', '')),
                        'percentage': None,
                        'since': r.get('recorded_datetime', r.get('documentDate', ''))[:10] if r.get('recorded_datetime') or r.get('documentDate') else None,
                    } for r in ownership_raw[:5]]
            except Exception:
                pass

            # Violations from DOB + HPD
            try:
                violations_raw = provider.get_violations(bbl)
                all_violations = []
                if isinstance(violations_raw, dict):
                    all_violations = violations_raw.get('dob', []) + violations_raw.get('hpd', [])
                elif isinstance(violations_raw, list):
                    all_violations = violations_raw
                if all_violations:
                    entry['violations'] = [{
                        'violationId': v.get('isn_dob_bis_viol', v.get('violationid', str(i))),
                        'source': v.get('_source', 'DOB'),
                        'date': v.get('issue_date', v.get('inspectiondate', '')),
                        'description': v.get('description', v.get('novdescription', '')),
                        'status': v.get('violation_type', v.get('currentstatus', '')),
                        'severity': None,
                    } for i, v in enumerate(all_violations[:10])]
            except Exception:
                pass

            # Story — check DynamoDB cache first, generate via Bedrock if missing
            pk = building_pk(bbl)
            story = None
            try:
                story_resp = table.get_item(Key={'PK': pk, 'SK': story_sk()})
                story_item = story_resp.get('Item')
                if story_item:
                    story = {
                        'headline': story_item.get('headline', ''),
                        'narrative': story_item.get('narrative', ''),
                        'funFacts': story_item.get('funFacts', []),
                        'generatedAt': story_item.get('generatedAt', ''),
                    }
            except Exception:
                pass

            if not story:
                story = _generate_story(entry, table, pk)

            if story:
                entry['story'] = story

        enriched.append(entry)

    return _response(200, {'candidates': enriched})


def _generate_story(entry, table, pk):
    """Generate building story via Bedrock and cache it."""
    try:
        profile = entry.get('profile', {})
        address = entry.get('address', 'Unknown')
        year = profile.get('yearBuilt', 'Unknown')
        stories = profile.get('stories', '')
        landmark = profile.get('landmark', '')
        bldg_class = profile.get('buildingClass', '')
        zone = profile.get('zoneDist', '')
        owner = ''
        if entry.get('ownership'):
            owner = entry['ownership'][0].get('name', '')

        units = profile.get('units', '')
        res_units = profile.get('residentialUnits', '0')
        is_commercial = res_units in ('0', '', None) and units
        diplo = entry.get('profile', {}).get('diplomaticStatus', {})
        air_sqft = entry.get('profile', {}).get('airRightsSqft', 0)

        prompt = (
            f"You are a knowledgeable NYC building expert. Write a brief, engaging profile of this building.\n\n"
            f"Building: {address}\nYear Built: {year}\nStories: {stories}\n"
            f"Building Class: {bldg_class}\nZoning: {zone}\nUnits: {units}\n"
            f"{'Landmark: ' + landmark if landmark else ''}\n"
            f"{'Current Owner: ' + owner if owner else ''}\n"
            f"{'Type: Commercial (0 residential units)' if is_commercial else ''}\n"
            f"{'DIPLOMATIC/FOREIGN GOVERNMENT PROPERTY — owned by: ' + owner if diplo.get('isDiplomatic') else ''}\n"
            f"{'GOVERNMENT PROPERTY — ' + owner if diplo.get('isGovernment') and not diplo.get('isDiplomatic') else ''}\n"
            f"{'Air Rights: ' + str(air_sqft) + ' sq ft of unused development rights' if air_sqft > 0 else ''}\n\n"
            f'Respond in JSON: {{"headline": "one-line hook under 80 chars", '
            f'"narrative": "2-3 paragraph engaging story covering history, architecture, and neighborhood context'
            f'{". Include notable current or past tenants, businesses, or retail if known" if is_commercial else ""}'
            f'{". Mention any recent notable events, sales, or news about this property or block if known" if owner else ""}'
            f'", '
            f'"funFacts": ["fact 1", "fact 2", "fact 3"]'
            f'{", " if is_commercial else ""}'
            f'{"notableTenants: [tenant 1, tenant 2] or empty list if unknown" if is_commercial else ""}'
            f'}}\n\n'
            f"Be specific and factual. Only include tenants/businesses you're confident about. "
            f"If not a famous building, focus on architectural style, era, and neighborhood character."
        )

        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        resp = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            contentType='application/json',
            accept='application/json',
            body=json.dumps({
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 500,
                'messages': [{'role': 'user', 'content': prompt}],
            }),
        )
        result = json.loads(resp['body'].read())
        text = result['content'][0]['text']

        # Parse JSON from response
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            story = json.loads(text[start:end])
        else:
            story = {'headline': '', 'narrative': text, 'funFacts': []}

        story['generatedAt'] = __import__('datetime').datetime.utcnow().isoformat()

        # Cache in DynamoDB
        from shared.models import story_sk
        table.put_item(Item={
            'PK': pk,
            'SK': story_sk(),
            'headline': story.get('headline', ''),
            'narrative': story.get('narrative', ''),
            'funFacts': story.get('funFacts', []),
            'generatedAt': story['generatedAt'],
        })

        return story
    except Exception:
        return None


def _detect_diplomatic(owner_name: str, is_tax_exempt: bool) -> dict:
    """Detect if a building has diplomatic/foreign government ownership signals."""
    owner_upper = owner_name.upper()

    # Known patterns for foreign government ownership
    diplomatic_keywords = [
        'CONSULATE', 'CONSUL', 'EMBASSY', 'MISSION', 'DELEGATION',
        'PERMANENT MISSION', 'REPUBLIC OF', 'KINGDOM OF', 'STATE OF',
        'GOVERNMENT OF', 'PEOPLES REPUBLIC', "PEOPLE'S REPUBLIC",
        'UNITED NATIONS', 'DIPLOMATIC', 'FOREIGN MINISTRY',
    ]

    government_keywords = [
        'CITY OF NEW YORK', 'NYC', 'STATE OF NEW YORK', 'NYS',
        'UNITED STATES', 'US GOVERNMENT', 'FEDERAL', 'USPS',
        'MTA', 'PORT AUTHORITY', 'HOUSING AUTHORITY', 'NYCHA',
    ]

    is_diplomatic = any(kw in owner_upper for kw in diplomatic_keywords)
    is_government = any(kw in owner_upper for kw in government_keywords)

    status = None
    if is_diplomatic:
        status = 'diplomatic'
    elif is_government:
        status = 'government'
    elif is_tax_exempt and owner_upper and not any(c.isdigit() for c in owner_upper[:3]):
        status = 'tax_exempt'

    return {
        'status': status,
        'isDiplomatic': is_diplomatic,
        'isGovernment': is_government,
        'isTaxExempt': is_tax_exempt,
        'ownerName': owner_name,
    }


def _convert_decimals(obj):
    if isinstance(obj, list):
        return [_convert_decimals(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _convert_decimals(v) for k, v in obj.items()}
    if isinstance(obj, Decimal):
        return float(obj)
    return obj


def _response(status_code: int, body: dict) -> dict:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
        },
        'body': json.dumps(body),
    }
