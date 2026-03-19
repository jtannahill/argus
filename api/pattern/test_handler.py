"""Tests for pattern detection Lambda."""

import json
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))
os.environ['TABLE_NAME'] = 'test-table'


def _make_sightings(plate, count, geohash='dr5reg', hours_apart=24):
    """Generate fake sighting items."""
    base = datetime(2026, 3, 19, 12, 0, 0)
    items = []
    for i in range(count):
        ts = (base - timedelta(hours=hours_apart * i)).isoformat() + 'Z'
        items.append({
            'PK': f'PLATE#{plate}',
            'SK': f'SIGHTING#{ts}',
            'plate': plate,
            'timestamp': ts,
            'latitude': '25.7617',
            'longitude': '-80.1918',
            'GSI1PK': f'GPS_HASH#{geohash}',
        })
    return items


@patch('pattern_detection.get_table')
def test_repeat_visit_alert(mock_table):
    table_mock = MagicMock()
    table_mock.query.return_value = {'Items': _make_sightings('ABC1234', 4, hours_apart=48)}
    table_mock.scan.return_value = {
        'Items': [{
            'PK': 'GEOFENCE#123',
            'SK': 'META',
            'geofenceId': '123',
            'label': 'Home',
            'polygon': '[[25.75,-80.20],[25.78,-80.20],[25.78,-80.18],[25.75,-80.18]]',
            'alertFor': 'all',
        }]
    }
    mock_table.return_value = table_mock

    from pattern_detection import lambda_handler
    result = lambda_handler({
        'plate': 'ABC1234',
        'sightingId': 'test',
        'timestamp': '2026-03-19T12:00:00Z',
        'latitude': 25.7617,
        'longitude': -80.1918,
        'hasMismatch': False,
    }, None)

    assert any(a['type'] == 'repeat_visit' for a in result['alerts'])


@patch('pattern_detection.get_table')
def test_circling_alert(mock_table):
    table_mock = MagicMock()
    # 3 sightings within 30 min at different GPS points
    base = datetime(2026, 3, 19, 12, 0, 0)
    items = []
    for i in range(3):
        ts = (base - timedelta(minutes=10 * i)).isoformat() + 'Z'
        items.append({
            'PK': 'PLATE#XYZ9999',
            'SK': f'SIGHTING#{ts}',
            'plate': 'XYZ9999',
            'timestamp': ts,
            'latitude': str(25.7617 + i * 0.001),
            'longitude': str(-80.1918 + i * 0.001),
            'GSI1PK': 'GPS_HASH#dr5reg',
        })
    table_mock.query.return_value = {'Items': items}
    table_mock.scan.return_value = {'Items': []}
    mock_table.return_value = table_mock

    from pattern_detection import lambda_handler
    result = lambda_handler({
        'plate': 'XYZ9999',
        'sightingId': 'test',
        'timestamp': '2026-03-19T12:00:00Z',
        'latitude': 25.7617,
        'longitude': -80.1918,
        'hasMismatch': False,
    }, None)

    assert any(a['type'] == 'circling' for a in result['alerts'])


@patch('pattern_detection.get_table')
def test_clone_suspicion_alert(mock_table):
    table_mock = MagicMock()
    table_mock.query.return_value = {'Items': []}
    table_mock.scan.return_value = {'Items': []}
    mock_table.return_value = table_mock

    from pattern_detection import lambda_handler
    result = lambda_handler({
        'plate': 'ABC1234',
        'sightingId': 'test',
        'timestamp': '2026-03-19T12:00:00Z',
        'latitude': 25.7617,
        'longitude': -80.1918,
        'hasMismatch': True,
        'mismatches': ['make: classifier=Honda, reg=Toyota'],
    }, None)

    assert any(a['type'] == 'clone_suspicion' for a in result['alerts'])
