"""
Seed data for failure_modes table (master-tech pattern layer).
Each entry: failure_id, display_name, description, mechanical_class,
required_conditions, supporting_conditions, disqualifiers, weight, confirm_tests, vehicle_scope.

confirm_tests entries support an optional "confidence_weight" field (float, default 1.0)
that scales the pass/fail score adjustment in apply_confirm_test().
High-diagnostic-value tests (leakdown, smoke, scope) should use 1.2–1.5.
Low-value tests (visual inspection, water spray) should use 0.6–0.8.
"""


def get_seed_failure_modes():
    """Return list of failure mode dicts for initial seed."""
    return [

        # ----------------------------------------------------------------
        # FUEL / AIR METERING
        # ----------------------------------------------------------------
        {
            "failure_id": "VACUUM_LEAK_BOTH_BANKS",
            "display_name": "Vacuum / intake leak (both banks)",
            "description": "Unmetered air entering intake; both banks lean at idle.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["P0171", "P0174"],
            "supporting_conditions": ["lean_trim_above_15", "at_idle", "hissing_noise"],
            "disqualifiers": ["lean_under_load_only", "one_bank_lean_only"],
            "weight": 0.85,
            "confirm_tests": [
                {"test": "smoke_test_intake", "tool": "Smoke machine", "expected": "Smoke escapes at leak point", "confidence_weight": 1.4},
                {"test": "spray_carb_cleaner", "tool": "Carb cleaner", "expected": "RPM change at leak point", "confidence_weight": 0.8},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "MAF_CONTAMINATION",
            "display_name": "MAF sensor contamination or fault",
            "description": "Dirty or faulty MAF; both-bank lean trim, driveability issues under load.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0171", "P0174"],
            "supporting_conditions": ["lean_trim_above_15", "under_load", "poor_driveability"],
            "disqualifiers": ["vacuum_leak_confirmed"],
            "weight": 0.70,
            "confirm_tests": [
                {"test": "maf_reading_scan", "tool": "Scan tool", "expected": "MAF g/s out of expected range", "confidence_weight": 1.2},
                {"test": "clean_maf_retest", "tool": "MAF cleaner spray", "expected": "Fuel trims improve after cleaning", "confidence_weight": 0.9},
                {"test": "maf_unplug_idle", "tool": "None", "expected": "Idle improves with MAF unplugged (speed density fallback)", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "O2_SENSOR_UPSTREAM_LAZY",
            "display_name": "Upstream O2 sensor lazy / degraded",
            "description": "Slow or biased upstream O2 sensor causing fuel trim hunting or false lean/rich codes.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0136"],
            "supporting_conditions": ["P0131", "P0132", "lean_trim_above_15", "poor_driveability"],
            "disqualifiers": [],
            "weight": 0.72,
            "confirm_tests": [
                {"test": "o2_live_data_scan", "tool": "Scan tool", "expected": "O2 voltage switches < 8 times in 10 sec at idle", "confidence_weight": 1.3},
                {"test": "o2_response_test", "tool": "Lab scope", "expected": "Slow cross-counts or biased waveform", "confidence_weight": 1.5},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "O2_SENSOR_DOWNSTREAM_MIMICKING",
            "display_name": "Downstream O2 sensor mimicking upstream",
            "description": "Catalyst efficiency code driven by downstream sensor switching like upstream.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0420"],
            "supporting_conditions": ["P0430", "high_mileage"],
            "disqualifiers": ["exhaust_leak_confirmed", "misfires_present"],
            "weight": 0.68,
            "confirm_tests": [
                {"test": "downstream_o2_live", "tool": "Scan tool", "expected": "Downstream O2 switching (should be flat ~0.6V)", "confidence_weight": 1.3},
                {"test": "catalyst_temp_drop", "tool": "Pyrometer", "expected": "Outlet temp not significantly lower than inlet", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "INJECTOR_LEAK_SINGLE",
            "display_name": "Fuel injector leak (single cylinder)",
            "description": "Injector dripping; rich at idle, possible single-cylinder misfire.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["rich_at_idle"],
            "supporting_conditions": ["P0300", "P0172", "occurs_at_idle"],
            "disqualifiers": ["lean_at_idle", "normal_trim_cruise"],
            "weight": 0.75,
            "confirm_tests": [
                {"test": "fuel_pressure_hold", "tool": "Fuel pressure gauge", "expected": "Pressure drops with engine off (> 5 psi drop in 10 min)", "confidence_weight": 1.2},
                {"test": "injector_balance_test", "tool": "Scan tool / scope", "expected": "One injector contribution pattern off", "confidence_weight": 1.4},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "PURGE_VALVE_STUCK_OPEN",
            "display_name": "EVAP purge valve stuck open",
            "description": "Purge valve leaking vapors into intake at idle; lean correction and EVAP codes.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0171"],
            "supporting_conditions": ["P0442", "P0455", "lean_trim_above_15", "at_idle"],
            "disqualifiers": ["no_evap_codes", "both_banks_lean_idle"],
            "weight": 0.75,
            "confirm_tests": [
                {"test": "purge_valve_click", "tool": "Scan tool", "expected": "Valve does not click when commanded", "confidence_weight": 1.1},
                {"test": "smoke_evap", "tool": "Smoke machine", "expected": "Smoke exits from purge valve or lines", "confidence_weight": 1.4},
                {"test": "block_purge_line_idle", "tool": "Clamp/cap", "expected": "Fuel trims improve when purge line clamped at idle", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # IGNITION / MISFIRE
        # ----------------------------------------------------------------
        {
            "failure_id": "IGNITION_COIL_SINGLE",
            "display_name": "Ignition coil failure (single cylinder)",
            "description": "One coil weak or dead; single-cylinder misfire, often P030x.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["single_cylinder_misfire"],
            "supporting_conditions": ["P0301", "P0302", "P0303", "P0304", "misfire_under_load", "cold_start_misfire"],
            "disqualifiers": ["misfire_all_cylinders", "coolant_loss"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "swap_coil", "tool": "None", "expected": "Misfire moves to swapped cylinder", "confidence_weight": 1.5},
                {"test": "secondary_scope", "tool": "Lab scope", "expected": "Weak or missing spark event on one cylinder", "confidence_weight": 1.5},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "SPARK_PLUG_WORN",
            "display_name": "Worn or fouled spark plug(s)",
            "description": "Degraded plugs causing weak ignition; misfires under load, rough idle.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0300"],
            "supporting_conditions": ["single_cylinder_misfire", "misfire_under_load", "high_mileage", "rough_idle"],
            "disqualifiers": ["coil_swap_moved_misfire"],
            "weight": 0.73,
            "confirm_tests": [
                {"test": "plug_inspection", "tool": "Visual", "expected": "Fouled, cracked, or gapped plug(s)", "confidence_weight": 0.8},
                {"test": "compression_test", "tool": "Compression tester", "expected": "Normal compression (rules out mechanical)", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "HEAD_GASKET_CYL1_COLD",
            "display_name": "Head gasket seepage (cylinder 1, cold start)",
            "description": "Coolant entering cylinder 1 at cold start; misfire and coolant loss.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0301", "cold_start_misfire", "coolant_loss"],
            "supporting_conditions": ["rough_cold_start", "lean_trim_above_15"],
            "disqualifiers": ["no_coolant_loss", "misfire_all_cylinders", "misfire_hot_only"],
            "weight": 0.82,
            "confirm_tests": [
                {"test": "overnight_pressure_test", "tool": "Cooling system pressure tester", "expected": "Pressure drops overnight", "confidence_weight": 1.3},
                {"test": "leakdown_test", "tool": "Cylinder leakdown tester", "expected": "Air escapes into coolant", "confidence_weight": 1.5},
                {"test": "combustion_gas_test", "tool": "Combustion leak test kit", "expected": "Hydrocarbons detected in coolant reservoir", "confidence_weight": 1.4},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # CAMSHAFT / VARIABLE VALVE TIMING
        # ----------------------------------------------------------------
        {
            "failure_id": "VVT_SOLENOID_BANK1_ADVANCED",
            "display_name": "VVT / cam phaser solenoid stuck advanced (bank 1)",
            "description": "Oil control valve stuck or sludged; cam timing advanced beyond spec.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0011"],
            "supporting_conditions": ["rough_idle", "poor_driveability", "high_mileage"],
            "disqualifiers": ["P0021"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "cam_timing_live", "tool": "Scan tool", "expected": "Cam angle offset outside spec at idle", "confidence_weight": 1.3},
                {"test": "oil_pressure_test", "tool": "Oil pressure gauge", "expected": "Normal oil pressure (rules out oil starvation)", "confidence_weight": 1.1},
                {"test": "vvt_solenoid_resistance", "tool": "Multimeter", "expected": "Resistance out of spec (typically 6.9–7.9 Ω)", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "VVT_SOLENOID_BANK1_RETARDED",
            "display_name": "VVT / cam phaser solenoid stuck retarded (bank 1)",
            "description": "Cam timing retarded beyond spec; low power, poor fuel economy.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0012"],
            "supporting_conditions": ["rough_idle", "poor_driveability"],
            "disqualifiers": ["P0022"],
            "weight": 0.76,
            "confirm_tests": [
                {"test": "cam_timing_live", "tool": "Scan tool", "expected": "Cam angle offset outside spec at idle", "confidence_weight": 1.3},
                {"test": "vvt_solenoid_resistance", "tool": "Multimeter", "expected": "Resistance out of spec", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # CRANK / CAM SENSORS
        # ----------------------------------------------------------------
        {
            "failure_id": "CKP_SENSOR_INTERMITTENT",
            "display_name": "Crankshaft position sensor (intermittent)",
            "description": "CKP signal dropout causing stall, no-start, or random misfire.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0335"],
            "supporting_conditions": ["P0336", "stall_intermittent", "no_start"],
            "disqualifiers": [],
            "weight": 0.80,
            "confirm_tests": [
                {"test": "ckp_waveform_scope", "tool": "Lab scope", "expected": "Signal dropout or erratic pattern during fault", "confidence_weight": 1.5},
                {"test": "ckp_air_gap", "tool": "Feeler gauge", "expected": "Air gap within spec (typically 0.020–0.050 in)", "confidence_weight": 0.9},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "CMP_SENSOR_BANK1",
            "display_name": "Camshaft position sensor fault (bank 1)",
            "description": "CMP signal missing or erratic; hard start, stall, or timing codes.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0340"],
            "supporting_conditions": ["P0341", "hard_start", "stall_intermittent"],
            "disqualifiers": [],
            "weight": 0.76,
            "confirm_tests": [
                {"test": "cmp_waveform_scope", "tool": "Lab scope", "expected": "Missing or erratic cam signal", "confidence_weight": 1.5},
                {"test": "cmp_resistance", "tool": "Multimeter", "expected": "Resistance or voltage out of spec", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # THROTTLE / ELECTRONIC THROTTLE BODY
        # ----------------------------------------------------------------
        {
            "failure_id": "TPS_CIRCUIT_FAULT",
            "display_name": "Throttle position sensor circuit fault",
            "description": "TPS signal out of range or erratic; hesitation, high idle, limp mode.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0121"],
            "supporting_conditions": ["P0122", "P0123", "hesitation", "high_idle"],
            "disqualifiers": [],
            "weight": 0.75,
            "confirm_tests": [
                {"test": "tps_sweep_scan", "tool": "Scan tool", "expected": "TPS % drops out or spikes during slow sweep", "confidence_weight": 1.3},
                {"test": "tps_voltage_scope", "tool": "Multimeter / scope", "expected": "Voltage dropout during sweep", "confidence_weight": 1.4},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "ETB_THROTTLE_BODY_DIRTY",
            "display_name": "Electronic throttle body carbon buildup",
            "description": "Carbon deposits on throttle plate causing rough idle, stumble, or idle relearn needed.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["rough_idle"],
            "supporting_conditions": ["P0507", "P0506", "high_idle", "stall_intermittent"],
            "disqualifiers": ["P0121", "P0122"],
            "weight": 0.65,
            "confirm_tests": [
                {"test": "throttle_body_visual", "tool": "Visual inspection", "expected": "Carbon deposits on throttle bore or plate", "confidence_weight": 0.7},
                {"test": "idle_after_cleaning", "tool": "Throttle body cleaner", "expected": "Idle stabilizes after cleaning + relearn", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # EGR
        # ----------------------------------------------------------------
        {
            "failure_id": "EGR_VALVE_STUCK_OPEN",
            "display_name": "EGR valve stuck open",
            "description": "Excessive exhaust gas recirculation at idle; rough idle, stumble, misfire.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0401"],
            "supporting_conditions": ["rough_idle", "at_idle", "stall_intermittent"],
            "disqualifiers": ["P0402"],
            "weight": 0.74,
            "confirm_tests": [
                {"test": "egr_live_data", "tool": "Scan tool", "expected": "EGR position not fully closed at idle", "confidence_weight": 1.2},
                {"test": "block_egr_port", "tool": "Vacuum cap / blocking plate", "expected": "Idle improves with EGR feed blocked", "confidence_weight": 1.3},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "EGR_VALVE_STUCK_CLOSED",
            "display_name": "EGR valve stuck closed / insufficient flow",
            "description": "EGR not opening under cruise; knock at light throttle, elevated NOx.",
            "mechanical_class": "combustion_impulse",
            "required_conditions": ["P0402"],
            "supporting_conditions": ["knock_light_throttle", "detonation"],
            "disqualifiers": ["P0401"],
            "weight": 0.70,
            "confirm_tests": [
                {"test": "egr_vacuum_test", "tool": "Vacuum pump", "expected": "Valve opens under applied vacuum", "confidence_weight": 1.2},
                {"test": "egr_port_inspection", "tool": "Visual / borescope", "expected": "Carbon-blocked passage", "confidence_weight": 0.9},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # COOLING SYSTEM
        # ----------------------------------------------------------------
        {
            "failure_id": "THERMOSTAT_STUCK_OPEN",
            "display_name": "Thermostat stuck open",
            "description": "Engine runs cold; never reaches normal operating temp, P0128.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["P0128"],
            "supporting_conditions": ["poor_fuel_economy", "slow_warmup", "heater_blows_cold"],
            "disqualifiers": ["overheating"],
            "weight": 0.82,
            "confirm_tests": [
                {"test": "coolant_temp_live", "tool": "Scan tool", "expected": "ECT never exceeds 170°F after 10 min drive", "confidence_weight": 1.3},
                {"test": "radiator_hose_temp", "tool": "IR thermometer", "expected": "Lower hose warm before upper (stat opens early)", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "COOLANT_TEMP_SENSOR_FAULT",
            "display_name": "Engine coolant temperature sensor fault",
            "description": "ECT signal out of range or biased; rich cold start, poor fuel trim.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0115"],
            "supporting_conditions": ["P0117", "P0118", "rich_cold_start", "poor_fuel_economy"],
            "disqualifiers": [],
            "weight": 0.74,
            "confirm_tests": [
                {"test": "ect_resistance_cold", "tool": "Multimeter", "expected": "Resistance matches spec for ambient temp", "confidence_weight": 1.3},
                {"test": "ect_vs_iat_comparison", "tool": "Scan tool", "expected": "ECT and IAT differ significantly after cold soak", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "RADIATOR_FAN_INOPERATIVE",
            "display_name": "Cooling fan inoperative (electric)",
            "description": "Electric fan not running; overheating at idle / low speed.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0217"],
            "supporting_conditions": ["overheating_idle", "P0480", "P0481"],
            "disqualifiers": ["normal_fan_operation"],
            "weight": 0.80,
            "confirm_tests": [
                {"test": "fan_command_scan", "tool": "Scan tool", "expected": "Fan does not spin when commanded on", "confidence_weight": 1.3},
                {"test": "fan_fuse_relay_check", "tool": "Test light / multimeter", "expected": "Blown fuse or faulty relay found", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # TRANSMISSION
        # ----------------------------------------------------------------
        {
            "failure_id": "TCC_SHUDDER_SLIP",
            "display_name": "Torque converter clutch shudder / slip",
            "description": "TCC not locking cleanly; shudder at highway cruise, P0741.",
            "mechanical_class": "gear_mesh_drivetrain",
            "required_conditions": ["P0741"],
            "supporting_conditions": ["shudder_highway", "shudder_light_throttle"],
            "disqualifiers": ["P0730"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "tcc_live_data", "tool": "Scan tool", "expected": "TCC slip RPM > 50 at highway cruise", "confidence_weight": 1.3},
                {"test": "fluid_condition", "tool": "Visual inspection", "expected": "Dark, burnt, or contaminated ATF", "confidence_weight": 0.8},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "TRANS_SOLENOID_FAULT",
            "display_name": "Transmission shift solenoid fault",
            "description": "Solenoid electrical fault or stuck; harsh shift, no 3rd gear, limp mode.",
            "mechanical_class": "gear_mesh_drivetrain",
            "required_conditions": ["P0700"],
            "supporting_conditions": ["P0730", "P0755", "P0758", "harsh_shift", "limp_mode"],
            "disqualifiers": [],
            "weight": 0.72,
            "confirm_tests": [
                {"test": "solenoid_resistance", "tool": "Multimeter", "expected": "Resistance out of spec for affected solenoid", "confidence_weight": 1.2},
                {"test": "atf_level_condition", "tool": "Dipstick / visual", "expected": "Low or degraded fluid", "confidence_weight": 0.7},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # ABS / WHEEL SPEED SENSORS
        # ----------------------------------------------------------------
        {
            "failure_id": "WHEEL_SPEED_SENSOR_FRONT_LEFT",
            "display_name": "Wheel speed sensor fault (front left)",
            "description": "C0035 / C0040 WSS circuit issue; ABS light, traction control disabled.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["C0035"],
            "supporting_conditions": ["ABS_light_on", "traction_control_off", "bearing_noise"],
            "disqualifiers": [],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "wss_live_data", "tool": "Scan tool", "expected": "Front left wheel speed drops to 0 while moving", "confidence_weight": 1.4},
                {"test": "wss_resistance", "tool": "Multimeter", "expected": "Open or short in sensor circuit", "confidence_weight": 1.2},
                {"test": "tone_ring_inspection", "tool": "Visual", "expected": "Damaged, packed, or missing tone ring", "confidence_weight": 0.9},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "ABS_MODULE_FAULT",
            "display_name": "ABS module / hydraulic unit fault",
            "description": "Internal ABS module failure; ABS and stability lights on with no WSS code.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["ABS_light_on"],
            "supporting_conditions": ["stability_light_on", "no_wss_code"],
            "disqualifiers": ["C0035", "C0040", "C0045", "C0050"],
            "weight": 0.65,
            "confirm_tests": [
                {"test": "abs_module_power_ground", "tool": "Multimeter", "expected": "Module has proper power and ground", "confidence_weight": 1.1},
                {"test": "enhanced_abs_scan", "tool": "Enhanced scan tool (ABS capable)", "expected": "Internal fault code in ABS module", "confidence_weight": 1.4},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # TURBO / BOOST
        # ----------------------------------------------------------------
        {
            "failure_id": "TURBO_UNDERBOOST",
            "display_name": "Turbocharger underboost / wastegate stuck open",
            "description": "Boost pressure below target; P0299, loss of power especially at high RPM.",
            "mechanical_class": "hydraulic_flow_cavitation",
            "required_conditions": ["P0299"],
            "supporting_conditions": ["low_power_high_rpm", "boost_leak"],
            "disqualifiers": ["P0234"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "boost_pressure_live", "tool": "Scan tool", "expected": "Boost pressure < target under WOT", "confidence_weight": 1.3},
                {"test": "boost_leak_test", "tool": "Smoke / pressure tester", "expected": "Leak found in intercooler pipe, BOV, or hose", "confidence_weight": 1.4},
                {"test": "wastegate_actuator_check", "tool": "Vacuum pump / hand pump", "expected": "Actuator does not hold pressure", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "TURBO_OVERBOOST",
            "display_name": "Turbocharger overboost / wastegate stuck closed",
            "description": "Boost exceeds target; P0234, detonation risk, possible boost cut.",
            "mechanical_class": "hydraulic_flow_cavitation",
            "required_conditions": ["P0234"],
            "supporting_conditions": ["knock_high_rpm", "boost_cut"],
            "disqualifiers": ["P0299"],
            "weight": 0.76,
            "confirm_tests": [
                {"test": "boost_pressure_live", "tool": "Scan tool", "expected": "Boost exceeds target under load", "confidence_weight": 1.3},
                {"test": "wastegate_actuator_check", "tool": "Vacuum pump", "expected": "Actuator won't extend under pressure", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # FUEL DELIVERY
        # ----------------------------------------------------------------
        {
            "failure_id": "FUEL_PUMP_WEAK",
            "display_name": "Fuel pump weak / failing",
            "description": "Insufficient fuel pressure under load; hesitation, stumble at WOT or hot.",
            "mechanical_class": "hydraulic_flow_cavitation",
            "required_conditions": ["P0087"],
            "supporting_conditions": ["P0230", "hesitation_wot", "stall_hot"],
            "disqualifiers": [],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "fuel_pressure_idle", "tool": "Fuel pressure gauge", "expected": "Pressure below spec at idle or drops under snap throttle", "confidence_weight": 1.4},
                {"test": "fuel_volume_test", "tool": "Graduated container", "expected": "Flow volume below spec (typically < 0.5 L in 10 sec)", "confidence_weight": 1.3},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "FUEL_PRESSURE_REGULATOR",
            "display_name": "Fuel pressure regulator fault",
            "description": "Regulator leaking or stuck; rich idle or lean stumble depending on failure mode.",
            "mechanical_class": "hydraulic_flow_cavitation",
            "required_conditions": ["P0172"],
            "supporting_conditions": ["rich_at_idle", "fuel_smell", "black_smoke"],
            "disqualifiers": [],
            "weight": 0.70,
            "confirm_tests": [
                {"test": "fpr_vacuum_off_check", "tool": "Fuel pressure gauge", "expected": "Pressure drops sharply with vacuum line removed (return-type FPR)", "confidence_weight": 1.3},
                {"test": "fpr_vacuum_port_smell", "tool": "Visual", "expected": "Fuel smell from vacuum port (diaphragm leak)", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # CHARGING / ELECTRICAL
        # ----------------------------------------------------------------
        {
            "failure_id": "ALTERNATOR_UNDERCHARGING",
            "display_name": "Alternator undercharging",
            "description": "Alternator output below spec; battery warning, low voltage, possible whine.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["P0562"],
            "supporting_conditions": ["battery_light", "electrical_drain", "char_whine"],
            "disqualifiers": [],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "charging_voltage_live", "tool": "Multimeter / scan tool", "expected": "Charging voltage < 13.5V at 1500 RPM", "confidence_weight": 1.4},
                {"test": "load_test_alternator", "tool": "Carbon pile tester", "expected": "Voltage drops below 12V under full load", "confidence_weight": 1.5},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "BATTERY_DRAIN_PARASITIC",
            "display_name": "Parasitic battery drain",
            "description": "Excessive key-off current draw; battery dead after overnight sit.",
            "mechanical_class": "electrical_interference",
            "required_conditions": ["battery_dead_overnight"],
            "supporting_conditions": ["P0562", "battery_fails_load_test"],
            "disqualifiers": [],
            "weight": 0.72,
            "confirm_tests": [
                {"test": "parasitic_draw_test", "tool": "Multimeter in series (mA)", "expected": "Draw > 50mA after 10 min sleep", "confidence_weight": 1.5},
                {"test": "fuse_pull_method", "tool": "Multimeter", "expected": "Draw drops when offending circuit fuse pulled", "confidence_weight": 1.3},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # BELTS / PULLEYS
        # ----------------------------------------------------------------
        {
            "failure_id": "BELT_TENSIONER_COLD",
            "display_name": "Serpentine belt / tensioner (cold squeal)",
            "description": "Belt or tensioner noise, often worse when cold.",
            "mechanical_class": "belt_drive_friction",
            "required_conditions": ["squeal_cold", "belt_noise"],
            "supporting_conditions": ["cold_start", "rpm_dependent"],
            "disqualifiers": ["noise_constant_hot"],
            "weight": 0.80,
            "confirm_tests": [
                {"test": "belt_inspection", "tool": "Visual", "expected": "Cracks, glaze, or tensioner oscillation", "confidence_weight": 0.7},
                {"test": "water_spray_test", "tool": "Water bottle", "expected": "Squeal briefly changes with water on belt", "confidence_weight": 0.9},
                {"test": "tensioner_damper_check", "tool": "Visual", "expected": "Tensioner arm oscillates or has oil-soaked damper", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "IDLER_PULLEY_BEARING",
            "display_name": "Idler pulley bearing failure",
            "description": "Idler pulley bearing worn or seized; chirp or shriek, often RPM-dependent.",
            "mechanical_class": "rolling_element_bearing",
            "required_conditions": ["bearing_noise", "rpm_dependency"],
            "supporting_conditions": ["engine_bay_only", "char_squeal"],
            "disqualifiers": ["speed_dependent"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "stethoscope_pulley", "tool": "Mechanic stethoscope", "expected": "Noise loud at idler pulley with belt on", "confidence_weight": 1.3},
                {"test": "belt_off_spin_pulley", "tool": "Hand spin", "expected": "Roughness or wobble felt when spinning by hand", "confidence_weight": 1.4},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # BEARINGS / WHEEL
        # ----------------------------------------------------------------
        {
            "failure_id": "WHEEL_BEARING",
            "display_name": "Wheel bearing wear",
            "description": "Wheel bearing rumble or growl; speed and turn dependent.",
            "mechanical_class": "rolling_element_bearing",
            "required_conditions": ["bearing_noise", "speed_dependent"],
            "supporting_conditions": ["turn_dependent", "rpm_independent"],
            "disqualifiers": ["engine_bay_only", "idle_noise"],
            "weight": 0.82,
            "confirm_tests": [
                {"test": "jack_and_spin", "tool": "Floor jack", "expected": "Rumble or radial play felt at wheel", "confidence_weight": 1.3},
                {"test": "stethoscope_wheel", "tool": "Mechanic stethoscope", "expected": "Noise loudest at hub during drive", "confidence_weight": 1.2},
                {"test": "load_shift_test", "tool": "Drive and swerve gently", "expected": "Noise increases when weight shifts toward bad bearing", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "WATER_PUMP_BEARING",
            "display_name": "Water pump bearing failure",
            "description": "Pump bearing worn; grinding near timing cover, possible coolant weep.",
            "mechanical_class": "rolling_element_bearing",
            "required_conditions": ["bearing_noise", "engine_bay_only"],
            "supporting_conditions": ["rpm_dependency", "coolant_loss", "P0217"],
            "disqualifiers": ["speed_dependent"],
            "weight": 0.78,
            "confirm_tests": [
                {"test": "stethoscope_waterpump", "tool": "Mechanic stethoscope", "expected": "Noise loudest at water pump body", "confidence_weight": 1.3},
                {"test": "pump_shaft_wobble", "tool": "Hand / visual", "expected": "Pulley wobble or bearing play felt by hand", "confidence_weight": 1.4},
                {"test": "weep_hole_inspection", "tool": "Visual / flashlight", "expected": "Coolant staining at pump weep hole", "confidence_weight": 1.0},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # SUSPENSION / STRUCTURAL
        # ----------------------------------------------------------------
        {
            "failure_id": "STRUT_MOUNT_WORN",
            "display_name": "Strut / strut mount worn or failed",
            "description": "Clunking over bumps, poor cornering; worn bearing or mount.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["clunk_over_bumps"],
            "supporting_conditions": ["speed_dependent", "turn_dependent", "maint_suspension_work"],
            "disqualifiers": ["idle_noise", "engine_bay_only"],
            "weight": 0.76,
            "confirm_tests": [
                {"test": "bounce_test", "tool": "Body weight", "expected": "Clunk heard/felt when bouncing corner", "confidence_weight": 1.0},
                {"test": "strut_inspection", "tool": "Visual / lift", "expected": "Leaking strut or cracked/worn mount", "confidence_weight": 1.1},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "SWAY_BAR_END_LINK",
            "display_name": "Sway bar end link or bushing worn",
            "description": "Knock or clunk over small bumps, especially at low speed.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["clunk_small_bumps"],
            "supporting_conditions": ["speed_dependent", "clunk_turning"],
            "disqualifiers": ["idle_noise"],
            "weight": 0.74,
            "confirm_tests": [
                {"test": "visual_sway_bar", "tool": "Visual / lift", "expected": "Cracked bushing or loose/broken end link", "confidence_weight": 1.0},
                {"test": "pry_bar_test", "tool": "Pry bar", "expected": "Movement or clunk felt at end link", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },
        {
            "failure_id": "CV_JOINT_TORN_BOOT",
            "display_name": "CV joint / torn boot (clicking on turns)",
            "description": "Inner or outer CV joint failing; clicking or clunking when turning under load.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["click_on_turns"],
            "supporting_conditions": ["turn_dependent", "speed_dependent"],
            "disqualifiers": ["idle_noise", "engine_bay_only"],
            "weight": 0.80,
            "confirm_tests": [
                {"test": "cv_boot_visual", "tool": "Visual", "expected": "Torn boot with grease flung on nearby components", "confidence_weight": 0.9},
                {"test": "slow_turn_test", "tool": "Drive", "expected": "Clicking increases with sharper turn angle", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },

        # ----------------------------------------------------------------
        # EXHAUST
        # ----------------------------------------------------------------
        {
            "failure_id": "EXHAUST_MANIFOLD_LEAK",
            "display_name": "Exhaust manifold crack or gasket leak",
            "description": "Exhaust gas escaping at manifold; ticking at cold start, smell.",
            "mechanical_class": "structural_resonance",
            "required_conditions": ["tick_cold_start"],
            "supporting_conditions": ["exhaust_smell", "rpm_dependency", "P0420"],
            "disqualifiers": ["tick_constant_hot"],
            "weight": 0.76,
            "confirm_tests": [
                {"test": "visual_manifold", "tool": "Visual / flashlight", "expected": "Carbon deposits, cracks, or warped flange", "confidence_weight": 0.9},
                {"test": "smoke_exhaust_test", "tool": "Smoke machine (exhaust side)", "expected": "Smoke exits at manifold seam or crack", "confidence_weight": 1.4},
                {"test": "prop_wash_test", "tool": "Propane torch unlit", "expected": "Combustible gas detected at leak point", "confidence_weight": 1.2},
            ],
            "vehicle_scope": None,
        },

    ]
