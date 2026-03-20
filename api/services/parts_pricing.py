"""
Real parts pricing API stubs.
AutoZone, NAPA, O'Reilly integrations.
Replace MOCK_RETAILERS in dispatch when API keys are configured.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PartRetailer:
    """Part availability at a retailer."""
    retailer_id: str
    retailer_name: str
    store_id: str
    part_number: str
    description: str
    price_cents: int
    in_stock: bool
    distance_mi: float


def get_autozone_parts(
    part_name: str,
    zip_code: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> list[PartRetailer]:
    """
    Get part availability and pricing from AutoZone.
    Stub: returns mock data. Configure AUTOZONE_API_KEY for real integration.
    """
    return [
        PartRetailer("az1", "AutoZone", "store_az_1", "BP-12345", part_name, 8999, True, 2.1),
    ]


def get_napa_parts(
    part_name: str,
    zip_code: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> list[PartRetailer]:
    """
    Get part availability from NAPA.
    Stub: returns mock data. Configure NAPA_API_KEY for real integration.
    """
    return [
        PartRetailer("napa1", "NAPA", "store_napa_1", "NAP-001", part_name, 9499, True, 3.0),
    ]


def get_oreilly_parts(
    part_name: str,
    zip_code: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> list[PartRetailer]:
    """
    Get part availability from O'Reilly.
    Stub: returns mock data. Configure OREILLY_API_KEY for real integration.
    """
    return [
        PartRetailer("oreilly1", "O'Reilly", "store_oreilly_1", "OR-001", part_name, 8499, True, 2.5),
    ]


def get_parts_from_all_retailers(
    part_name: str,
    zip_code: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> list[dict]:
    """
    Aggregate parts from all configured retailers.
    Returns list of {id, name, distance_mi, store_id, price_cents} for dispatch.
    """
    results = []
    for fn in [get_autozone_parts, get_napa_parts, get_oreilly_parts]:
        try:
            parts = fn(part_name, zip_code, lat, lng)
            for p in parts:
                results.append({
                    "id": p.retailer_id,
                    "name": p.retailer_name,
                    "distance_mi": p.distance_mi,
                    "store_id": p.store_id,
                    "price_cents": p.price_cents,
                })
        except Exception as e:
            logger.warning("Parts lookup failed for %s: %s", fn.__name__, e)
    return results
