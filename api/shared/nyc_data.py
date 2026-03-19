"""NYC data provider for Argus building intelligence.

Queries NYC public APIs (PLUTO, ACRIS, DOB, HPD, LPC, DOF) via the
Socrata open data platform. All data is keyed by BBL (Borough/Block/Lot).
"""

import math
import os
from typing import Any, Dict, List, Optional, Tuple

import requests

# Socrata open data base URL
SOCRATA_BASE = "https://data.cityofnewyork.us/resource"

# NYC Geoclient v2 (address → BBL resolution)
GEOCLIENT_BASE = "https://api.nyc.gov/geoclient/v2"

# Socrata dataset IDs
DATASETS = {
    "PLUTO": "64uk-42ks",
    "ACRIS": "bnx9-e6tj",
    "DOB_VIOLATIONS": "3h2n-5cm9",
    "DOB_PERMITS": "ipu4-2vta",
    "HPD_VIOLATIONS": "wvxf-dwi5",
    "LPC": "s2zq-q7et",
    "DOF": "8y4t-faws",
}


class NYCDataProvider:
    """Fetches building data from NYC public APIs.

    All geographic queries use the Socrata SoQL API. BBL is the canonical
    building identifier throughout — a 10-digit string encoding borough (1),
    block (5), and lot (4).
    """

    def __init__(
        self,
        geoclient_app_id: Optional[str] = None,
        geoclient_app_key: Optional[str] = None,
        socrata_token: Optional[str] = None,
    ):
        self.geoclient_app_id = geoclient_app_id or os.environ.get(
            "GEOCLIENT_APP_ID", ""
        )
        self.geoclient_app_key = geoclient_app_key or os.environ.get(
            "GEOCLIENT_APP_KEY", ""
        )
        self.socrata_token = socrata_token or os.environ.get("SOCRATA_TOKEN", "")
        self._geoclient_headers = {
            "Ocp-Apim-Subscription-Key": self.geoclient_app_key,
        }

    # ------------------------------------------------------------------
    # Geoclient v2
    # ------------------------------------------------------------------

    def geoclient_search(self, query: str) -> Optional[Dict]:
        """Free-text location search via Geoclient v2.

        Accepts addresses, BBLs, BINs, intersections, or place names.
        Returns the first successful geocoded result with BBL.
        """
        if not self.geoclient_app_key:
            return None
        try:
            resp = requests.get(
                f"{GEOCLIENT_BASE}/search",
                params={"input": query},
                headers=self._geoclient_headers,
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            results = data.get("results", [])
            for r in results:
                response = r.get("response", {})
                bbl = response.get("bbl", "")
                if bbl and len(bbl) >= 10:
                    return {
                        "bbl": bbl[:10],
                        "address": response.get("firstStreetNameNormalized", ""),
                        "houseNumber": response.get("houseNumber", ""),
                        "borough": response.get("firstBoroughName", ""),
                        "zipCode": response.get("zipCode", ""),
                        "latitude": response.get("latitude"),
                        "longitude": response.get("longitude"),
                        "bin": response.get("buildingIdentificationNumber", ""),
                    }
        except (requests.RequestException, ValueError, KeyError):
            pass
        return None

    def geoclient_address(self, house_number: str, street: str,
                          borough: str = None, zip_code: str = None) -> Optional[Dict]:
        """Structured address lookup via Geoclient v2."""
        if not self.geoclient_app_key:
            return None
        params = {"houseNumber": house_number, "street": street}
        if borough:
            params["borough"] = borough
        if zip_code:
            params["zip"] = zip_code

        try:
            resp = requests.get(
                f"{GEOCLIENT_BASE}/address",
                params=params,
                headers=self._geoclient_headers,
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("address", {})
            bbl = data.get("bbl", "")
            if bbl:
                return {
                    "bbl": bbl[:10],
                    "address": f"{house_number} {data.get('firstStreetNameNormalized', street)}",
                    "borough": data.get("firstBoroughName", ""),
                    "zipCode": data.get("zipCode", ""),
                    "latitude": data.get("latitude"),
                    "longitude": data.get("longitude"),
                    "bin": data.get("buildingIdentificationNumber", ""),
                }
        except (requests.RequestException, ValueError, KeyError):
            pass
        return None

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def resolve_location(
        self,
        lat: float,
        lon: float,
        heading: float,
        radius_m: float = 50,
        cone_degrees: float = 90,
    ) -> List[Dict[str, Any]]:
        """Find candidate buildings near (lat, lon) within heading cone.

        Queries PLUTO by bounding box derived from radius_m, then filters
        by heading cone to return only buildings the user is facing.
        Returns up to 3 candidates sorted by distance.

        Args:
            lat: User latitude in decimal degrees.
            lon: User longitude in decimal degrees.
            heading: User compass heading in degrees (0 = north).
            radius_m: Bounding box half-side in meters (default 50).
            cone_degrees: Full width of the heading acceptance cone in
                degrees (default 90). Narrow cones improve precision at
                longer distances (e.g. 15° at 800 m, 90° at 30 m).

        Returns:
            List of up to 3 PLUTO records (dicts) sorted by distance.
        """
        # Convert radius_m to rough degree offsets
        # Use 1.5x radius for bounding box so cone filter has enough candidates
        box_radius = radius_m * 1.5
        lat_offset = box_radius / 111_320.0
        lon_offset = box_radius / (111_320.0 * math.cos(math.radians(lat)))

        min_lat = lat - lat_offset
        max_lat = lat + lat_offset
        min_lon = lon - lon_offset
        max_lon = lon + lon_offset

        where = (
            f"latitude >= '{min_lat}' AND latitude <= '{max_lat}' "
            f"AND longitude >= '{min_lon}' AND longitude <= '{max_lon}'"
        )

        url = f"{SOCRATA_BASE}/{DATASETS['PLUTO']}.json"
        query_limit = 200 if radius_m > 200 else 50
        params = {"$where": where, "$limit": query_limit}
        if self.socrata_token:
            params["$$app_token"] = self.socrata_token

        response = requests.get(url, params=params)
        response.raise_for_status()
        candidates = response.json()

        # Filter by heading cone
        filtered = self._filter_by_heading(lat, lon, heading, candidates, cone_degrees=cone_degrees)

        # At long range, sort by heading alignment (closest to center of aim)
        # At short range, sort by distance (closest building)
        is_far = cone_degrees <= 20
        for b in filtered:
            try:
                blat = float(b.get("latitude", lat))
                blon = float(b.get("longitude", lon))
                b["_distance"] = self._haversine(lat, lon, blat, blon)
                bearing = self._bearing(lat, lon, blat, blon)
                b["_angle_diff"] = abs((bearing - heading + 180) % 360 - 180)
            except (TypeError, ValueError):
                b["_distance"] = float("inf")
                b["_angle_diff"] = 180.0

        if is_far:
            # Far mode: prioritize heading alignment, break ties by distance
            filtered.sort(key=lambda b: (b.get("_angle_diff", 180), b.get("_distance", float("inf"))))
        else:
            # Near mode: prioritize distance
            filtered.sort(key=lambda b: b.get("_distance", float("inf")))

        # Return more candidates at far range (harder to nail the exact one)
        max_results = 5 if is_far else 3
        return filtered[:max_results]

    def get_profile(self, bbl: str) -> Optional[Dict[str, Any]]:
        """Fetch PLUTO record for a building by BBL.

        Args:
            bbl: 10-digit BBL string (e.g. "1005430021").

        Returns:
            PLUTO record dict or None if not found.
        """
        url = f"{SOCRATA_BASE}/{DATASETS['PLUTO']}.json"
        params = {"$where": f"bbl='{bbl.strip()}'", "$limit": 1}
        if self.socrata_token:
            params["$$app_token"] = self.socrata_token

        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json()
        return results[0] if results else None

    def get_ownership(self, bbl: str) -> List[Dict[str, Any]]:
        """Fetch ownership/deed records from ACRIS for a BBL.

        Uses ACRIS Legals (8h5j-fqxa) to find document_ids by BBL,
        then joins to ACRIS Master (bnx9-e6tj) for deed details.
        ACRIS legals uses non-zero-padded block/lot numbers.
        """
        borough, block, lot = self._parse_bbl(bbl)
        # ACRIS uses non-padded block/lot
        block_stripped = str(int(block))
        lot_stripped = str(int(lot))

        # Step 1: Get document IDs from legals table
        legals_url = f"{SOCRATA_BASE}/8h5j-fqxa.json"
        legals_params = {
            "$where": f"borough='{borough}' AND block='{block_stripped}' AND lot='{lot_stripped}'",
            "$limit": 10,
            "$order": "good_through_date DESC",
        }
        if self.socrata_token:
            legals_params["$$app_token"] = self.socrata_token

        legals_resp = requests.get(legals_url, params=legals_params, timeout=5)
        legals_resp.raise_for_status()
        legals = legals_resp.json()
        if not legals:
            return []

        # Step 2: Get deed details from master table
        doc_ids = list(set(r.get("document_id", "") for r in legals if r.get("document_id")))[:5]
        if not doc_ids:
            return []

        doc_id_filter = " OR ".join(f"document_id='{d}'" for d in doc_ids)
        master_url = f"{SOCRATA_BASE}/{DATASETS['ACRIS']}.json"
        master_params = {
            "$where": doc_id_filter,
            "$order": "recorded_datetime DESC",
            "$limit": 10,
        }
        if self.socrata_token:
            master_params["$$app_token"] = self.socrata_token

        master_resp = requests.get(master_url, params=master_params, timeout=5)
        master_resp.raise_for_status()

        # Step 3: Get party names
        parties_url = f"{SOCRATA_BASE}/636b-3b5g.json"
        parties_params = {
            "$where": doc_id_filter,
            "$limit": 20,
        }
        if self.socrata_token:
            parties_params["$$app_token"] = self.socrata_token

        parties_resp = requests.get(parties_url, params=parties_params, timeout=5)
        parties_resp.raise_for_status()

        # Merge master + parties
        master_map = {r["document_id"]: r for r in master_resp.json()}
        results = []
        for party in parties_resp.json():
            doc_id = party.get("document_id", "")
            master = master_map.get(doc_id, {})
            results.append({
                "name": party.get("name", ""),
                "party_type": party.get("party_type", ""),
                "doc_type": master.get("doc_type", ""),
                "document_date": master.get("document_date", ""),
                "document_amt": master.get("document_amt", ""),
                "recorded_datetime": master.get("recorded_datetime", ""),
            })

        return results

    def get_violations(self, bbl: str) -> Dict[str, List[Dict[str, Any]]]:
        """Fetch active violations from DOB and HPD for a BBL.

        Makes two API calls (DOB violations + HPD violations) and returns
        combined results keyed by source.

        Args:
            bbl: 10-digit BBL string.

        Returns:
            Dict with keys "dob" and "hpd", each containing a list of records.
        """
        borough, block, lot = self._parse_bbl(bbl)

        # DOB violations
        dob_url = f"{SOCRATA_BASE}/{DATASETS['DOB_VIOLATIONS']}.json"
        dob_params = {
            "$where": (
                f"boro='{borough}' AND block='{block}' AND lot='{lot}'"
            ),
            "$limit": 200,
        }
        if self.socrata_token:
            dob_params["$$app_token"] = self.socrata_token

        dob_response = requests.get(dob_url, params=dob_params)
        dob_response.raise_for_status()
        dob_violations = dob_response.json()

        # HPD violations
        hpd_url = f"{SOCRATA_BASE}/{DATASETS['HPD_VIOLATIONS']}.json"
        hpd_params = {
            "$where": (
                f"boroid='{borough}' AND block='{block}' AND lot='{lot}'"
            ),
            "$limit": 200,
        }
        if self.socrata_token:
            hpd_params["$$app_token"] = self.socrata_token

        hpd_response = requests.get(hpd_url, params=hpd_params)
        hpd_response.raise_for_status()
        hpd_violations = hpd_response.json()

        return {"dob": dob_violations, "hpd": hpd_violations}

    def get_permits(self, bbl: str) -> List[Dict[str, Any]]:
        """Fetch DOB permit records for a BBL.

        Args:
            bbl: 10-digit BBL string.

        Returns:
            List of DOB permit records.
        """
        borough, block, lot = self._parse_bbl(bbl)
        url = f"{SOCRATA_BASE}/{DATASETS['DOB_PERMITS']}.json"
        params = {
            "$where": f"block='{block}' AND lot='{lot}'",
            "$order": "filing_date DESC",
            "$limit": 100,
        }
        if self.socrata_token:
            params["$$app_token"] = self.socrata_token

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_landmarks(self, bbl: str) -> List[Dict[str, Any]]:
        """Fetch LPC landmark designations for a BBL.

        Args:
            bbl: 10-digit BBL string.

        Returns:
            List of LPC landmark records.
        """
        url = f"{SOCRATA_BASE}/{DATASETS['LPC']}.json"
        params = {"$where": f"bbl='{bbl.strip()}'", "$limit": 10}
        if self.socrata_token:
            params["$$app_token"] = self.socrata_token

        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_assessed_value(self, bbl: str) -> Optional[Dict[str, Any]]:
        """Fetch DOF assessed value for a BBL.

        The DOF dataset (8y4t-faws) uses "parid" as the parcel identifier,
        which corresponds to the BBL padded to 10 digits.

        Args:
            bbl: 10-digit BBL string.

        Returns:
            DOF assessment record dict or None if not found.
        """
        url = f"{SOCRATA_BASE}/{DATASETS['DOF']}.json"
        params = {"$where": f"parid='{bbl.strip()}'", "$limit": 1}
        if self.socrata_token:
            params["$$app_token"] = self.socrata_token

        response = requests.get(url, params=params)
        response.raise_for_status()
        results = response.json()
        return results[0] if results else None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_bbl(self, bbl: str) -> Tuple[str, str, str]:
        """Split a 10-digit BBL into (borough, block, lot) components.

        BBL format: B BBBBB LLLL
          - 1 digit  borough (1–5)
          - 5 digits block
          - 4 digits lot

        Args:
            bbl: 10-digit BBL string (e.g. "1005430021").

        Returns:
            Tuple of (borough, block, lot) as zero-padded strings.

        Example:
            >>> _parse_bbl("1005430021")
            ("1", "00543", "0021")
        """
        bbl = bbl.strip().zfill(10)
        borough = bbl[0]
        block = bbl[1:6]
        lot = bbl[6:10]
        return borough, block, lot

    def _filter_by_heading(
        self,
        user_lat: float,
        user_lon: float,
        heading: float,
        candidates: List[Dict[str, Any]],
        cone_degrees: float = 90,
    ) -> List[Dict[str, Any]]:
        """Filter candidates to those within the heading cone.

        Only buildings whose bearing from the user falls within
        ±(cone_degrees/2) of the user's heading are returned.

        Args:
            user_lat: User latitude.
            user_lon: User longitude.
            heading: User compass heading in degrees (0 = north, clockwise).
            candidates: List of building dicts with "latitude"/"longitude".
            cone_degrees: Full width of the acceptance cone in degrees.

        Returns:
            Filtered list of buildings within the cone.
        """
        half_cone = cone_degrees / 2.0
        result = []

        for building in candidates:
            try:
                blat = float(building.get("latitude", 0))
                blon = float(building.get("longitude", 0))
            except (TypeError, ValueError):
                continue

            bearing = self._bearing(user_lat, user_lon, blat, blon)
            # Compute angular difference in [0, 180]
            diff = abs((bearing - heading + 180) % 360 - 180)
            if diff <= half_cone:
                result.append(building)

        return result

    def _bearing(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Compute the initial compass bearing from point 1 to point 2.

        Args:
            lat1, lon1: Source coordinates in decimal degrees.
            lat2, lon2: Target coordinates in decimal degrees.

        Returns:
            Bearing in degrees [0, 360), where 0 is north, clockwise.
        """
        lat1_r = math.radians(lat1)
        lat2_r = math.radians(lat2)
        dlon_r = math.radians(lon2 - lon1)

        x = math.sin(dlon_r) * math.cos(lat2_r)
        y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(
            lat2_r
        ) * math.cos(dlon_r)

        bearing = math.degrees(math.atan2(x, y))
        return (bearing + 360) % 360

    def _haversine(
        self,
        lat1: float,
        lon1: float,
        lat2: float,
        lon2: float,
    ) -> float:
        """Compute great-circle distance between two points.

        Args:
            lat1, lon1: First point in decimal degrees.
            lat2, lon2: Second point in decimal degrees.

        Returns:
            Distance in meters.
        """
        R = 6_371_000.0  # Earth radius in metres

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
