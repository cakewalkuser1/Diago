"""
MOTOR DaaS integration stub.
Provides labor times, parts, DTCs, service procedures for upfront pricing.
Replace with real MOTOR API when MOTOR_API_KEY is configured.
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LaborTime:
    """Labor time for a repair operation."""
    operation: str
    hours: float
    description: str


@dataclass
class PartInfo:
    """Part information from MOTOR."""
    part_number: str
    description: str
    price_cents: int
    quantity: int = 1


@dataclass
class DTCInfo:
    """DTC (Diagnostic Trouble Code) info."""
    code: str
    description: str
    system: str
    repair_operations: list[str]


def get_labor_times(
    year: int,
    make: str,
    model: str,
    operation: str,
) -> list[LaborTime]:
    """
    Get labor times for a repair operation.
    Stub: returns mock data. Replace with MOTOR API when configured.
    """
    # Stub labor times (typical ranges)
    stub_ops = {
        "brake_pad": LaborTime("Brake pad replacement", 1.5, "Front or rear brake pads"),
        "oil_change": LaborTime("Oil and filter change", 0.5, "Engine oil and filter"),
        "battery": LaborTime("Battery replacement", 0.25, "12V battery"),
        "spark_plug": LaborTime("Spark plug replacement", 1.0, "All cylinders"),
        "alternator": LaborTime("Alternator replacement", 2.0, "Alternator R&R"),
        "wheel_bearing": LaborTime("Wheel bearing replacement", 2.5, "Hub assembly"),
    }
    key = operation.lower().replace(" ", "_")[:20]
    for k, v in stub_ops.items():
        if k in key or key in k:
            return [v]
    return [LaborTime(operation, 1.0, "Estimated labor")]


def get_parts_for_operation(
    year: int,
    make: str,
    model: str,
    operation: str,
) -> list[PartInfo]:
    """
    Get parts list for a repair operation.
    Stub: returns mock data. Replace with MOTOR API when configured.
    """
    stub_parts = {
        "brake": [PartInfo("BP-12345", "Brake pad set", 8999, 1)],
        "oil": [PartInfo("OF-001", "Oil filter", 1299, 1), PartInfo("OIL-5QT", "Motor oil 5qt", 2999, 1)],
        "battery": [PartInfo("BAT-65", "12V Battery 65Ah", 14999, 1)],
        "spark": [PartInfo("SP-4PK", "Spark plug set (4)", 3999, 1)],
    }
    op_lower = operation.lower()
    for k, parts in stub_parts.items():
        if k in op_lower:
            return parts
    return [PartInfo("PART-001", operation, 4999, 1)]


def get_dtc_info(code: str) -> Optional[DTCInfo]:
    """
    Get DTC information and suggested repair operations.
    Stub: returns mock data. Replace with MOTOR API when configured.
    """
    stub_dtcs = {
        "P0300": DTCInfo("P0300", "Random/Multiple Cylinder Misfire", "Powertrain", ["Spark plug replacement", "Ignition coil check"]),
        "P0301": DTCInfo("P0301", "Cylinder 1 Misfire", "Powertrain", ["Spark plug replacement", "Ignition coil"]),
        "P0420": DTCInfo("P0420", "Catalyst System Efficiency", "Powertrain", ["Catalytic converter", "O2 sensor"]),
    }
    return stub_dtcs.get(code.upper())


def get_upfront_estimate(
    year: int,
    make: str,
    model: str,
    part_info: str,
    labor_rate_cents_per_hour: int = 15000,  # $150/hr default
) -> dict:
    """
    Get upfront repair estimate (labor + parts).
    Used in dispatch for mechanic pricing.
    """
    labor_times = get_labor_times(year, make, model, part_info)
    parts = get_parts_for_operation(year, make, model, part_info)
    labor_cents = sum(int(lt.hours * 100 * labor_rate_cents_per_hour / 100) for lt in labor_times)
    parts_cents = sum(p.price_cents * p.quantity for p in parts)
    return {
        "labor_hours": sum(lt.hours for lt in labor_times),
        "labor_cents": labor_cents,
        "parts_cents": parts_cents,
        "total_cents": labor_cents + parts_cents,
        "operations": [{"operation": lt.operation, "hours": lt.hours} for lt in labor_times],
        "parts": [{"part_number": p.part_number, "description": p.description, "price_cents": p.price_cents} for p in parts],
    }
