"""
google_api.py
-------------
Thin wrapper around the Google Places API.
No file I/O here — functions receive parameters and return data.
Callers are responsible for caching results.

Two endpoints used:
  - Nearby Search:  finds places within a radius of a coordinate
  - Place Details:  fetches rich data for a single place_id
"""

import logging
import time

import requests

from config import API_KEY, PAGINATION_DELAY

log = logging.getLogger(__name__)

NEARBY_URL  = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Fields requested from Place Details.
# Fewer fields = lower API cost. Add fields here if your embedding strategy needs them.
DETAIL_FIELDS = ",".join([
    "name",
    "place_id",
    "formatted_address",
    "geometry",
    "rating",
    "price_level",
    "opening_hours",
    "reviews",
    "types",
    "editorial_summary",
])


def search_nearby(lat: float, lng: float, place_type: str, radius: int = 1000) -> list:
    """
    Query Google Nearby Search for places of a given type near a coordinate.
    Follows pagination automatically — returns a flat list of all place stubs.

    Each stub is a dict with basic fields (name, place_id, geometry, etc.)
    but NOT full details like reviews. Use fetch_place_detail() for those.
    """
    results = []
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": place_type,
        "key": API_KEY,
    }

    while True:
        response = requests.get(NEARBY_URL, params=params)
        response.raise_for_status()
        data = response.json()

        status = data.get("status")
        if status not in ("OK", "ZERO_RESULTS"):
            log.warning("Nearby Search returned status %s for (%s,%s) %s", status, lat, lng, place_type)
            break

        results.extend(data.get("results", []))

        next_token = data.get("next_page_token")
        if not next_token:
            break

        # Google requires a short pause before the next_page_token becomes valid
        time.sleep(PAGINATION_DELAY)
        params = {"pagetoken": next_token, "key": API_KEY}

    return results


def fetch_place_detail(place_id: str) -> dict:
    """
    Fetch full details for a single place from Google Place Details API.
    Returns the 'result' dict, or an empty dict if the request fails.
    """
    params = {
        "place_id": place_id,
        "fields": DETAIL_FIELDS,
        "language": "es",   # Spanish reviews — important for Medellín data quality
        "key": API_KEY,
    }

    response = requests.get(DETAILS_URL, params=params)
    response.raise_for_status()
    data = response.json()

    status = data.get("status")
    if status != "OK":
        log.warning("Place Details returned status %s for place_id %s", status, place_id)
        return {}

    return data.get("result", {})
