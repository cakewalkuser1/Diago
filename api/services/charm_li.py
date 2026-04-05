"""
charm.li (Operation CHARM) integration — on-demand service manual links.
We do not host the database; we build URLs so the user can open the right
manual in the browser. Covers 1982–2013. See https://charm.li/about.html
"""

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

CHARM_BASE = "https://charm.li"

# NHTSA / app make names → charm.li URL path slug (exact as on charm.li index)
_MAKE_TO_SLUG: dict[str, str] = {
    "acura": "Acura",
    "audi": "Audi",
    "bmw": "BMW",
    "buick": "Buick",
    "cadillac": "Cadillac",
    "chevrolet": "Chevrolet",
    "chevy": "Chevrolet",
    "chrysler": "Chrysler",
    "daewoo": "Daewoo",
    "daihatsu": "Daihatsu",
    "dodge": "Dodge and Ram",
    "ram": "Dodge and Ram",
    "eagle": "Eagle",
    "fiat": "Fiat",
    "ford": "Ford",
    "freightliner": "Freightliner",
    "geo": "Geo",
    "gmc": "GMC",
    "honda": "Honda",
    "hummer": "Hummer",
    "hyundai": "Hyundai",
    "infiniti": "Infiniti",
    "isuzu": "Isuzu",
    "jaguar": "Jaguar",
    "jeep": "Jeep",
    "kia": "Kia",
    "land rover": "Land Rover",
    "lexus": "Lexus",
    "lincoln": "Lincoln",
    "mazda": "Mazda",
    "mercedes-benz": "Mercedes Benz",
    "mercedes": "Mercedes Benz",
    "mercury": "Mercury",
    "mini": "Mini",
    "mini cooper": "Mini",
    "mitsubishi": "Mitsubishi",
    "nissan": "Nissan-Datsun",
    "datsun": "Nissan-Datsun",
    "oldsmobile": "Oldsmobile",
    "peugeot": "Peugeot",
    "plymouth": "Plymouth",
    "pontiac": "Pontiac",
    "porsche": "Porsche",
    "renault": "Renault",
    "saab": "Saab",
    "saturn": "Saturn",
    "scion": "Scion",
    "smart": "Smart",
    "srt": "SRT",
    "subaru": "Subaru",
    "suzuki": "Suzuki",
    "toyota": "Toyota",
    "ud": "UD",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "volvo": "Volvo",
    "workhorse": "Workhorse",
    "yugo": "Yugo",
}


def get_manual_url(make: str, model_year: int | None) -> str | None:
    """
    Return the charm.li URL for a make and optional model year.
    If the make is not in our mapping, returns None.
    charm.li covers 1982–2013; we still return the URL for other years so the user can try.
    """
    if not (make or "").strip():
        return None
    key = make.strip().lower()
    slug = _MAKE_TO_SLUG.get(key)
    if not slug:
        return None
    path = quote(slug)
    if model_year is not None and 1982 <= model_year <= 2013:
        path = f"{path}/{model_year}"
    return f"{CHARM_BASE}/{path}"
