"""Tests for scan_analytics aggregator Lambda."""

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('TABLE_NAME', 'test-table')

import scan_analytics.aggregator as aggregator  # noqa: E402

# Reusable heat items representing yesterday's building scan counters
HEAT_ITEMS = [
    {
        'PK': 'HEAT#2026-03-18',
        'SK': 'BLDG#1000477501',
        'scanCount': Decimal('8'),
        'uniqueUsers': {'user-1', 'user-2', 'user-3'},
    },
    {
        'PK': 'HEAT#2026-03-18',
        'SK': 'BLDG#2000112233',
        'scanCount': Decimal('3'),
        'uniqueUsers': {'user-1'},
    },
    {
        'PK': 'HEAT#2026-03-18',
        'SK': 'BLDG#3001234567',
        'scanCount': Decimal('6'),
        'uniqueUsers': {'user-2', 'user-4'},
    },
]


def _make_table_mock(items):
    table_mock = MagicMock()
    table_mock.query.return_value = {'Items': items}
    return table_mock


@patch('scan_analytics.aggregator.get_table')
def test_correctly_sums_scan_counts(mock_get_table):
    """Verifies totalScans and buildingsScanned are rolled up correctly."""
    table_mock = _make_table_mock(HEAT_ITEMS)
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    # 8 + 3 + 6 = 17
    assert result['totalScans'] == 17
    assert result['buildingsScanned'] == 3


@patch('scan_analytics.aggregator.get_table')
def test_identifies_trending_buildings(mock_get_table):
    """Verifies buildings with scanCount >= 5 are flagged as trending."""
    table_mock = _make_table_mock(HEAT_ITEMS)
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    # Buildings 1000477501 (8 scans) and 3001234567 (6 scans) exceed threshold of 5
    # Building 2000112233 (3 scans) does NOT
    assert result['trendingCount'] == 2


@patch('scan_analytics.aggregator.get_table')
def test_non_trending_building_excluded(mock_get_table):
    """Verifies buildings below the trending threshold are not included."""
    table_mock = _make_table_mock(HEAT_ITEMS)
    mock_get_table.return_value = table_mock

    aggregator.lambda_handler({}, None)

    put_kwargs = table_mock.put_item.call_args[1]
    item = put_kwargs['Item']
    trending_bbls = [b['bbl'] for b in item['trendingBuildings']]

    assert '1000477501' in trending_bbls
    assert '3001234567' in trending_bbls
    assert '2000112233' not in trending_bbls


@patch('scan_analytics.aggregator.get_table')
def test_writes_analytics_summary(mock_get_table):
    """Verifies an ANALYTICS#daily summary record is written to DynamoDB."""
    table_mock = _make_table_mock(HEAT_ITEMS)
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    assert table_mock.put_item.call_count == 1
    put_kwargs = table_mock.put_item.call_args[1]
    item = put_kwargs['Item']

    assert item['PK'] == 'ANALYTICS#daily'
    assert 'SK' in item           # date string
    assert item['totalScans'] == Decimal('17')
    assert item['buildingsScanned'] == Decimal('3')
    assert item['trendingCount'] == Decimal('2')


@patch('scan_analytics.aggregator.get_table')
def test_result_contains_date(mock_get_table):
    """Verifies the returned dict includes a date key."""
    table_mock = _make_table_mock(HEAT_ITEMS)
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    assert 'date' in result
    # Date should be in YYYY-MM-DD format
    parts = result['date'].split('-')
    assert len(parts) == 3


@patch('scan_analytics.aggregator.get_table')
def test_empty_partition_produces_zero_counts(mock_get_table):
    """Verifies graceful handling when no heat records exist for yesterday."""
    table_mock = _make_table_mock([])
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    assert result['totalScans'] == 0
    assert result['buildingsScanned'] == 0
    assert result['trendingCount'] == 0


@patch('scan_analytics.aggregator.get_table')
def test_pagination_accumulates_all_items(mock_get_table):
    """Verifies paginated query results are fully accumulated."""
    table_mock = MagicMock()
    # First page returns 2 items and signals a next page
    table_mock.query.side_effect = [
        {'Items': HEAT_ITEMS[:2], 'LastEvaluatedKey': {'PK': 'HEAT#2026-03-18', 'SK': 'BLDG#2000112233'}},
        {'Items': HEAT_ITEMS[2:]},
    ]
    mock_get_table.return_value = table_mock

    result = aggregator.lambda_handler({}, None)

    assert table_mock.query.call_count == 2
    assert result['totalScans'] == 17
    assert result['buildingsScanned'] == 3
