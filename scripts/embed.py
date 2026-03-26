"""
embed.py
--------
Batch embedding script — generates and stores vector embeddings
for all PlaceDocuments that don't have an embedding yet.

Run from inside the scripts/ folder:
    python embed.py

Or run only a small batch for testing:
    python embed.py --limit 10
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# ── Bootstrap Django ─────────────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent / "ferv_project"
sys.path.insert(0, str(ROOT_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ferv_project.settings")

import django
from dotenv import load_dotenv
load_dotenv(ROOT_DIR / ".env")
django.setup()

# ── Imports ───────────────────────────────────────────────────────────────────
from places.models import PlaceDocument
from recommendation.models import PlaceEmbedding
from recommendation.services import EmbeddingService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def run(limit: int = None) -> None:
    """
    Generates embeddings for all PlaceDocuments that don't
    have a PlaceEmbedding yet. Skips already embedded places.
    """
    embedder = EmbeddingService()

    # Find all documents that don't have an embedding yet
    documents = PlaceDocument.objects.filter(
        place__embedding__isnull=True
    ).select_related("place")

    if limit:
        documents = documents[:limit]

    total = documents.count()
    log.info("Found %d documents to embed.", total)

    success = 0
    failed = 0

    for doc in documents:
        try:
            vector = embedder.embed(doc.text)

            PlaceEmbedding.objects.update_or_create(
                place=doc.place,
                defaults={"vector": vector},
            )

            success += 1
            log.info("[%d/%d] Embedded: %s", success, total, doc.place.name)

        except Exception as e:
            log.error("Failed to embed %s: %s", doc.place.name, e)
            failed += 1

    log.info("Done. ✅ Success: %d | ❌ Failed: %d", success, failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only embed this many documents (useful for testing)"
    )
    args = parser.parse_args()
    run(limit=args.limit)