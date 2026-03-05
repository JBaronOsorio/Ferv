#!/usr/bin/env python3
"""
script_name.py
--------------
What this script does in one sentence.

Usage:
    python script_name.py --input data.csv --output result.json
"""

import argparse
import logging
import sys
from pathlib import Path
import itertools
import requests
import time
import json
import os

# ── Config ────────────────────────────────────────────────────────────────────
# Put all your "magic numbers", file paths, and toggles here so future-you
# doesn't have to hunt through the code.

INPUT_FILE  = Path("data.csv")
OUTPUT_FILE = Path("result.json")
DEBUG       = False  # flip to True, or let --debug flag handle it

# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)-8s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            # logging.FileHandler("script.log"),  # uncomment to also write a log file
        ],
    )

log = logging.getLogger(__name__)

# ── Core logic ────────────────────────────────────────────────────────────────

# Medellín's approximate bounding box
LAT_MIN, LAT_MAX = 6.15, 6.35
LNG_MIN, LNG_MAX = -75.65, -75.52

STEP = 0.009  # ~1km in degrees at this latitude

def generate_grid():
    lats = [LAT_MIN + i * STEP 
            for i in range(int((LAT_MAX - LAT_MIN) / STEP))]
    lngs = [LNG_MIN + i * STEP 
            for i in range(int((LNG_MAX - LNG_MIN) / STEP))]
    return list(itertools.product(lats, lngs))

log.debug("Grid points: %s", len(generate_grid()))


API_KEY = "AIzaSyBmdpOhdJgaed6Wjua4uYc0vFTzWcF50DQ"

def search_nearby(lat, lng, place_type, radius=1000):
    """Returns a flat list of place stubs for one grid point."""
    results = []
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": place_type,
        "key": API_KEY
    }
    
    while True:
        response = requests.get(url, params=params).json()
        results.extend(response.get("results", []))
        
        # Follow pagination if it exists
        next_token = response.get("next_page_token")
        if not next_token:
            break
        
        time.sleep(2)  # Google requires a short delay before using the token
        params = {"pagetoken": next_token, "key": API_KEY}
    
    return results

CACHE_FILE = "data/raw_cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}

def save_cache(cache):
    os.makedirs("data", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def collect_all(place_types):
    cache = load_cache()
    grid = generate_grid()
    
    for lat, lng in grid:
        for place_type in place_types:
            key = f"{round(lat,4)}_{round(lng,4)}_{place_type}"
            
            if key in cache:
                print(f"Cache hit: {key}")
                continue  # Skip — already have this one
            
            print(f"Fetching: {key}")
            results = search_nearby(lat, lng, place_type)
            cache[key] = results
            save_cache(cache)  # Save after every successful fetch
            
            time.sleep(0.5)  # Respect rate limits

def deduplicate(cache):
    seen_ids = {}
    for key, results in cache.items():
        for place in results:
            pid = place["place_id"]
            if pid not in seen_ids:
                seen_ids[pid] = place
    return seen_ids  # dict of {place_id: stub}

def fetch_place_detail(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,place_id,formatted_address,geometry,rating,"
                  "price_level,opening_hours,reviews,types,editorial_summary",
        "language": "es",  # Get Spanish reviews — important for Medellín
        "key": API_KEY
    }
    response = requests.get(url, params=params).json()
    return response.get("result", {})

# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input",  type=Path, default=INPUT_FILE)
    p.add_argument("--output", type=Path, default=OUTPUT_FILE)
    p.add_argument("--debug",  action="store_true", default=DEBUG)
    return p.parse_args()

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()
    setup_logging(args.debug)
    log.debug("Args: %s", args)
    #result = search_nearby(6.20, -75.56, "bar")
    #save_cache({"test": result})
    cache = load_cache()
    seen_ids = deduplicate(cache)
    print(f"Results: {len(seen_ids)}")
    fetched_details = {
        pid: fetch_place_detail(pid) 
        for pid in seen_ids.keys()
    }
    print(f"Fetched details for {len(fetched_details)} places")
    

if __name__ == "__main__":
    main()