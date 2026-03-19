import pytest
from models import (
    building_pk, profile_sk, story_sk, owner_sk, violation_sk,
    permit_sk, image_sk, scan_pk, scan_sk, geo_pk, heat_pk,
    geohash6, analytics_pk
)

def test_building_pk():
    assert building_pk("1-00543-0021") == "BLDG#1-00543-0021"

def test_building_pk_strips_whitespace():
    assert building_pk(" 1-00543-0021 ") == "BLDG#1-00543-0021"

def test_profile_sk():
    assert profile_sk() == "PROFILE"

def test_story_sk():
    assert story_sk() == "STORY"

def test_owner_sk():
    assert owner_sk("2024-03-15") == "OWNER#2024-03-15"

def test_violation_sk():
    assert violation_sk("DOB-123456") == "VIOLATION#DOB-123456"

def test_permit_sk():
    assert permit_sk("M00123456") == "PERMIT#M00123456"

def test_image_sk():
    assert image_sk("2026-03-19T14:30:00") == "IMAGE#2026-03-19T14:30:00"

def test_scan_pk():
    assert scan_pk("user123", "2026-03-19T14:30:00") == "SCAN#user123#2026-03-19T14:30:00"

def test_scan_sk():
    assert scan_sk() == "SCAN"

def test_geo_pk():
    pk = geo_pk(40.7128, -74.0060)
    assert pk.startswith("GEO#dr5r")

def test_heat_pk():
    assert heat_pk("2026-03-19") == "HEAT#2026-03-19"

def test_analytics_pk():
    assert analytics_pk("weekly") == "ANALYTICS#weekly"

def test_geohash6_precision():
    h = geohash6(40.7128, -74.0060)
    assert len(h) == 6
    assert h.startswith("dr5r")
