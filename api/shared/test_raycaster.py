"""Tests for 3D building ray caster."""

import math
import unittest

from raycaster import BuildingRayCaster, _ray_aabb_intersect, _to_local, _M_PER_DEG_LAT


def _make_building(lat, lon, numfloors=10, bldgfront=20, bldgdepth=20, groundelev=0):
    """Helper: create a minimal PLUTO-like building dict.
    bldgfront/bldgdepth in feet, numfloors as integer."""
    return {
        'latitude': str(lat),
        'longitude': str(lon),
        'numfloors': str(numfloors),
        'bldgfront': str(bldgfront),  # feet
        'bldgdepth': str(bldgdepth),  # feet
        'lotarea': str(bldgfront * bldgdepth),
        'groundelev': str(groundelev),
        'bbl': '1000000001',
        'address': 'TEST',
    }


class TestRayAABBIntersect(unittest.TestCase):
    """Low-level slab-method tests."""

    def test_hit_box_in_front(self):
        origin = (0, 0, 0)
        direction = (0, 1, 0)  # looking north
        box_min = (-1, 5, -1)
        box_max = (1, 7, 1)
        t = _ray_aabb_intersect(origin, direction, box_min, box_max)
        self.assertIsNotNone(t)
        self.assertAlmostEqual(t, 5.0, places=5)

    def test_miss_box_to_side(self):
        origin = (0, 0, 0)
        direction = (0, 1, 0)
        box_min = (10, 5, -1)
        box_max = (12, 7, 1)
        t = _ray_aabb_intersect(origin, direction, box_min, box_max)
        self.assertIsNone(t)

    def test_ray_inside_box(self):
        origin = (0, 0, 0)
        direction = (0, 1, 0)
        box_min = (-1, -1, -1)
        box_max = (1, 1, 1)
        t = _ray_aabb_intersect(origin, direction, box_min, box_max)
        self.assertEqual(t, 0.0)

    def test_box_behind_ray(self):
        origin = (0, 0, 0)
        direction = (0, 1, 0)
        box_min = (-1, -7, -1)
        box_max = (1, -5, 1)
        t = _ray_aabb_intersect(origin, direction, box_min, box_max)
        self.assertIsNone(t)


class TestBuildingRayCaster(unittest.TestCase):
    """Integration tests with PLUTO-like building dicts."""

    def setUp(self):
        self.caster = BuildingRayCaster()
        # Reference point: Times Square-ish
        self.user_lat = 40.758
        self.user_lon = -73.9855

    def _offset_lat(self, metres_north):
        return self.user_lat + metres_north / _M_PER_DEG_LAT

    def _offset_lon(self, metres_east):
        import math as _m
        return self.user_lon + metres_east / (111320 * _m.cos(_m.radians(self.user_lat)))

    def test_tall_building_occludes_short_behind(self):
        """A tall building 50m away should occlude a short building 100m away."""
        tall = _make_building(
            self._offset_lat(50), self.user_lon,
            numfloors=30, bldgfront=60, bldgdepth=60,
        )
        short = _make_building(
            self._offset_lat(100), self.user_lon,
            numfloors=3, bldgfront=60, bldgdepth=60,
        )
        # Looking north, horizontal
        result = self.caster.cast(
            self.user_lat, self.user_lon, 2.0, heading=0, pitch=0,
            candidates=[short, tall],
        )
        # Tall building should come first
        self.assertEqual(result[0]['latitude'], tall['latitude'])

    def test_building_to_side_not_hit(self):
        """A building 90 degrees to the right should not be hit when looking north."""
        ahead = _make_building(
            self._offset_lat(50), self.user_lon,
            numfloors=10, bldgfront=40, bldgdepth=40,
        )
        side = _make_building(
            self.user_lat, self._offset_lon(50),
            numfloors=10, bldgfront=40, bldgdepth=40,
        )
        result = self.caster.cast(
            self.user_lat, self.user_lon, 2.0, heading=0, pitch=0,
            candidates=[side, ahead],
        )
        # Building ahead should be first (hit), side building goes to misses
        self.assertEqual(result[0]['latitude'], ahead['latitude'])

    def test_pitch_up_hits_tall_far_building(self):
        """Looking up at 30 degrees should hit a tall building further away."""
        short_near = _make_building(
            self._offset_lat(30), self.user_lon,
            numfloors=3, bldgfront=40, bldgdepth=40,
        )
        tall_far = _make_building(
            self._offset_lat(150), self.user_lon,
            numfloors=50, bldgfront=80, bldgdepth=80,
        )
        # Pitch up: the ray goes over the short building and hits the tall one
        result = self.caster.cast(
            self.user_lat, self.user_lon, 2.0, heading=0, pitch=30,
            candidates=[short_near, tall_far],
        )
        # Tall far building should be first hit
        self.assertEqual(result[0]['latitude'], tall_far['latitude'])

    def test_pitch_down_hits_nearby_short_building(self):
        """Looking down should hit the nearby short building, not the far tall one."""
        short_near = _make_building(
            self._offset_lat(20), self.user_lon,
            numfloors=2, bldgfront=40, bldgdepth=40,
        )
        tall_far = _make_building(
            self._offset_lat(200), self.user_lon,
            numfloors=50, bldgfront=80, bldgdepth=80,
        )
        # From 15m altitude looking down — ray hits nearby rooftop
        result = self.caster.cast(
            self.user_lat, self.user_lon, 15.0, heading=0, pitch=-20,
            candidates=[tall_far, short_near],
        )
        self.assertEqual(result[0]['latitude'], short_near['latitude'])

    def test_fallback_miss_sorted_by_distance(self):
        """Buildings the ray misses should be sorted by distance."""
        far = _make_building(
            self.user_lat, self._offset_lon(200),
            numfloors=5, bldgfront=20, bldgdepth=20,
        )
        near = _make_building(
            self.user_lat, self._offset_lon(50),
            numfloors=5, bldgfront=20, bldgdepth=20,
        )
        # Looking north; both buildings are to the east — both miss
        result = self.caster.cast(
            self.user_lat, self.user_lon, 2.0, heading=0, pitch=0,
            candidates=[far, near],
        )
        # Near should come before far in the miss-sorted list
        self.assertEqual(result[0]['longitude'], near['longitude'])
        self.assertEqual(result[1]['longitude'], far['longitude'])

    def test_empty_candidates(self):
        result = self.caster.cast(self.user_lat, self.user_lon, 2.0, 0, 0, [])
        self.assertEqual(result, [])


if __name__ == '__main__':
    unittest.main()
