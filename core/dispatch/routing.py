"""
ETA and routing service for mechanic dispatch.
Uses haversine distance + average speed as fallback.
Can be extended with OSRM or Mapbox when configured.
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Average urban driving speed (mph) for ETA estimate when no routing API
DEFAULT_AVG_SPEED_MPH = 25.0


@dataclass
class RouteResult:
    """Route distance and ETA."""
    distance_mi: float
    duration_min: float
    eta_min: float  # alias for duration_min
    source: str  # "haversine" | "osrm" | "mapbox"


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance in miles between two points (WGS84)."""
    R = 3959  # Earth radius in miles
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_route_eta(
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    avg_speed_mph: float = DEFAULT_AVG_SPEED_MPH,
) -> RouteResult:
    """
    Get route distance and ETA.
    Uses haversine distance; duration = distance / avg_speed.
    Override with OSRM/Mapbox when API keys are configured.
    """
    distance_mi = haversine_mi(from_lat, from_lon, to_lat, to_lon)
    duration_min = (distance_mi / avg_speed_mph) * 60 if avg_speed_mph > 0 else 0
    return RouteResult(
        distance_mi=distance_mi,
        duration_min=duration_min,
        eta_min=duration_min,
        source="haversine",
    )
