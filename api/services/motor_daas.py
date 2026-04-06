"""
MOTOR DaaS integration stub.
Provides labor times, parts, DTCs, and service procedures for upfront pricing.

Replace with real MOTOR API when MOTOR_API_KEY is configured in the environment.
Until then, this stub returns realistic flat-rate hour estimates and typical
parts data drawn from industry standard flat-rate guides (Chilton, Mitchell, AllData).

Labor hours are *per-axle* or *per-unit* unless noted. Ranges are given as
(base, max) — actual time varies by vehicle design, access, and condition.
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
    hours_max: Optional[float]
    description: str
    skill_level: str = "intermediate"  # basic | intermediate | advanced | professional
    notes: str = ""


@dataclass
class PartInfo:
    """Part information."""
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


# ---------------------------------------------------------------------------
# Comprehensive stub labor time database (~40 operations)
# Format: operation_key -> LaborTime
# hours / hours_max are industry-average flat-rate times.
# ---------------------------------------------------------------------------

_LABOR_DB: dict[str, LaborTime] = {
    # ---- Brakes ----
    "brake_pad_front":          LaborTime("Front brake pad replacement", 1.5, 2.0, "Front pads; does not include rotor R&R or fluid flush"),
    "brake_pad_rear":           LaborTime("Rear brake pad replacement", 1.5, 2.2, "Rear pads; caliper wind-back required on some vehicles"),
    "brake_rotor_front":        LaborTime("Front brake rotor replacement (R&R)", 1.8, 2.5, "Includes pad R&R"),
    "brake_rotor_rear":         LaborTime("Rear brake rotor replacement (R&R)", 2.0, 2.8, "Includes pad R&R"),
    "brake_caliper_front":      LaborTime("Front brake caliper replacement", 1.5, 2.0, "One side; includes pad and bleed"),
    "brake_caliper_rear":       LaborTime("Rear brake caliper replacement", 1.5, 2.2, "One side; includes pad and bleed"),
    "brake_master_cylinder":    LaborTime("Brake master cylinder replacement", 2.0, 3.0, "Includes bench bleed and full system bleed", "advanced"),
    "brake_fluid_flush":        LaborTime("Brake fluid flush (full system)", 0.7, 1.0, "Gravity or pressure bleed"),
    "abs_wheel_speed_sensor":   LaborTime("ABS wheel speed sensor replacement", 0.8, 1.5, "One sensor; includes connector inspection"),
    "abs_module":               LaborTime("ABS module / hydraulic unit replacement", 3.0, 5.0, "Includes bleed and initialization", "professional"),

    # ---- Engine ----
    "oil_change":               LaborTime("Oil and filter change", 0.4, 0.6, "Drain, fill, reset service indicator"),
    "spark_plug":               LaborTime("Spark plug replacement (all cylinders)", 1.0, 3.0, "Hours vary widely by access; coil-on-plug included"),
    "ignition_coil":            LaborTime("Ignition coil replacement (single)", 0.5, 1.0, "Includes plug inspection"),
    "timing_belt":              LaborTime("Timing belt replacement", 3.5, 6.0, "Includes tensioner/idler; coolant hoses and water pump recommended", "advanced"),
    "timing_chain":             LaborTime("Timing chain replacement", 6.0, 10.0, "Includes guides, tensioner, gaskets", "professional"),
    "valve_cover_gasket":       LaborTime("Valve cover gasket replacement", 1.0, 2.5, "Hours vary by cam cover access"),
    "head_gasket":              LaborTime("Head gasket replacement (one head)", 8.0, 14.0, "Includes resurface check, new head bolts, coolant flush", "professional"),
    "intake_manifold_gasket":   LaborTime("Intake manifold gasket replacement", 2.0, 4.0, "Coolant crossover included where applicable"),
    "vvt_solenoid":             LaborTime("VVT / oil control solenoid replacement", 0.8, 1.5, "Includes filter screen inspection"),
    "cam_sensor":               LaborTime("Camshaft position sensor replacement", 0.5, 1.2, ""),
    "crank_sensor":             LaborTime("Crankshaft position sensor replacement", 0.8, 1.5, "Access varies; some require subframe drop", "intermediate"),
    "egr_valve":                LaborTime("EGR valve replacement", 1.0, 2.0, "Includes passage cleaning"),
    "throttle_body_service":    LaborTime("Throttle body cleaning + idle relearn", 0.8, 1.2, "Includes ETB relearn procedure"),
    "throttle_body_replace":    LaborTime("Throttle body replacement + relearn", 1.2, 2.0, "Includes all gaskets and relearn"),
    "maf_sensor":               LaborTime("MAF sensor replacement / cleaning", 0.3, 0.5, ""),
    "coolant_temp_sensor":      LaborTime("Engine coolant temperature sensor replacement", 0.5, 1.0, "Includes partial coolant drain"),
    "thermostat":               LaborTime("Thermostat and housing replacement", 0.8, 1.5, "Includes coolant drain and refill"),
    "water_pump":               LaborTime("Water pump replacement", 1.5, 4.0, "Range reflects belt-driven vs gear-driven; cooling flush included"),
    "radiator":                 LaborTime("Radiator replacement", 2.0, 3.5, "Includes coolant flush and hose inspection"),
    "radiator_fan_electric":    LaborTime("Electric radiator fan assembly replacement", 1.0, 1.8, ""),

    # ---- Fuel System ----
    "fuel_pump":                LaborTime("Fuel pump replacement (in-tank)", 1.5, 3.0, "Includes ring lock and sending unit; some vehicles require fuel tank drop", "intermediate"),
    "fuel_injector":            LaborTime("Fuel injector replacement (single)", 0.8, 1.5, "Includes fuel rail drop and O-ring kit"),
    "fuel_injectors_all":       LaborTime("Fuel injector replacement (all, 4-cyl)", 2.0, 3.0, "Full set; includes rail and manifold as needed"),
    "fuel_pressure_regulator":  LaborTime("Fuel pressure regulator replacement", 0.5, 1.0, ""),

    # ---- Charging / Starting ----
    "battery":                  LaborTime("Battery replacement (12V)", 0.3, 0.5, "Includes terminal cleaning and registration if required"),
    "alternator":               LaborTime("Alternator replacement", 1.5, 2.5, "Includes belt R&R and charging test"),
    "starter":                  LaborTime("Starter motor replacement", 1.2, 2.5, "Access varies significantly by model"),

    # ---- Belts / Pulleys / Accessories ----
    "serpentine_belt":          LaborTime("Serpentine belt replacement", 0.5, 1.0, ""),
    "belt_tensioner":           LaborTime("Belt tensioner replacement", 0.8, 1.5, "Includes belt R&R"),
    "idler_pulley":             LaborTime("Idler pulley replacement", 0.5, 1.0, "Includes belt R&R"),
    "power_steering_pump":      LaborTime("Power steering pump replacement", 2.0, 3.0, "Includes flush and bleed", "intermediate"),

    # ---- Suspension ----
    "wheel_bearing_front":      LaborTime("Front wheel bearing / hub assembly replacement", 2.0, 3.0, "One side; includes brake inspection"),
    "wheel_bearing_rear":       LaborTime("Rear wheel bearing / hub assembly replacement", 1.8, 2.8, "One side"),
    "strut_front":              LaborTime("Front strut assembly replacement", 2.0, 3.0, "One side; alignment required after", "intermediate"),
    "strut_rear":               LaborTime("Rear strut assembly replacement", 1.5, 2.5, "One side"),
    "strut_mount":              LaborTime("Strut mount / bearing plate replacement", 0.8, 1.2, "Per side; includes strut R&R"),
    "sway_bar_end_link":        LaborTime("Sway bar end link replacement", 0.5, 0.8, "Per side"),
    "sway_bar_bushing":         LaborTime("Sway bar bushing replacement", 0.8, 1.2, "Both sides"),
    "ball_joint_lower":         LaborTime("Lower ball joint replacement", 2.0, 3.5, "Per side; alignment required after", "advanced"),
    "control_arm":              LaborTime("Control arm replacement", 1.5, 2.5, "Per side; alignment required after"),
    "tie_rod_end":              LaborTime("Tie rod end replacement", 1.0, 1.5, "Per side; alignment required after"),
    "cv_axle_front":            LaborTime("Front CV axle shaft replacement", 1.5, 2.5, "One side"),
    "cv_axle_rear":             LaborTime("Rear CV axle shaft replacement", 1.5, 2.5, "One side; some AWD vehicles significantly longer"),

    # ---- Transmission ----
    "transmission_fluid":       LaborTime("Transmission fluid and filter service (AT)", 1.0, 1.5, "Includes pan drop and filter; full flush extra"),
    "torque_converter":         LaborTime("Torque converter replacement", 6.0, 10.0, "Transmission R&R required", "professional"),
    "trans_shift_solenoid":     LaborTime("Transmission shift solenoid replacement", 3.0, 6.0, "May require pan drop or full R&R depending on location", "professional"),
    "clutch_kit":               LaborTime("Clutch kit replacement (manual trans)", 5.0, 8.0, "Includes flywheel inspection and resurface", "advanced"),

    # ---- Exhaust ----
    "oxygen_sensor_upstream":   LaborTime("Upstream O2 sensor replacement", 0.5, 1.0, "Thread sealant and bung condition check included"),
    "oxygen_sensor_downstream": LaborTime("Downstream O2 sensor replacement", 0.5, 1.0, ""),
    "catalytic_converter":      LaborTime("Catalytic converter replacement (direct-fit)", 1.5, 2.5, "Includes O2 sensor reinstall and exhaust gasket"),
    "exhaust_manifold":         LaborTime("Exhaust manifold replacement", 2.0, 4.0, "Includes gasket and stud replacement as needed", "intermediate"),
    "exhaust_manifold_gasket":  LaborTime("Exhaust manifold gasket replacement", 1.5, 3.0, ""),

    # ---- HVAC ----
    "ac_recharge":              LaborTime("A/C system recharge (R-134a)", 0.8, 1.2, "Includes leak check and performance test"),
    "ac_compressor":            LaborTime("A/C compressor replacement", 3.0, 5.0, "Includes system evacuate and recharge", "advanced"),
    "cabin_air_filter":         LaborTime("Cabin air filter replacement", 0.2, 0.5, ""),
    "blower_motor":             LaborTime("Blower motor replacement", 0.8, 1.5, "Access varies; some require dash partial disassembly"),
    "blend_door_actuator":      LaborTime("Blend door actuator replacement", 1.0, 2.5, "Access varies widely by vehicle"),
}


# ---------------------------------------------------------------------------
# Parts stub database (~common operations)
# ---------------------------------------------------------------------------

_PARTS_DB: dict[str, list[PartInfo]] = {
    "brake_pad":        [PartInfo("BP-PREM", "Premium brake pad set (axle)", 7500, 1)],
    "brake_rotor":      [PartInfo("BR-OEM", "Brake rotor (each)", 6500, 1)],
    "brake_caliper":    [PartInfo("BC-REMAN", "Remanufactured brake caliper", 8999, 1)],
    "oil_change":       [PartInfo("OF-001", "Oil filter", 899, 1), PartInfo("OIL-5QT", "Full synthetic oil 5qt", 3299, 1)],
    "battery":          [PartInfo("BAT-65AGM", "Group 65 AGM battery", 17999, 1)],
    "spark_plug":       [PartInfo("SP-NGK-4PK", "NGK iridium plugs (4-pack)", 5999, 1)],
    "ignition_coil":    [PartInfo("IC-OEM", "OEM-spec ignition coil", 4999, 1)],
    "alternator":       [PartInfo("ALT-REMAN", "Remanufactured alternator", 19999, 1)],
    "starter":          [PartInfo("STR-REMAN", "Remanufactured starter", 13999, 1)],
    "serpentine_belt":  [PartInfo("SB-GATES", "Gates serpentine belt", 2999, 1)],
    "belt_tensioner":   [PartInfo("BT-OEM", "Tensioner assembly", 4999, 1), PartInfo("SB-GATES", "Serpentine belt", 2999, 1)],
    "wheel_bearing":    [PartInfo("WB-HUB", "Hub/bearing assembly", 12999, 1)],
    "water_pump":       [PartInfo("WP-GATES", "Water pump with gasket", 6999, 1)],
    "thermostat":       [PartInfo("TSTAT-OEM", "Thermostat + housing kit", 3999, 1)],
    "fuel_pump":        [PartInfo("FP-AIRTEX", "Fuel pump module assembly", 18999, 1)],
    "fuel_injector":    [PartInfo("FI-REMAN", "Remanufactured fuel injector", 5499, 1)],
    "oxygen_sensor":    [PartInfo("O2-BOSCH", "Bosch O2 sensor", 4999, 1)],
    "catalytic_converter": [PartInfo("CAT-DIRECT", "Direct-fit catalytic converter", 29999, 1)],
    "maf_sensor":       [PartInfo("MAF-OEM", "MAF sensor", 8999, 1)],
    "egr_valve":        [PartInfo("EGR-NEW", "EGR valve", 9999, 1)],
    "vvt_solenoid":     [PartInfo("VVT-SOL", "Oil control valve / VVT solenoid", 4999, 1)],
    "cam_sensor":       [PartInfo("CMP-OEM", "Camshaft position sensor", 2999, 1)],
    "crank_sensor":     [PartInfo("CKP-OEM", "Crankshaft position sensor", 2999, 1)],
    "strut_front":      [PartInfo("STR-MONRO", "Front strut assembly (each)", 9999, 1)],
    "cv_axle":          [PartInfo("CV-REMAN", "Remanufactured CV axle shaft", 11999, 1)],
    "abs_sensor":       [PartInfo("ABS-WSS", "Wheel speed sensor", 3499, 1)],
    "timing_belt_kit":  [PartInfo("TBK-GATES", "Timing belt kit (belt + tensioner + idler)", 17999, 1), PartInfo("WP-GATES", "Water pump", 6999, 1)],
    "head_gasket":      [PartInfo("HG-FEL", "Head gasket set (Fel-Pro)", 14999, 1), PartInfo("HB-OEM", "Head bolt set", 3999, 1)],
    "ac_compressor":    [PartInfo("ACC-REMAN", "Remanufactured A/C compressor", 24999, 1)],
    "blower_motor":     [PartInfo("BM-OEM", "Blower motor", 7999, 1)],
    "torque_converter": [PartInfo("TC-REMAN", "Remanufactured torque converter", 29999, 1)],
    "clutch_kit":       [PartInfo("CLT-SACHS", "SACHS clutch kit (disc + PP + TO bearing)", 24999, 1)],
}


# ---------------------------------------------------------------------------
# DTC stub database (common codes)
# ---------------------------------------------------------------------------

_DTC_DB: dict[str, DTCInfo] = {
    "P0087": DTCInfo("P0087", "Fuel Rail/System Pressure Too Low",            "Powertrain", ["fuel_pump", "fuel_pressure_regulator", "fuel_filter"]),
    "P0088": DTCInfo("P0088", "Fuel Rail/System Pressure Too High",           "Powertrain", ["fuel_pressure_regulator"]),
    "P0011": DTCInfo("P0011", "Camshaft Position Timing Over-Advanced B1",    "Powertrain", ["vvt_solenoid", "timing_chain"]),
    "P0012": DTCInfo("P0012", "Camshaft Position Timing Over-Retarded B1",    "Powertrain", ["vvt_solenoid", "timing_chain"]),
    "P0021": DTCInfo("P0021", "Camshaft Position Timing Over-Advanced B2",    "Powertrain", ["vvt_solenoid"]),
    "P0022": DTCInfo("P0022", "Camshaft Position Timing Over-Retarded B2",    "Powertrain", ["vvt_solenoid"]),
    "P0113": DTCInfo("P0113", "Intake Air Temperature Sensor Circuit High",   "Powertrain", ["maf_sensor"]),
    "P0115": DTCInfo("P0115", "Engine Coolant Temperature Circuit Fault",     "Powertrain", ["coolant_temp_sensor"]),
    "P0121": DTCInfo("P0121", "Throttle Position Sensor Range/Performance",   "Powertrain", ["throttle_body_replace"]),
    "P0128": DTCInfo("P0128", "Coolant Temperature Below Thermostat Range",   "Powertrain", ["thermostat"]),
    "P0171": DTCInfo("P0171", "System Too Lean (Bank 1)",                     "Powertrain", ["maf_sensor", "oxygen_sensor_upstream", "fuel_pump"]),
    "P0172": DTCInfo("P0172", "System Too Rich (Bank 1)",                     "Powertrain", ["fuel_pressure_regulator", "fuel_injector", "oxygen_sensor_upstream"]),
    "P0174": DTCInfo("P0174", "System Too Lean (Bank 2)",                     "Powertrain", ["maf_sensor", "oxygen_sensor_upstream"]),
    "P0217": DTCInfo("P0217", "Engine Over Temperature",                      "Powertrain", ["radiator_fan_electric", "thermostat", "water_pump"]),
    "P0299": DTCInfo("P0299", "Turbocharger Underboost Condition",            "Powertrain", ["serpentine_belt", "power_steering_pump"]),  # generic ops
    "P0300": DTCInfo("P0300", "Random/Multiple Cylinder Misfire",             "Powertrain", ["spark_plug", "ignition_coil", "fuel_injector"]),
    "P0301": DTCInfo("P0301", "Cylinder 1 Misfire Detected",                  "Powertrain", ["spark_plug", "ignition_coil"]),
    "P0302": DTCInfo("P0302", "Cylinder 2 Misfire Detected",                  "Powertrain", ["spark_plug", "ignition_coil"]),
    "P0335": DTCInfo("P0335", "Crankshaft Position Sensor Circuit",           "Powertrain", ["crank_sensor"]),
    "P0340": DTCInfo("P0340", "Camshaft Position Sensor Circuit (B1)",        "Powertrain", ["cam_sensor"]),
    "P0401": DTCInfo("P0401", "EGR Insufficient Flow",                        "Powertrain", ["egr_valve"]),
    "P0420": DTCInfo("P0420", "Catalyst System Efficiency Below Threshold B1","Powertrain", ["catalytic_converter", "oxygen_sensor_downstream"]),
    "P0430": DTCInfo("P0430", "Catalyst System Efficiency Below Threshold B2","Powertrain", ["catalytic_converter", "oxygen_sensor_downstream"]),
    "P0441": DTCInfo("P0441", "EVAP Emission Control System Incorrect Purge", "Powertrain", ["fuel_pressure_regulator"]),
    "P0562": DTCInfo("P0562", "System Voltage Low",                           "Powertrain", ["alternator", "battery"]),
    "P0700": DTCInfo("P0700", "Transmission Control System Malfunction",      "Powertrain", ["trans_shift_solenoid", "transmission_fluid"]),
    "P0741": DTCInfo("P0741", "Torque Converter Clutch Circuit Performance",  "Powertrain", ["torque_converter", "transmission_fluid"]),
    "C0035": DTCInfo("C0035", "Left Front Wheel Speed Sensor Circuit",        "Chassis",   ["abs_wheel_speed_sensor"]),
    "C0040": DTCInfo("C0040", "Right Front Wheel Speed Sensor Circuit",       "Chassis",   ["abs_wheel_speed_sensor"]),
    "C0045": DTCInfo("C0045", "Left Rear Wheel Speed Sensor Circuit",         "Chassis",   ["abs_wheel_speed_sensor"]),
    "C0050": DTCInfo("C0050", "Right Rear Wheel Speed Sensor Circuit",        "Chassis",   ["abs_wheel_speed_sensor"]),
}


# ---------------------------------------------------------------------------
# Public API (unchanged signatures for drop-in compatibility)
# ---------------------------------------------------------------------------

def get_labor_times(
    year: int,
    make: str,
    model: str,
    operation: str,
) -> list[LaborTime]:
    """
    Get labor time(s) for a repair operation.
    Falls back to the comprehensive stub when MOTOR_API_KEY is not configured.
    """
    key = operation.lower().strip().replace(" ", "_")
    # Direct key match
    if key in _LABOR_DB:
        return [_LABOR_DB[key]]
    # Partial key match (longest matching key wins)
    matches = [(k, v) for k, v in _LABOR_DB.items() if k in key or key in k]
    if matches:
        best = max(matches, key=lambda x: len(x[0]))
        return [best[1]]
    return [LaborTime(operation, 1.0, None, "Estimated – operation not in flat-rate guide")]


def get_parts_for_operation(
    year: int,
    make: str,
    model: str,
    operation: str,
) -> list[PartInfo]:
    """
    Get parts list for a repair operation.
    Falls back to comprehensive stub when MOTOR_API_KEY is not configured.
    """
    op_lower = operation.lower()
    for k, parts in _PARTS_DB.items():
        if k in op_lower or op_lower in k:
            return parts
    return [PartInfo("PART-EST", operation, 4999, 1)]


def get_dtc_info(code: str) -> Optional[DTCInfo]:
    """
    Get DTC information and suggested repair operations.
    Falls back to stub; replace with MOTOR API when configured.
    """
    return _DTC_DB.get((code or "").strip().upper())


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
    labor_cents = sum(int(lt.hours * labor_rate_cents_per_hour) for lt in labor_times)
    parts_cents = sum(p.price_cents * p.quantity for p in parts)
    return {
        "labor_hours": sum(lt.hours for lt in labor_times),
        "labor_hours_max": sum(lt.hours_max or lt.hours for lt in labor_times),
        "labor_cents": labor_cents,
        "parts_cents": parts_cents,
        "total_cents": labor_cents + parts_cents,
        "operations": [
            {
                "operation": lt.operation,
                "hours": lt.hours,
                "hours_max": lt.hours_max,
                "skill_level": lt.skill_level,
                "notes": lt.notes,
            }
            for lt in labor_times
        ],
        "parts": [
            {"part_number": p.part_number, "description": p.description, "price_cents": p.price_cents}
            for p in parts
        ],
    }
