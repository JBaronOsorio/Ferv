"""
ingest.py
---------
Pipeline station 6 — ingests structured place data into PostgreSQL.

Reads from data/cache/structured/, writes to the database via Django ORM.
Re-runnable — uses update_or_create so existing records are updated, not duplicated.

Should not be run directly. Called from pipeline.py as a station:
    python pipeline.py --steps ingest
"""

import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def _bootstrap_django() -> None:
    """
    Initialize Django before any models can be imported.
    Called once at the start of ingest_all() — not at module level,
    so importing this file doesn't trigger Django setup as a side effect.
    """
    root_dir = Path(__file__).resolve().parent.parent / "ferv_project"
    sys.path.insert(0, str(root_dir))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ferv_project.settings")

    import django
    from dotenv import load_dotenv
    load_dotenv(root_dir / ".env")
    django.setup()


def ingest_place(data: dict) -> bool:
    """
    Upsert a single structured place dict into the database.
    Returns True if created, False if updated.
    Raises on unexpected errors — caller handles them.
    """
    from places.models import Place, PlaceTag  # import here — Django must be set up first

    place, created = Place.objects.update_or_create(
        place_id=data["place_id"],
        defaults={
            "name":             data.get("name", ""),
            "address":          data.get("address", ""),
            "neighborhood":     data.get("neighborhood", ""),
            "latitude":         data.get("lat"),
            "longitude":        data.get("lng"),
            "rating":           data.get("rating"),
            "price_level":      data.get("price_level"),
            "hours":            data.get("hours", []),
            "review_count":     data.get("review_count", 0),
            "editorial_summary": data.get("editorial_summary", ""),
        },
    )

    # Sync tags — get_or_create means re-running won't duplicate them
    for tag_value in data.get("types", []):
        PlaceTag.objects.get_or_create(place=place, tag=tag_value)

    return created


def ingest_all() -> None:
    """
    Pipeline station — reads all structured JSON files and ingests them.
    Raises FileNotFoundError if the structured directory doesn't exist,
    so pipeline.py can handle it cleanly.
    """
    from config import CACHE_DIR, STRUCTURED_DIR  # local import — avoids circular issues

    _bootstrap_django()

    structured_path = CACHE_DIR / STRUCTURED_DIR
    if not structured_path.exists():
        raise FileNotFoundError(
            f"Structured cache not found at {structured_path}. "
            "Run the transform station first."
        )

    files = list(structured_path.glob("*.json"))
    log.info("ingest_all — %s structured files to process", len(files))

    created = 0
    updated = 0
    failed = 0

    for file_path in files:
        try:
            import json
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            was_created = ingest_place(data)
            if was_created:
                created += 1
                log.debug("Created: %s", data.get("name"))
            else:
                updated += 1
                log.debug("Updated: %s", data.get("name"))

        except Exception as e:
            log.error("Failed to ingest %s: %s", file_path.name, e)
            failed += 1

    log.info(
        "ingest_all complete — created: %s, updated: %s, failed: %s",
        created, updated, failed
    )