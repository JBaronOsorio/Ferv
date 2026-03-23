# transform.py

NOISE_TYPES = {
    "establishment", "point_of_interest", 
    "food", "premise", "geocode"
}

PRICE_LABELS = {
    0: "gratuito",
    1: "económico",
    2: "moderado", 
    3: "caro",
    4: "muy caro"
}

def extract_neighborhood(address: str) -> str:
    """
    'Cra. 43A, El Poblado, Medellín, Antioquia' → 'El Poblado'
    Google's address format puts neighborhood as the first
    comma-separated segment after the street. Fragile — worth
    cleaning manually later if quality is low.
    """
    parts = [p.strip() for p in address.split(",")]
    return parts[1] if len(parts) > 1 else ""


def clean_types(types: list) -> list:
    return [t for t in types if t not in NOISE_TYPES]


def clean_reviews(reviews: list) -> list:
    """Filter out reviews with empty text."""
    return [r for r in reviews if r.get("text", "").strip()]

def is_qualified(detail: dict) -> tuple[bool, str]:
    has_summary = bool(
        detail.get("editorial_summary", {}).get("overview", "").strip()
    )
    text_reviews = clean_reviews(detail.get("reviews", []))

    if len(text_reviews) >= 2 or has_summary:
        return True, "ok"
    
    if len(text_reviews) == 1:
        return False, "only_one_review"
    
    return False, "no_reviews_no_summary"

def to_structured(detail: dict) -> dict:
    address = detail.get("formatted_address", "")
    location = detail.get("geometry", {}).get("location", {})
    hours_data = detail.get("opening_hours", {})
    reviews = clean_reviews(detail.get("reviews", []))

    return {
        "place_id":     detail.get("place_id"),
        "name":         detail.get("name"),
        "address":      address,
        "neighborhood": extract_neighborhood(address),
        "lat":          location.get("lat"),
        "lng":          location.get("lng"),
        "rating":       detail.get("rating"),
        "price_level":  detail.get("price_level"),  # None if missing
        "types":        clean_types(detail.get("types", [])),
        "hours":        hours_data.get("weekday_text", []),
        "review_count": len(reviews),
    }


def to_document(structured: dict, reviews: list) -> str:
    """
    Build the natural language paragraph for embedding.
    Takes structured (already cleaned) + raw reviews list.
    """
    name = structured["name"]
    neighborhood = structured["neighborhood"]
    types_str = " y ".join(structured["types"]) if structured["types"] else "lugar"
    rating = structured["rating"] or "sin calificación"
    price = PRICE_LABELS.get(structured["price_level"], "precio desconocido")

    hours = structured["hours"]
    hours_str = hours[0] if hours else "horario no disponible"
    # Check if all days share the same schedule — common case
    if len(set(h.split(": ")[1] for h in hours)) == 1:
        hours_str = f"todos los días {hours[0].split(': ')[1]}"

    clean = clean_reviews(reviews)
    reviews_str = "\n".join(f'- "{r["text"]}"' for r in clean)

    return f"""{name} es un {types_str} ubicado en {neighborhood}, Medellín.\nCalificación: {rating} estrellas. Precio: {price}.\nHorario: {hours_str}.\nReseñas de visitantes: \n{reviews_str}""".strip()