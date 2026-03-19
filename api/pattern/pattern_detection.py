"""Pattern detection — evaluates sighting history for anomalies and geofence breaches."""

import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from math import radians, sin, cos, sqrt, atan2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared.dynamo import get_table
from shared.models import sighting_pk, alert_pk

from boto3.dynamodb.conditions import Key, Attr


def lambda_handler(event, context):
    plate = event['plate']
    sighting_id = event['sightingId']
    timestamp = event['timestamp']
    lat = float(event.get('latitude', 0))
    lon = float(event.get('longitude', 0))
    mismatch = event.get('hasMismatch', False)
    mismatch_details = event.get('mismatches', [])

    table = get_table()
    alerts = []

    # Get last 7 days of sightings for this plate
    cutoff_dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) - timedelta(days=7)
    cutoff = cutoff_dt.strftime('%Y-%m-%dT%H:%M:%S') + 'Z'

    sightings = []
    query_kwargs = {
        'KeyConditionExpression': Key('PK').eq(sighting_pk(plate)) & Key('SK').gte(f'SIGHTING#{cutoff}'),
    }
    while True:
        response = table.query(**query_kwargs)
        sightings.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        query_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    # Get all geofences
    geofences = []
    scan_kwargs = {
        'FilterExpression': Attr('PK').begins_with('GEOFENCE#') & Attr('SK').eq('META'),
    }
    while True:
        response = table.scan(**scan_kwargs)
        geofences.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']

    # Rule 1: Repeat visit — same plate, same geofence, 3+ times in 7 days
    for gf in geofences:
        polygon = json.loads(gf.get('polygon', '[]'))
        if not polygon:
            continue
        count = sum(1 for s in sightings if _point_in_polygon(
            float(s.get('latitude', 0)), float(s.get('longitude', 0)), polygon
        ))
        if count >= 3:
            alerts.append({
                'type': 'repeat_visit',
                'plate': plate,
                'geofenceId': gf.get('geofenceId', ''),
                'message': f"Plate {plate} seen {count} times at {gf.get('label', 'zone')} in 7 days",
            })

    # Rule 2: Circling — 2+ sightings within 30 min, different GPS points within 500m
    recent = [s for s in sightings if _within_minutes(s.get('timestamp', ''), timestamp, 30)]
    if len(recent) >= 2:
        points = [(float(s.get('latitude', 0)), float(s.get('longitude', 0))) for s in recent]
        if _all_within_radius(points, 0.5) and _has_distinct_points(points):
            alerts.append({
                'type': 'circling',
                'plate': plate,
                'message': f"Plate {plate} seen {len(recent)} times within 30 min in a 500m radius",
            })

    # Rule 3: Clone suspicion
    if mismatch:
        alerts.append({
            'type': 'clone_suspicion',
            'plate': plate,
            'message': f"Vehicle mismatch for {plate}: {', '.join(mismatch_details)}",
        })

    # Write alerts to DynamoDB
    for alert in alerts:
        alert_id = str(uuid.uuid4())
        table.put_item(Item={
            'PK': alert_pk(alert_id),
            'SK': timestamp,
            **alert,
        })

    return {'plate': plate, 'sightingId': sighting_id, 'alerts': alerts}


def _point_in_polygon(lat: float, lon: float, polygon: list) -> bool:
    """Ray casting algorithm for point-in-polygon."""
    n = len(polygon)
    inside = False
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        if ((yi > lat) != (yj > lat)) and (lon < (xj - xi) * (lat - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _within_minutes(ts1: str, ts2: str, minutes: int) -> bool:
    try:
        dt1 = datetime.fromisoformat(ts1.replace('Z', '+00:00'))
        dt2 = datetime.fromisoformat(ts2.replace('Z', '+00:00'))
        return abs((dt2 - dt1).total_seconds()) <= minutes * 60
    except (ValueError, TypeError):
        return False


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def _all_within_radius(points: list, radius_km: float) -> bool:
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if _haversine_km(points[i][0], points[i][1], points[j][0], points[j][1]) > radius_km:
                return False
    return True


def _has_distinct_points(points: list, min_distance_km: float = 0.01) -> bool:
    """Ensure points aren't all at the exact same location."""
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            if _haversine_km(points[i][0], points[i][1], points[j][0], points[j][1]) > min_distance_km:
                return True
    return False
