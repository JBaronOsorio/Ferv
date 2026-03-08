#!/usr/bin/env python3
"""
pipeline.py
-----------
Ferv data collection pipeline — orchestrates the three stations:

  1. collect_all()     Grid sweep → raw cache
  2. deduplicate()     Raw cache → unique place stubs
  3. collect_details() Place stubs → full place details

Each station is independently re-runnable. Cached entries are never re-fetched.

Usage:
    python pipeline.py            # runs all three stations
    python pipeline.py --steps collect details   # run just collection and detail fetching
    python pipeline.py --steps deduplicate          # run just deduplication
    python pipeline.py --steps deduplicate --debug     # run just deduplication with debug logging
    python pipeline.py --debug    # verbose logging
"""

import argparse
import itertools
import logging
import sys
import time

import cache
import google_api
from config import (
    ACTIVE_BOUNDS,
    DETAILS_DIR,
    PLACE_TYPES,
    PLACES_DIR,
    RAW_DIR,
    REQUEST_DELAY,
    STEP,
)

log = logging.getLogger(__name__)


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler("pipeline.log"),  # uncomment to write a log file
        ],
    )


# ── Station 1: Grid sweep ─────────────────────────────────────────────────────

def generate_grid() -> list:
    """Generate lat/lng grid points covering the active bounding box."""
    b = ACTIVE_BOUNDS
    lats = [b["lat_min"] + i * STEP for i in range(int((b["lat_max"] - b["lat_min"]) / STEP))]
    lngs = [b["lng_min"] + i * STEP for i in range(int((b["lng_max"] - b["lng_min"]) / STEP))]
    return list(itertools.product(lats, lngs))


def collect_all(place_types: list = PLACE_TYPES) -> None:
    """
    Sweep the grid for each place type and cache raw results.
    Skips any grid+type combination already in the raw cache.
    """
    grid = generate_grid()
    log.info("Grid: %s points × %s types = %s requests max", len(grid), len(place_types), len(grid) * len(place_types))

    new = 0
    skipped = 0

    for lat, lng in grid:
        for place_type in place_types:
            key = f"{round(lat, 4)}_{round(lng, 4)}_{place_type}"

            if cache.key_is_cached(key, RAW_DIR):
                log.debug("Cache hit (raw): %s", key)
                skipped += 1
                continue

            log.debug("Fetching: %s", key)
            results = google_api.search_nearby(lat, lng, place_type)
            cache.save_entry(key, results, RAW_DIR)
            new += 1

            time.sleep(REQUEST_DELAY)

    log.info("collect_all complete — new: %s, skipped: %s", new, skipped)


# ── Station 2: Deduplication ──────────────────────────────────────────────────

def deduplicate() -> None:
    """
    Read all raw cache entries, extract unique places by place_id,
    and write each unique stub to the places cache.
    """
    raw = cache.load_cache(RAW_DIR)
    new = 0
    skipped = 0

    for _key, results in raw.items():
        for place in results:
            place_id = place.get("place_id")
            if not place_id:
                continue

            if cache.key_is_cached(place_id, PLACES_DIR):
                log.debug("Cache hit (places): %s", place_id)
                skipped += 1
                continue

            cache.save_entry(place_id, place, PLACES_DIR)
            log.debug("Saved unique place: %s", place_id)
            new += 1

    log.info("deduplicate complete — new: %s, skipped: %s, total: %s", new, skipped, new + skipped)


# ── Station 3: Detail fetching ────────────────────────────────────────────────

def collect_details() -> None:
    """
    For each unique place in the places cache, fetch full details from Google
    and write them to the details cache. Skips already-fetched places.
    """
    place_ids = cache.list_cached_keys(PLACES_DIR)
    log.info("collect_details — %s places to process", len(place_ids))

    new = 0
    skipped = 0

    for place_id in place_ids:
        if cache.key_is_cached(place_id, DETAILS_DIR):
            log.debug("Cache hit (details): %s", place_id)
            skipped += 1
            continue

        log.debug("Fetching details: %s", place_id)
        detail = google_api.fetch_place_detail(place_id)

        if detail:
            cache.save_entry(place_id, detail, DETAILS_DIR)
            new += 1
        else:
            log.warning("Empty detail response for place_id: %s", place_id)

        time.sleep(REQUEST_DELAY)

    log.info("collect_details complete — new: %s, skipped: %s, total: %s", new, skipped, new + skipped)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    p.add_argument(
        "--steps",
        nargs="+",
        choices=["collect", "deduplicate", "details"],
        default=["collect", "deduplicate", "details"],
        help="Which pipeline steps to run (default: all)"
    )
    return p.parse_args()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    setup_logging(args.debug)
    log.debug("Args: %s", args)

    if "collect" in args.steps:
        log.info("── Station 1: Grid sweep ──")
        collect_all()

    if "deduplicate" in args.steps:
        log.info("── Station 2: Deduplication ──")
        deduplicate()

    if "details" in args.steps:
        log.info("── Station 3: Detail fetching ──")
        collect_details()

    log.info("Pipeline complete.")


if __name__ == "__main__":
    main()
