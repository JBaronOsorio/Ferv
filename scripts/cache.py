"""
cache.py
--------
All filesystem operations for the Ferv data pipeline.
No other module should read or write files directly — go through these functions.

The cache is structured as:
    data/cache/
    ├── raw/          grid+type sweep results     key: "{lat}_{lng}_{type}"
    ├── places/       deduplicated place stubs     key: place_id
    └── details/      full Place Details response  key: place_id
"""

import json
import logging
from pathlib import Path

from config import CACHE_DIR, RAW_DIR

log = logging.getLogger(__name__)


def _dir(sub_dir: str) -> Path:
    """Resolve full path for a cache subdirectory."""
    return CACHE_DIR / sub_dir


def _path(key: str, sub_dir: str) -> Path:
    """Resolve full path for a single cache entry."""
    return _dir(sub_dir) / f"{key}.json"


def key_is_cached(key: str, sub_dir: str = RAW_DIR) -> bool:
    """Return True if this key already has a cached file."""
    return _path(key, sub_dir).exists()


def list_cached_keys(sub_dir: str = RAW_DIR) -> set:
    """
    Return the set of all cached keys in a subdirectory.
    Keys are filenames with .json stripped — they match the keys used in save/load.
    Returns an empty set if the directory doesn't exist yet.
    """
    dir_path = _dir(sub_dir)
    if not dir_path.exists():
        return set()
    return {f.stem for f in dir_path.iterdir() if f.suffix == ".json"}


def load_entry(key: str, sub_dir: str = RAW_DIR) -> dict:
    """
    Load and return a single cached entry.
    Returns an empty dict if the key doesn't exist.
    """
    path = _path(key, sub_dir)
    if not path.exists():
        log.warning("Cache miss on load: %s/%s", sub_dir, key)
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_cache(sub_dir: str = RAW_DIR) -> dict:
    """
    Load all entries in a subdirectory into a dict keyed by cache key.
    Use sparingly — prefer list_cached_keys() + load_entry() when you
    only need to iterate, to avoid loading everything into memory at once.
    """
    keys = list_cached_keys(sub_dir)
    cache = {key: load_entry(key, sub_dir) for key in keys}
    log.info("Loaded %s entries from cache/%s", len(cache), sub_dir)
    return cache


def save_entry(key: str, data: dict | list, sub_dir: str = RAW_DIR) -> None:
    """
    Save a single entry to the cache.
    Creates the subdirectory if it doesn't exist.
    Writes atomically enough for our purposes — always UTF-8.
    """
    dir_path = _dir(sub_dir)
    dir_path.mkdir(parents=True, exist_ok=True)

    path = _path(key, sub_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    log.debug("Saved cache entry: %s/%s", sub_dir, key)
