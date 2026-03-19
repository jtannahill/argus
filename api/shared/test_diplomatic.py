"""Tests for diplomatic plate detection."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))


def test_us_diplomat_plate():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('D001234')
    assert result is not None
    assert result['isDiplomatic'] is True
    assert result['issuingCountry'] == 'US'
    assert result['prefix'] == 'D'
    assert result['plateType'] == 'diplomat'
    assert result['countryCode'] == '001'
    assert result['mission'] is not None
    assert result['mission']['country'] == 'United Kingdom'


def test_us_consul_plate():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('C011456')
    assert result is not None
    assert result['plateType'] == 'consul'
    assert result['countryCode'] == '011'


def test_us_staff_plate():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('S005123')
    assert result is not None
    assert result['plateType'] == 'staff'


def test_us_attache_plate():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('A020789')
    assert result is not None
    assert result['plateType'] == 'attache'


def test_canadian_diplomatic():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('CD12345')
    assert result is not None
    assert result['isDiplomatic'] is True
    assert result['issuingCountry'] == 'CA'
    assert result['plateType'] == 'diplomat'
    assert result['mission'] is None


def test_canadian_consular():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('CC54321')
    assert result is not None
    assert result['plateType'] == 'consul'


def test_mexican_diplomatic():
    from diplomatic import detect_diplomatic_format
    result = detect_diplomatic_format('DMT12345')
    assert result is not None
    assert result['isDiplomatic'] is True
    assert result['issuingCountry'] == 'MX'
    assert result['plateType'] == 'diplomat'


def test_normal_plate_returns_none():
    from diplomatic import detect_diplomatic_format
    assert detect_diplomatic_format('ABC1234') is None
    assert detect_diplomatic_format('FL123XY') is None
    assert detect_diplomatic_format('') is None


def test_us_mission_lookup():
    from diplomatic import lookup_us_mission
    result = lookup_us_mission('001')
    assert result is not None
    assert result['country'] == 'United Kingdom'
    assert 'latitude' in result
    assert 'longitude' in result


def test_unknown_code_returns_none():
    from diplomatic import lookup_us_mission
    assert lookup_us_mission('999') is None


def test_diplomatic_geofences():
    from diplomatic import detect_diplomatic_format, get_diplomatic_geofences
    info = detect_diplomatic_format('D001234')
    geofences = get_diplomatic_geofences(info)
    assert len(geofences) >= 1  # At least the embassy
