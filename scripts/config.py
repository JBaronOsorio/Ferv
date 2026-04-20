"""
config.py
---------
Central configuration for the Ferv data pipeline.
All magic numbers, paths, and environment variables live here.
Other modules import from this file — never the other way around.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────

API_KEY = os.environ["GOOGLE_API_KEY"]

# ── Bounding boxes ────────────────────────────────────────────────────────────

# El Poblado (for testing)
BOUNDS_EL_POBLADO = {
    "lat_min": 6.18, "lat_max": 6.22,
    "lng_min": -75.58, "lng_max": -75.54,
}

# Full Medellín
BOUNDS_MEDELLIN = {
    "lat_min": 6.15, "lat_max": 6.35,
    "lng_min": -75.65, "lng_max": -75.52,
}

# Test with single point (for debugging)
BOUNDS_TEST = {
    "lat_min": 6.20, "lat_max": 6.22,
    "lng_min": -75.57, "lng_max": -75.55,
}

# Active bounds — swap this to BOUNDS_MEDELLIN for full city collection
ACTIVE_BOUNDS = BOUNDS_TEST

STEP = 0.009  # ~1km in degrees at this latitude

# ── Place types ───────────────────────────────────────────────────────────────

PLACE_TYPES = [
    "art_gallery",
    "bar",
    "museum",
    "cafe",
    "night_club",
    "park",
    "restaurant",
]

# ── Cache paths ───────────────────────────────────────────────────────────────

CACHE_DIR   = Path("data/cache")
RAW_DIR     = "raw"
PLACES_DIR  = "places"
DETAILS_DIR = "details"
STRUCTURED_DIR = "structured"
DOCUMENTS_DIR = "documents"
QUALIFIED_DIR = "qualified"
REJECTED_DIR = "rejected"
EMBEDDINGS_DIR = "embeddings"

# ── HTTP ──────────────────────────────────────────────────────────────────────

PAGINATION_DELAY = 2.0   # seconds — Google requires this between paginated requests
REQUEST_DELAY    = 0.5   # seconds — polite delay between successive API calls
