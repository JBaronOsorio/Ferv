"""
ingest.py
---------
Pipeline station 6 — ingests structured place data and embedding documents
into PostgreSQL.

Reads from:
  - data/cache/structured/   → Place, PlaceTag
  - data/cache/documents/    → PlaceDocument

Re-runnable — uses update_or_create so existing records are updated, not duplicated.
Called from pipeline.py:
    python pipeline.py --steps ingest
"""

import json
import logging
import os
import sys
from pathlib import Path
from config import CACHE_DIR, STRUCTURED_DIR, DOCUMENTS_DIR, EMBEDDINGS_DIR

from places.models import Place, PlaceTag, PlaceDocument
from recommendation.models import GeminiEmbeddingVector, GeminiEmbeddingVectorLarge, OpenAIEmbeddingVector, PlaceEmbedding

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
    """

    place, created = Place.objects.update_or_create(
        place_id=data["place_id"],
        defaults={
            "name":              data.get("name", ""),
            "address":           data.get("address", ""),
            "neighborhood":      data.get("neighborhood", ""),
            "latitude":          data.get("lat"),
            "longitude":         data.get("lng"),
            "rating":            data.get("rating"),
            "price_level":       data.get("price_level"),
            "hours":             data.get("hours", []),
            "review_count":      data.get("review_count", 0),
            "editorial_summary": data.get("editorial_summary", ""),
        },
    )

    for tag_value in data.get("types", []):
        PlaceTag.objects.get_or_create(place=place, tag=tag_value)

    return created


def ingest_document(place_id: str, text: str) -> bool:
    """
    Upsert the embedding document for a place.
    The Place record must already exist — call ingest_place() first.
    Returns True if created, False if updated.
    """

    try:
        place = Place.objects.get(place_id=place_id)
    except Place.DoesNotExist:
        log.warning("Skipping document for unknown place_id: %s", place_id)
        return False

    _doc, created = PlaceDocument.objects.update_or_create(
        place=place,
        defaults={"text": text},
    )

    return created

def ingest_embedding(place_id: str, vector: list, model_name: str) -> bool:
    """
    Upsert a PlaceEmbedding for the given place using the GFK model structure.
    If a PlaceEmbedding already exists for the place, update its vector object in place.
    Returns True if created, False if updated.
    """
    from django.contrib.contenttypes.models import ContentType


    VectorClass = (
        GeminiEmbeddingVector if "gemini" in model_name.lower() and len(vector) == 768
        
        else GeminiEmbeddingVectorLarge if "gemini" in model_name.lower() and len(vector) == 3072
        
        else OpenAIEmbeddingVector
    )
    ct = ContentType.objects.get_for_model(VectorClass)

    try:
        place = Place.objects.get(place_id=place_id)
    except Place.DoesNotExist:
        log.warning("Skipping embedding for unknown place_id: %s", place_id)
        return False

    try:
        pe = PlaceEmbedding.objects.get(place=place)
        VectorClass.objects.filter(id=pe.object_id).update(
            vector=vector, model_name=model_name
        )
        return False
    except PlaceEmbedding.DoesNotExist:
        vector_obj = VectorClass.objects.create(vector=vector, model_name=model_name)
        PlaceEmbedding.objects.create(place=place, content_type=ct, object_id=vector_obj.pk)
        return True


def ingest_embeddings_from_cache() -> None:
    """
    Pass 3 of ingest_all: read all embedding cache entries and upsert PlaceEmbedding rows.
    Reads from data/cache/embeddings/<model-slug>/ directories.
    """

    embeddings_root = CACHE_DIR / EMBEDDINGS_DIR
    if not embeddings_root.exists():
        log.info("No embeddings cache found at %s — skipping.", embeddings_root)
        return

    model_dirs = [d for d in embeddings_root.iterdir() if d.is_dir()]
    if not model_dirs:
        log.info("No model subdirectories in embeddings cache — skipping.")
        return

    for model_dir in model_dirs:
        files = list(model_dir.glob("*.json"))
        log.info(
            "ingest_embeddings — %d files in %s", len(files), model_dir.name
        )
        created = updated = failed = 0
        for file_path in files:
            try:
                import json
                with open(file_path, encoding="utf-8") as f:
                    data = json.load(f)
                place_id = file_path.stem
                model_name = data.get("model", "")
                vector = data.get("vector", [])
                was_created = ingest_embedding(place_id, vector, model_name)
                if was_created:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                log.error("Failed to ingest embedding %s: %s", file_path.name, e)
                failed += 1
        log.info(
            "Embeddings (%s) — created: %d, updated: %d, failed: %d",
            model_dir.name, created, updated, failed,
        )
        
def ingest_all() -> None:
    """
    Pipeline station — ingests all structured places then all documents.
    Places are ingested first so documents can resolve their FK safely.
    Raises FileNotFoundError if either cache directory is missing.
    """

    _bootstrap_django()

    structured_path = CACHE_DIR / STRUCTURED_DIR
    documents_path  = CACHE_DIR / DOCUMENTS_DIR

    if not structured_path.exists():
        raise FileNotFoundError(
            f"Structured cache not found at {structured_path}. "
            "Run the transform station first."
        )
    if not documents_path.exists():
        raise FileNotFoundError(
            f"Documents cache not found at {documents_path}. "
            "Run the transform station first."
        )

    # ── Pass 1: places ────────────────────────────────────────────────────────
    files = list(structured_path.glob("*.json"))
    log.info("ingest_all — %s structured files", len(files))

    created = updated = failed = 0
    for file_path in files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            was_created = ingest_place(data)
            if was_created:
                created += 1
                log.debug("Created place: %s", data.get("name"))
            else:
                updated += 1
                log.debug("Updated place: %s", data.get("name"))
        except Exception as e:
            log.error("Failed to ingest place %s: %s", file_path.name, e)
            failed += 1

    log.info("Places — created: %s, updated: %s, failed: %s", created, updated, failed)

    # ── Pass 2: documents ─────────────────────────────────────────────────────
    files = list(documents_path.glob("*.json"))
    log.info("ingest_all — %s document files", len(files))

    created = updated = failed = 0
    for file_path in files:
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            place_id = file_path.stem  # filename is the place_id
            was_created = ingest_document(place_id, data["text"])
            if was_created:
                created += 1
                log.debug("Created document: %s", place_id)
            else:
                updated += 1
                log.debug("Updated document: %s", place_id)
        except Exception as e:
            log.error("Failed to ingest document %s: %s", file_path.name, e)
            failed += 1

    log.info("Documents — created: %s, updated: %s, failed: %s", created, updated, failed)

    # ── Pass 3: embeddings ────────────────────────────────────────────────────
    ingest_embeddings_from_cache()

    log.info("ingest_all complete.")

