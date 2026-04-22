"""
embed.py
--------
Pipeline station: embed — generates vector embeddings for all place documents
and writes them to the file cache. No database writes.

Reads from:  data/cache/documents/   (one JSON per place, key: place_id)
Writes to:   data/cache/embeddings/<model-slug>/  (one JSON per place, key: place_id)

The ingest station reads from the embeddings cache to populate PlaceEmbedding rows.

Run standalone:
    python embed.py
    python embed.py --limit 10

Or as part of the pipeline (after transform, before ingest):
    python pipeline.py --steps embed
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ── Bootstrap Django ──────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent / "ferv_project"
sys.path.insert(0, str(ROOT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ferv_project.settings")

import django
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env")
django.setup()

# ── Imports (after Django setup) ──────────────────────────────────────────────
import cache
from config import CACHE_DIR, DOCUMENTS_DIR, EMBEDDINGS_DIR
from recommendation.services import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def _model_cache_dir(embedder: EmbeddingService) -> str:
    """Return the cache sub-directory string for this embedder's model."""
    slug = embedder.model_key.replace("/", "-").replace(".", "-")
    return str(Path(EMBEDDINGS_DIR) / slug)


def run(limit: int | None = None) -> None:
    """
    Generate embeddings for all documents not yet cached.
    Writes {"vector": [...], "model": "<model_name>"} per place_id.
    """
    embedder = EmbeddingService()
    model_dir = _model_cache_dir(embedder)

    doc_keys = cache.list_cached_keys(DOCUMENTS_DIR)
    if limit:
        doc_keys = set(list(doc_keys)[:limit])

    total = len(doc_keys)
    log.info(
        "embed — %d documents to process (model: %s)", total, embedder.model_key
    )

    success = 0
    skipped = 0
    failed = 0

    for place_id in doc_keys:
        if cache.key_is_cached(place_id, model_dir):
            skipped += 1
            continue

        try:
            doc = cache.load_entry(place_id, DOCUMENTS_DIR)
            text = doc.get("text", "")
            if not text:
                log.warning("Empty document for place_id: %s — skipping", place_id)
                failed += 1
                continue

            vector = embedder.embed(text)
            cache.save_entry(
                place_id,
                {"vector": vector, "model": embedder.model_key},
                model_dir,
            )
            success += 1
            log.info("[%d/%d] Embedded: %s", success + skipped, total, place_id)

        except Exception as e:
            log.error("Failed to embed %s: %s", place_id, e)
            failed += 1

    log.info(
        "embed complete — success: %d | skipped: %d | failed: %d",
        success,
        skipped,
        failed,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only embed this many documents (useful for testing)",
    )
    args = parser.parse_args()
    run(limit=args.limit)
