"""Tests for NYC data provider."""

import math
import unittest
from unittest.mock import MagicMock, patch, call


class TestBBLParsing(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    def test_bbl_to_borough_block_lot(self):
        borough, block, lot = self.provider._parse_bbl("1005430021")
        self.assertEqual(borough, "1")
        self.assertEqual(block, "00543")
        self.assertEqual(lot, "0021")

    def test_bbl_parse_brooklyn(self):
        borough, block, lot = self.provider._parse_bbl("3012340056")
        self.assertEqual(borough, "3")
        self.assertEqual(block, "01234")
        self.assertEqual(lot, "0056")


class TestHeadingFilter(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    def test_heading_filter(self):
        """Buildings behind user (opposite heading) should be filtered out."""
        user_lat = 40.7128
        user_lon = -74.0060
        heading = 0.0  # pointing north

        # Building directly north (~100m) — should pass
        north_bldg = {
            "latitude": "40.7137",
            "longitude": "-74.0060",
            "bbl": "1000010001",
        }
        # Building directly south (~100m) — should be filtered (behind user)
        south_bldg = {
            "latitude": "40.7119",
            "longitude": "-74.0060",
            "bbl": "1000010002",
        }

        candidates = [north_bldg, south_bldg]
        filtered = self.provider._filter_by_heading(
            user_lat, user_lon, heading, candidates, cone_degrees=90
        )

        bbls = [b["bbl"] for b in filtered]
        self.assertIn("1000010001", bbls)
        self.assertNotIn("1000010002", bbls)

    def test_heading_filter_east(self):
        """Buildings to the west should be filtered when heading east."""
        user_lat = 40.7128
        user_lon = -74.0060
        heading = 90.0  # pointing east

        east_bldg = {
            "latitude": "40.7128",
            "longitude": "-73.9960",  # roughly east
            "bbl": "1000010003",
        }
        west_bldg = {
            "latitude": "40.7128",
            "longitude": "-74.0160",  # roughly west
            "bbl": "1000010004",
        }

        candidates = [east_bldg, west_bldg]
        filtered = self.provider._filter_by_heading(
            user_lat, user_lon, heading, candidates, cone_degrees=90
        )

        bbls = [b["bbl"] for b in filtered]
        self.assertIn("1000010003", bbls)
        self.assertNotIn("1000010004", bbls)


class TestResolveLocation(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    @patch("nyc_data.requests.get")
    def test_resolve_location_returns_candidates(self, mock_get):
        """resolve_location should query PLUTO and return up to 3 candidates."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "bbl": "1005430021",
                "latitude": "40.7128",
                "longitude": "-74.0060",
                "address": "100 BROADWAY",
                "yearbuilt": "1900",
                "numfloors": "10",
                "bldgclass": "O5",
                "landuse": "05",
                "assesstot": "5000000",
            },
            {
                "bbl": "1005430022",
                "latitude": "40.7130",
                "longitude": "-74.0062",
                "address": "102 BROADWAY",
                "yearbuilt": "1920",
                "numfloors": "8",
                "bldgclass": "O4",
                "landuse": "05",
                "assesstot": "3000000",
            },
        ]
        mock_get.return_value = mock_response

        results = self.provider.resolve_location(
            lat=40.7128, lon=-74.0060, heading=0.0, radius_m=50
        )

        self.assertIsInstance(results, list)
        self.assertLessEqual(len(results), 3)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("64uk-42ks", call_url)


class TestGetProfile(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    @patch("nyc_data.requests.get")
    def test_get_profile_assembles_pluto_data(self, mock_get):
        """get_profile should return PLUTO record for given BBL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "bbl": "1005430021",
                "address": "100 BROADWAY",
                "yearbuilt": "1900",
                "numfloors": "10",
                "bldgclass": "O5",
                "landuse": "05",
                "assesstot": "5000000",
                "latitude": "40.7128",
                "longitude": "-74.0060",
                "ownername": "CITY OF NEW YORK",
                "lotarea": "10000",
                "bldgarea": "80000",
                "unitstotal": "0",
                "zonedist1": "C5-3",
            }
        ]
        mock_get.return_value = mock_response

        profile = self.provider.get_profile("1005430021")

        self.assertIsNotNone(profile)
        self.assertEqual(profile["bbl"], "1005430021")
        self.assertEqual(profile["address"], "100 BROADWAY")
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("64uk-42ks", call_url)


class TestGetOwnership(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    @patch("nyc_data.requests.get")
    def test_get_ownership_from_acris(self, mock_get):
        """get_ownership should query ACRIS and return ownership records."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "borough": "1",
                "block": "00543",
                "lot": "0021",
                "party_type": "1",
                "name": "ACME CORP",
                "doc_type": "DEED",
                "recorded_datetime": "2020-01-15T00:00:00.000",
            }
        ]
        mock_get.return_value = mock_response

        ownership = self.provider.get_ownership("1005430021")

        self.assertIsInstance(ownership, list)
        self.assertGreater(len(ownership), 0)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("bnx9-e6tj", call_url)


class TestGetViolations(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    @patch("nyc_data.requests.get")
    def test_get_violations_from_dob(self, mock_get):
        """get_violations should query DOB + HPD and combine results."""
        dob_response = MagicMock()
        dob_response.status_code = 200
        dob_response.json.return_value = [
            {
                "isn_dob_bis_viol": "DOB-001",
                "boro": "1",
                "block": "00543",
                "lot": "0021",
                "description": "Failure to maintain",
                "violation_category": "V*-DOB VIOLATION - DISMISSED",
                "issue_date": "2021-03-10T00:00:00.000",
            }
        ]

        hpd_response = MagicMock()
        hpd_response.status_code = 200
        hpd_response.json.return_value = [
            {
                "violationid": "HPD-002",
                "boroid": "1",
                "block": "00543",
                "lot": "0021",
                "class": "B",
                "novdescription": "Lack of heat",
                "inspectiondate": "2021-04-01T00:00:00.000",
            }
        ]

        mock_get.side_effect = [dob_response, hpd_response]

        violations = self.provider.get_violations("1005430021")

        self.assertIsInstance(violations, dict)
        self.assertIn("dob", violations)
        self.assertIn("hpd", violations)
        self.assertEqual(len(violations["dob"]), 1)
        self.assertEqual(len(violations["hpd"]), 1)
        self.assertEqual(mock_get.call_count, 2)

        urls_called = [c[0][0] for c in mock_get.call_args_list]
        self.assertTrue(any("3h2n-5cm9" in u for u in urls_called))
        self.assertTrue(any("wvxf-dwi5" in u for u in urls_called))


class TestGetPermits(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    @patch("nyc_data.requests.get")
    def test_get_permits_from_dob(self, mock_get):
        """get_permits should query DOB permits and return records."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "house__": "100",
                "street_name": "BROADWAY",
                "borough": "MANHATTAN",
                "block": "00543",
                "lot": "0021",
                "job__": "123456789",
                "job_type": "A1",
                "work_type": "OT",
                "filing_status": "ISSUED",
                "filing_date": "2022-06-01T00:00:00.000",
            }
        ]
        mock_get.return_value = mock_response

        permits = self.provider.get_permits("1005430021")

        self.assertIsInstance(permits, list)
        self.assertGreater(len(permits), 0)
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        self.assertIn("ipu4-2vta", call_url)


class TestHaversineAndBearing(unittest.TestCase):
    def setUp(self):
        from nyc_data import NYCDataProvider
        self.provider = NYCDataProvider(
            geoclient_app_id="test_id",
            geoclient_app_key="test_key",
            socrata_token="test_token",
        )

    def test_haversine_same_point(self):
        dist = self.provider._haversine(40.7128, -74.0060, 40.7128, -74.0060)
        self.assertAlmostEqual(dist, 0.0, places=3)

    def test_haversine_known_distance(self):
        # NYC to roughly 1km north
        dist = self.provider._haversine(40.7128, -74.0060, 40.7218, -74.0060)
        self.assertAlmostEqual(dist, 1000.0, delta=50.0)

    def test_bearing_north(self):
        # Point directly north
        bearing = self.provider._bearing(40.7128, -74.0060, 40.7218, -74.0060)
        self.assertAlmostEqual(bearing, 0.0, delta=1.0)

    def test_bearing_east(self):
        # Point roughly east
        bearing = self.provider._bearing(40.7128, -74.0060, 40.7128, -73.9960)
        self.assertAlmostEqual(bearing, 90.0, delta=2.0)


if __name__ == "__main__":
    unittest.main()
