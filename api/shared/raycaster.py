"""3D ray casting for building identification using PLUTO geometry.

Shoots a ray from the user's 3D position (GPS + altitude) in their look
direction (heading + pitch) and finds which building volume the ray hits
first.  Tall buildings correctly occlude shorter ones behind them.

Height data is sourced in priority order:
  1. NYC 3D Building Footprints (u9wf-3gbt) — measured roof heights in feet,
     matched to PLUTO candidates by BIN or nearest centroid.
  2. PLUTO numfloors × floor-height estimation (fallback).
"""

import math
from typing import Dict, List, Optional, Tuple

# Approximate metres-per-degree at NYC latitude (~40.7°N)
_M_PER_DEG_LAT = 111_320.0

# Default floor height in metres
_FLOOR_HEIGHT_M = 3.5

# Maximum horizontal distance (m) to match a 3D footprint centroid to a PLUTO
# candidate when BIN lookup fails.
_MAX_HEIGHT_MATCH_M = 30.0


def _m_per_deg_lon(lat: float) -> float:
    """Metres per degree of longitude at a given latitude."""
    return 111_320.0 * math.cos(math.radians(lat))


def _to_local(ref_lat: float, ref_lon: float,
              target_lat: float, target_lon: float) -> Tuple[float, float]:
    """Convert lat/lon to local (east, north) metres relative to ref point."""
    east = (target_lon - ref_lon) * _m_per_deg_lon(ref_lat)
    north = (target_lat - ref_lat) * _M_PER_DEG_LAT
    return east, north


def _ray_aabb_intersect(
    origin: Tuple[float, float, float],
    direction: Tuple[float, float, float],
    box_min: Tuple[float, float, float],
    box_max: Tuple[float, float, float],
) -> Optional[float]:
    """Ray-AABB intersection using the slab method.

    Returns the distance along the ray to the nearest intersection, or None
    if the ray misses the box.  Handles the ray originating inside the box
    (returns 0.0 in that case).
    """
    tmin = -math.inf
    tmax = math.inf

    for i in range(3):
        if abs(direction[i]) < 1e-12:
            # Ray is parallel to this slab
            if origin[i] < box_min[i] or origin[i] > box_max[i]:
                return None
        else:
            inv_d = 1.0 / direction[i]
            t1 = (box_min[i] - origin[i]) * inv_d
            t2 = (box_max[i] - origin[i]) * inv_d
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None

    # tmin < 0 means the ray starts inside the box
    if tmin < 0:
        if tmax < 0:
            return None  # box is entirely behind the ray
        return 0.0

    return tmin


def _flat_distance(east: float, north: float) -> float:
    return math.sqrt(east * east + north * north)


def _estimate_dimension(candidate: Dict, key: str, fallback_key: str = 'lotarea') -> float:
    """Get a building dimension in metres, falling back to sqrt(lotarea)."""
    val = candidate.get(key)
    if val:
        try:
            v = float(val)
            if v > 0:
                # PLUTO dimensions are in feet — convert to metres
                return v * 0.3048
        except (TypeError, ValueError):
            pass
    # Fallback: sqrt(lotarea) — lotarea is in sq ft
    lot = candidate.get(fallback_key)
    if lot:
        try:
            l = float(lot)
            if l > 0:
                return math.sqrt(l) * 0.3048
        except (TypeError, ValueError):
            pass
    return 10.0  # absolute fallback: 10m


def _resolve_height(
    candidate: Dict,
    blat: float,
    blon: float,
    height_by_bin: Dict[str, Dict],
    height_points: List[Dict],
) -> Tuple[float, float]:
    """Return (height_m, ground_elev_m) for a PLUTO candidate.

    Resolution order:
      1. Match by BIN from the 3D footprint index (exact, O(1)).
      2. Match by nearest centroid within _MAX_HEIGHT_MATCH_M (spatial fallback).
      3. Fall back to PLUTO numfloors × _FLOOR_HEIGHT_M estimation.

    Args:
        candidate:      PLUTO building dict.
        blat, blon:     Building centroid coordinates.
        height_by_bin:  Dict of BIN → 3D height record.
        height_points:  Full list of 3D height records for nearest-match scan.

    Returns:
        Tuple of (height_m, ground_elev_m) both in metres.
    """
    h_rec: Optional[Dict] = None

    # 1. BIN exact match
    bin_val = str(candidate.get("bin", "")).strip()
    if bin_val and bin_val in height_by_bin:
        h_rec = height_by_bin[bin_val]

    # 2. Nearest centroid within threshold
    if h_rec is None and height_points:
        best_dist = _MAX_HEIGHT_MATCH_M
        for hp in height_points:
            try:
                hp_lat = float(hp["latitude"])
                hp_lon = float(hp["longitude"])
            except (TypeError, ValueError, KeyError):
                continue
            he, hn = _to_local(blat, blon, hp_lat, hp_lon)
            d = _flat_distance(he, hn)
            if d < best_dist:
                best_dist = d
                h_rec = hp

    if h_rec is not None:
        try:
            height_m = float(h_rec.get("height_roof_m", 0) or 0)
            ground_m = float(h_rec.get("ground_elev_m", 0) or 0)
            if height_m > 0:
                return height_m, ground_m
        except (TypeError, ValueError):
            pass

    # 3. PLUTO fallback: numfloors × floor height
    try:
        floors = float(candidate.get("numfloors", 0) or 0)
    except (TypeError, ValueError):
        floors = 0
    height_m = max(floors * _FLOOR_HEIGHT_M, _FLOOR_HEIGHT_M)

    try:
        ground_m = float(candidate.get("groundelev", 0) or 0) * 0.3048  # ft→m
    except (TypeError, ValueError):
        ground_m = 0.0

    return height_m, ground_m


class BuildingRayCaster:
    """Cast a 3D ray from the user's position to identify which building
    they are looking at, accounting for occlusion by taller buildings."""

    def cast(
        self,
        user_lat: float,
        user_lon: float,
        user_alt: float,
        heading: float,
        pitch: float,
        candidates: List[Dict],
        building_heights: Optional[List[Dict]] = None,
    ) -> List[Dict]:
        """Cast a ray and return candidates sorted by intersection distance.

        Args:
            user_lat, user_lon: GPS position.
            user_alt: altitude in metres above ground (0 = ground level).
            heading: compass heading in degrees (0=N, 90=E, 180=S, 270=W).
            pitch: camera pitch in degrees (0=horizon, negative=down, positive=up).
            candidates: list of PLUTO building dicts.
            building_heights: optional list of 3D footprint dicts from
                NYCDataProvider.get_building_heights().  Each dict must have
                ``bin``, ``height_roof_m``, ``ground_elev_m``, ``latitude``,
                ``longitude``.  When provided, measured roof heights take
                priority over PLUTO floor-count estimates.

        Returns:
            candidates sorted by ray intersection distance (closest hit first).
            Buildings not hit by the ray are appended at the end, sorted by
            flat distance.
        """
        if not candidates:
            return candidates

        # Build an index of 3D height data for fast lookup.
        # Prefer BIN match; fall back to nearest-centroid within _MAX_HEIGHT_MATCH_M.
        height_by_bin: Dict[str, Dict] = {}
        height_points: List[Dict] = []
        if building_heights:
            for h in building_heights:
                bin_key = str(h.get("bin", "")).strip()
                if bin_key:
                    height_by_bin[bin_key] = h
                height_points.append(h)

        # Build ray origin in local 3D coords (east, north, up)
        origin = (0.0, 0.0, user_alt)

        # Convert heading + pitch to 3D direction vector
        # heading: 0=N (+north), 90=E (+east), 180=S, 270=W
        heading_rad = math.radians(heading)
        pitch_rad = math.radians(pitch)

        cos_pitch = math.cos(pitch_rad)
        direction = (
            math.sin(heading_rad) * cos_pitch,   # east
            math.cos(heading_rad) * cos_pitch,    # north
            math.sin(pitch_rad),                  # up
        )

        hits: List[Tuple[float, int, Dict]] = []
        misses: List[Tuple[float, int, Dict]] = []

        for idx, cand in enumerate(candidates):
            # Building centre in local coords
            try:
                blat = float(cand.get('latitude', 0))
                blon = float(cand.get('longitude', 0))
            except (TypeError, ValueError):
                misses.append((9999.0, idx, cand))
                continue

            east, north = _to_local(user_lat, user_lon, blat, blon)

            # Building dimensions from PLUTO
            half_w = _estimate_dimension(cand, 'bldgfront') / 2.0
            half_d = _estimate_dimension(cand, 'bldgdepth') / 2.0

            # ----------------------------------------------------------------
            # Height resolution: prefer 3D footprint data over PLUTO estimate.
            # ----------------------------------------------------------------
            height_m, ground_elev_m = _resolve_height(
                cand, blat, blon, height_by_bin, height_points
            )

            box_min = (east - half_w, north - half_d, ground_elev_m)
            box_max = (east + half_w, north + half_d, ground_elev_m + height_m)

            t = _ray_aabb_intersect(origin, direction, box_min, box_max)
            if t is not None:
                hits.append((t, idx, cand))
            else:
                dist = _flat_distance(east, north)
                misses.append((dist, idx, cand))

        # Sort hits by distance along ray, misses by flat distance
        hits.sort(key=lambda x: x[0])
        misses.sort(key=lambda x: x[0])

        return [c for _, _, c in hits] + [c for _, _, c in misses]
