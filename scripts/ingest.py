"""
ingest.py
---------
Loads place data from data/cache/structures/ into the PostgreSQL database.
Run this script from inside the scripts/ folder:

    python ingest.py

Make sure your .env file is configured and PostgreSQL is running before executing.
"""

import os
import sys
import json
import logging
from pathlib import Path

# ── 1. Bootstrap Django ──────────────────────────────────────────────────────
# We need to tell Django where to find settings.py before importing any models.
# This script lives in scripts/, so we go one level up to reach ferv_project/.

ROOT_DIR = Path(__file__).resolve().parent.parent / "ferv_project"
sys.path.insert(0, str(ROOT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ferv_project.settings")

import django
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")
django.setup()

# ── 2. Now we can safely import Django models ────────────────────────────────
from places.models import Place, PlaceTag

# ── 3. Configure logging ─────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ── 4. Define where the structures folder is ─────────────────────────────────
STRUCTURES_DIR = Path(__file__).resolve().parent / "data" / "cache" / "structures"


def ingest_place(data: dict) -> None:
    """
    Takes a single structure JSON object and saves it to the database.
    Creates the Place if it doesn't exist, updates it if it does.
    Also creates PlaceTag entries for each type.
    """

    # -- Save or update the Place --
    place, created = Place.objects.update_or_create(
        place_id=data["place_id"],  # this is the unique identifier
        defaults={
            "name": data.get("name", ""),
            "address": data.get("address", ""),
            "neighborhood": data.get("neighborhood", ""),
            "latitude": data.get("lat"),
            "longitude": data.get("lng"),
            "rating": data.get("rating"),
            "price_level": data.get("price_level"),
            "hours": data.get("hours", []),
            "review_count": data.get("review_count", 0),
            "editorial_summary": data.get("editorial_summary", ""),
        },
    )

    action = "Created" if created else "Updated"
    log.info("%s place: %s", action, place.name)

    # -- Save tags (types) --
    # Each entry in "types" becomes a PlaceTag row
    for tag_value in data.get("types", []):
        PlaceTag.objects.get_or_create(place=place, tag=tag_value)


def run():
    """
    Main entry point. Reads all JSON files from structures/ and ingests them.
    """
    if not STRUCTURES_DIR.exists():
        log.error("Structures directory not found: %s", STRUCTURES_DIR)
        log.error("Make sure the pipeline has been run and cache is populated.")
        sys.exit(1)

    files = list(STRUCTURES_DIR.glob("*.json"))
    log.info("Found %d structure files to ingest.", len(files))

    success = 0
    failed = 0

    for file_path in files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            ingest_place(data)
            success += 1
        except Exception as e:
            log.error("Failed to ingest %s: %s", file_path.name, e)
            failed += 1

    log.info("Ingestion complete. ✅ Success: %d | ❌ Failed: %d", success, failed)


if __name__ == "__main__":
    run()