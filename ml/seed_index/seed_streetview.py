"""Seed the building image index from Google Street View Static API.

For each Manhattan landmark fetched from the NYC PLUTO dataset (via Socrata),
this script captures 2-4 photos at different headings, uploads them to S3,
generates CLIP embeddings via SageMaker, and stores indexed records in DynamoDB.

Usage:
    python seed_streetview.py --api-key YOUR_GOOGLE_KEY [options]

Options:
    --limit INT         Max number of buildings to process (default: 100)
    --dry-run           Fetch PLUTO data and log actions without writing to AWS
    --api-key STR       Google Street View Static API key (required unless --dry-run)
    --bucket STR        S3 bucket for image storage (default: argus-index)
    --table STR         DynamoDB table name (default: ArgusTable)
    --endpoint STR      SageMaker endpoint name for CLIP embeddings (default: argus-clip)
    --headings STR      Comma-separated headings in degrees (default: 0,90,180,270)
    --region STR        AWS region (default: us-east-1)
"""

import argparse
import io
import json
import logging
import sys
import time
from datetime import datetime, timezone

import boto3
import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SOCRATA_URL = (
    "https://data.cityofnewyork.us/resource/64uk-42ks.json"
    "?$where=borough='MN'&$limit={limit}&$select=bbl,latitude,longitude,address"
)
STREETVIEW_URL = (
    "https://maps.googleapis.com/maps/api/streetview"
    "?location={lat},{lon}&heading={heading}&size=640x640&fov=90&pitch=10&key={key}"
)
MIN_IMAGE_BYTES = 5 * 1024  # 5 KB — Street View placeholder images are smaller


# ---------------------------------------------------------------------------
# PLUTO / Socrata
# ---------------------------------------------------------------------------
def fetch_pluto_landmarks(limit: int) -> list[dict]:
    """Query NYC PLUTO via Socrata for Manhattan buildings with coordinates.

    Returns a list of dicts with keys: bbl, lat, lon, address.
    """
    url = SOCRATA_URL.format(limit=limit)
    log.info("Fetching up to %d buildings from PLUTO (Socrata)…", limit)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    raw = resp.json()

    buildings = []
    skipped = 0
    for row in raw:
        try:
            bbl = str(row["bbl"]).strip()
            lat = float(row["latitude"])
            lon = float(row["longitude"])
            address = row.get("address", "")
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue
        if lat == 0.0 or lon == 0.0:
            skipped += 1
            continue
        buildings.append({"bbl": bbl, "lat": lat, "lon": lon, "address": address})

    log.info("Retrieved %d buildings (%d skipped due to missing/invalid data)", len(buildings), skipped)
    return buildings


# ---------------------------------------------------------------------------
# Street View image fetch
# ---------------------------------------------------------------------------
def fetch_streetview_image(lat: float, lon: float, heading: int, api_key: str) -> bytes | None:
    """Fetch a Street View image for the given coordinates and heading.

    Returns raw image bytes, or None if the image is a placeholder (< MIN_IMAGE_BYTES).
    """
    url = STREETVIEW_URL.format(lat=lat, lon=lon, heading=heading, key=api_key)
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.warning("Street View request failed (lat=%s, lon=%s, heading=%s): %s", lat, lon, heading, exc)
        return None

    data = resp.content
    if len(data) < MIN_IMAGE_BYTES:
        log.debug(
            "Skipping placeholder image (lat=%s, lon=%s, heading=%s, size=%d bytes)",
            lat, lon, heading, len(data),
        )
        return None
    return data


# ---------------------------------------------------------------------------
# S3 upload
# ---------------------------------------------------------------------------
def upload_to_s3(s3_client, bucket: str, key: str, image_bytes: bytes) -> str:
    """Upload image bytes to S3 and return the S3 key."""
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=image_bytes,
        ContentType="image/jpeg",
    )
    return key


# ---------------------------------------------------------------------------
# SageMaker CLIP embedding
# ---------------------------------------------------------------------------
def get_clip_embedding(sagemaker_runtime, endpoint_name: str, image_bytes: bytes) -> list[float]:
    """Invoke the CLIP SageMaker endpoint and return the 512-dim embedding as a list of floats."""
    resp = sagemaker_runtime.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType="image/jpeg",
        Body=image_bytes,
    )
    result = json.loads(resp["Body"].read().decode("utf-8"))
    return result["embedding"]


# ---------------------------------------------------------------------------
# DynamoDB write
# ---------------------------------------------------------------------------
def put_building_image(
    table,
    bbl: str,
    heading: int,
    s3_key: str,
    embedding: list[float],
) -> None:
    """Write a building image index record to DynamoDB.

    Schema:
        PK  = BLDG#{bbl}
        SK  = IMAGE#seed-{heading}
    """
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(
        Item={
            "PK": f"BLDG#{bbl}",
            "SK": f"IMAGE#seed-{heading}",
            "s3Key": s3_key,
            "embedding": json.dumps(embedding),
            "source": "streetview",
            "heading": heading,
            "capturedAt": now,
        }
    )


# ---------------------------------------------------------------------------
# Per-building processing
# ---------------------------------------------------------------------------
def process_building(
    building: dict,
    headings: list[int],
    api_key: str,
    bucket: str,
    s3_client,
    sagemaker_runtime,
    endpoint_name: str,
    table,
    dry_run: bool,
) -> dict:
    """Fetch Street View images for one building and index them.

    Returns a summary dict with counts of attempted / stored / skipped images.
    """
    bbl = building["bbl"]
    lat = building["lat"]
    lon = building["lon"]
    address = building.get("address", "")

    attempted = 0
    stored = 0
    skipped = 0

    for heading in headings:
        attempted += 1
        log.debug("  BBL=%s heading=%d address=%s", bbl, heading, address)

        if dry_run:
            log.info("[dry-run] Would fetch heading=%d for BBL=%s (%s)", heading, bbl, address)
            skipped += 1
            continue

        image_bytes = fetch_streetview_image(lat, lon, heading, api_key)
        if image_bytes is None:
            skipped += 1
            continue

        s3_key = f"buildings/{bbl}/streetview_{heading}.jpg"

        try:
            upload_to_s3(s3_client, bucket, s3_key, image_bytes)
        except Exception as exc:
            log.warning("S3 upload failed for BBL=%s heading=%d: %s", bbl, heading, exc)
            skipped += 1
            continue

        try:
            embedding = get_clip_embedding(sagemaker_runtime, endpoint_name, image_bytes)
        except Exception as exc:
            log.warning("CLIP embedding failed for BBL=%s heading=%d: %s", bbl, heading, exc)
            skipped += 1
            continue

        try:
            put_building_image(table, bbl, heading, s3_key, embedding)
        except Exception as exc:
            log.warning("DynamoDB write failed for BBL=%s heading=%d: %s", bbl, heading, exc)
            skipped += 1
            continue

        stored += 1
        log.debug("  Stored BBL=%s heading=%d → s3://%s/%s", bbl, heading, bucket, s3_key)

    return {"attempted": attempted, "stored": stored, "skipped": skipped}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed building image index from Google Street View."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Max number of buildings to process (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch PLUTO data and log without writing to AWS",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Google Street View Static API key",
    )
    parser.add_argument(
        "--bucket",
        default="argus-index",
        help="S3 bucket for image storage (default: argus-index)",
    )
    parser.add_argument(
        "--table",
        default="ArgusTable",
        help="DynamoDB table name (default: ArgusTable)",
    )
    parser.add_argument(
        "--endpoint",
        default="argus-clip",
        help="SageMaker endpoint name for CLIP embeddings (default: argus-clip)",
    )
    parser.add_argument(
        "--headings",
        default="0,90,180,270",
        help="Comma-separated headings in degrees (default: 0,90,180,270)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    headings = [int(h.strip()) for h in args.headings.split(",") if h.strip()]
    if not headings:
        log.error("--headings must contain at least one integer value")
        return 1

    if not args.dry_run and not args.api_key:
        log.error("--api-key is required unless --dry-run is specified")
        return 1

    log.info(
        "Starting Street View seeding | limit=%d dry_run=%s bucket=%s table=%s endpoint=%s headings=%s",
        args.limit, args.dry_run, args.bucket, args.table, args.endpoint, headings,
    )

    # Fetch buildings from PLUTO
    try:
        buildings = fetch_pluto_landmarks(args.limit)
    except requests.RequestException as exc:
        log.error("Failed to fetch PLUTO data: %s", exc)
        return 1

    if not buildings:
        log.warning("No buildings returned from PLUTO — nothing to do")
        return 0

    # AWS clients (skip in dry-run to avoid credential requirements)
    table = None
    s3_client = None
    sagemaker_runtime = None

    if not args.dry_run:
        dynamodb = boto3.resource("dynamodb", region_name=args.region)
        table = dynamodb.Table(args.table)
        s3_client = boto3.client("s3", region_name=args.region)
        sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=args.region)

    # Process each building
    total_attempted = 0
    total_stored = 0
    total_skipped = 0
    processed_buildings = 0

    start_time = time.monotonic()

    for idx, building in enumerate(buildings, start=1):
        bbl = building["bbl"]
        address = building.get("address", "")
        log.info(
            "[%d/%d] Processing BBL=%s address=%s",
            idx, len(buildings), bbl, address,
        )

        summary = process_building(
            building=building,
            headings=headings,
            api_key=args.api_key,
            bucket=args.bucket,
            s3_client=s3_client,
            sagemaker_runtime=sagemaker_runtime,
            endpoint_name=args.endpoint,
            table=table,
            dry_run=args.dry_run,
        )

        total_attempted += summary["attempted"]
        total_stored += summary["stored"]
        total_skipped += summary["skipped"]
        processed_buildings += 1

    elapsed = time.monotonic() - start_time
    log.info(
        "Seeding complete | buildings=%d images_attempted=%d stored=%d skipped=%d elapsed=%.1fs",
        processed_buildings, total_attempted, total_stored, total_skipped, elapsed,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
