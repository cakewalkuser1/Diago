"""
Seed Data for Known Automotive Fault Signatures

Contains descriptive data for common engine, exhaust, suspension,
bearing, and belt faults along with their associated OBD-II trouble codes.

Note: The actual audio fingerprint hashes would be generated from real
recordings of these faults. The seed data below provides the signature
metadata. Fingerprint hashes can be added via the GUI or by processing
sample WAV files placed in assets/sample_signatures/.
"""


def get_seed_signatures() -> list[dict]:
    """
    Return a list of seed fault signature dictionaries.

    Each dict has: name, description, category, associated_codes
    """
    return [
        # --- Engine Misfire Patterns ---
        {
            "name": "Engine Misfire - Random/Multiple Cylinders",
            "description": (
                "Irregular firing pattern across multiple cylinders. "
                "Characterized by uneven idle RPM fluctuations and "
                "low-frequency rumble with irregular gaps in the "
                "firing order harmonics."
            ),
            "category": "engine",
            "associated_codes": "P0300",
        },
        {
            "name": "Engine Misfire - Cylinder #1",
            "description": (
                "Single-cylinder misfire producing a rhythmic gap in "
                "the firing sequence. Shows as a periodic dropout in "
                "the fundamental firing frequency with sub-harmonics."
            ),
            "category": "engine",
            "associated_codes": "P0301",
        },
        {
            "name": "Engine Misfire - Cylinder #2",
            "description": (
                "Single-cylinder misfire on cylinder 2. Similar "
                "spectral pattern to Cyl #1 misfire but phase-shifted "
                "in the firing order sequence."
            ),
            "category": "engine",
            "associated_codes": "P0302",
        },
        {
            "name": "Engine Misfire - Cylinder #3",
            "description": (
                "Single-cylinder misfire on cylinder 3. Detectable "
                "by periodic amplitude modulation at the cylinder "
                "firing rate."
            ),
            "category": "engine",
            "associated_codes": "P0303",
        },
        {
            "name": "Engine Misfire - Cylinder #4",
            "description": (
                "Single-cylinder misfire on cylinder 4. Produces a "
                "characteristic periodic gap in the exhaust pulse "
                "pattern."
            ),
            "category": "engine",
            "associated_codes": "P0304",
        },
        {
            "name": "Engine Misfire - Cylinder #5",
            "description": (
                "Misfire on cylinder 5 (V6/V8 engines). Identified "
                "by its position in the firing order spectrum."
            ),
            "category": "engine",
            "associated_codes": "P0305",
        },
        {
            "name": "Engine Misfire - Cylinder #6",
            "description": (
                "Misfire on cylinder 6 (V6/V8 engines). Phase "
                "position differs from other cylinders."
            ),
            "category": "engine",
            "associated_codes": "P0306",
        },

        # --- Vacuum / Intake Leak ---
        {
            "name": "Vacuum Leak - Intake Manifold",
            "description": (
                "High-frequency hissing sound (2000-6000 Hz) caused by "
                "unmetered air entering the intake manifold. Often "
                "varies with engine load. Broadband noise with possible "
                "tonal components from the leak orifice."
            ),
            "category": "intake",
            "associated_codes": "P0171,P0174",
        },
        {
            "name": "Vacuum Leak - Brake Booster",
            "description": (
                "Hissing from the brake booster vacuum line. Typically "
                "more pronounced during braking. Frequency content "
                "in the 1500-4000 Hz range."
            ),
            "category": "intake",
            "associated_codes": "P0171",
        },
        {
            "name": "PCV Valve Stuck Open",
            "description": (
                "Whistling or sucking noise from the PCV system. "
                "Creates a lean condition with tonal noise around "
                "800-2000 Hz that varies with engine RPM."
            ),
            "category": "intake",
            "associated_codes": "P0171,P0507",
        },

        # --- Exhaust System ---
        {
            "name": "Catalytic Converter Rattle",
            "description": (
                "Internal substrate breakdown causing a metallic "
                "rattling sound, especially at idle and low RPM. "
                "Broadband impulsive noise in 500-3000 Hz range "
                "with acceleration-dependent intensity."
            ),
            "category": "exhaust",
            "associated_codes": "P0420,P0430",
        },
        {
            "name": "Exhaust Manifold Leak",
            "description": (
                "Ticking or tapping sound from a cracked exhaust "
                "manifold or failed gasket. Most prominent at cold "
                "start, reduces as metal expands. Pulsed broadband "
                "noise synchronized with exhaust valve events."
            ),
            "category": "exhaust",
            "associated_codes": "P0420",
        },
        {
            "name": "Exhaust Pipe Leak",
            "description": (
                "Hissing or popping from an exhaust pipe crack or "
                "loose connection. Broadband noise in the "
                "500-4000 Hz range, louder under acceleration."
            ),
            "category": "exhaust",
            "associated_codes": "P0420",
        },

        # --- Belt and Accessory Drive ---
        {
            "name": "Serpentine Belt Squeal",
            "description": (
                "High-pitched squealing from a worn or loose "
                "serpentine belt. Strong tonal content at 1000-4000 Hz "
                "with harmonics. Often worse at cold start or "
                "during power steering input."
            ),
            "category": "belt",
            "associated_codes": "",
        },
        {
            "name": "Belt Tensioner Noise",
            "description": (
                "Chirping or rattling from a failing belt tensioner. "
                "Rhythmic chirp synchronized with belt rotation speed. "
                "May have bearing whine component at higher frequencies."
            ),
            "category": "belt",
            "associated_codes": "",
        },
        {
            "name": "Alternator Whine",
            "description": (
                "Electrical whine from alternator bearings or "
                "brush noise. Tonal frequency proportional to RPM, "
                "typically 600-3000 Hz. May also appear in the "
                "audio system as electrical interference."
            ),
            "category": "electrical",
            "associated_codes": "P0562,P0622",
        },
        {
            "name": "Power Steering Pump Whine",
            "description": (
                "Whining noise from power steering pump, especially "
                "at full lock. Low-to-mid frequency tonal noise "
                "(300-1500 Hz) that varies with steering input "
                "and engine RPM."
            ),
            "category": "other",
            "associated_codes": "",
        },

        # --- Bearings ---
        {
            "name": "Wheel Bearing Hum - Front",
            "description": (
                "Continuous humming or growling that increases with "
                "vehicle speed. Frequency content centered around "
                "200-800 Hz. Changes character during turns "
                "(loading/unloading the bearing)."
            ),
            "category": "bearing",
            "associated_codes": "P0500",
        },
        {
            "name": "Wheel Bearing Hum - Rear",
            "description": (
                "Similar to front wheel bearing hum but typically "
                "lower in frequency. Constant hum that correlates "
                "with vehicle speed, not engine RPM."
            ),
            "category": "bearing",
            "associated_codes": "P0500",
        },
        {
            "name": "Water Pump Bearing Failure",
            "description": (
                "Grinding or squealing from a failing water pump "
                "bearing. Frequency increases with RPM. May have "
                "intermittent metallic scraping sounds as the "
                "impeller contacts the housing."
            ),
            "category": "bearing",
            "associated_codes": "P0117",
        },

        # --- Suspension ---
        {
            "name": "Strut/Shock Clunk",
            "description": (
                "Clunking or knocking from worn strut mounts or "
                "shock absorbers. Impulsive broadband noise "
                "triggered by bumps and road irregularities."
            ),
            "category": "suspension",
            "associated_codes": "",
        },
        {
            "name": "CV Joint Click",
            "description": (
                "Clicking or popping from a worn CV joint, "
                "especially during turns at low speed. Rhythmic "
                "metallic clicks synchronized with wheel rotation."
            ),
            "category": "suspension",
            "associated_codes": "",
        },
        {
            "name": "Sway Bar End Link Rattle",
            "description": (
                "Rattling or clunking over bumps from worn sway bar "
                "end links. Metallic clatter from the front or rear "
                "suspension, especially on uneven surfaces."
            ),
            "category": "suspension",
            "associated_codes": "",
        },
        {
            "name": "Ball Joint Pop",
            "description": (
                "Popping or snapping from a worn ball joint. "
                "Single impulsive sound when steering or going "
                "over bumps. May be accompanied by play in the wheel."
            ),
            "category": "suspension",
            "associated_codes": "",
        },
        {
            "name": "Tie Rod End Clunk",
            "description": (
                "Clunking when turning the steering wheel, caused "
                "by worn inner or outer tie rod ends. Metallic knock "
                "heard when steering input changes direction."
            ),
            "category": "suspension",
            "associated_codes": "",
        },

        # --- Engine Knock / Detonation ---
        {
            "name": "Engine Knock / Detonation",
            "description": (
                "Pinging or knocking sound from abnormal combustion. "
                "Metallic tapping in the 5000-8000 Hz range that "
                "increases with engine load. Usually more severe "
                "under acceleration."
            ),
            "category": "engine",
            "associated_codes": "P0325,P0332",
        },
        {
            "name": "Rod Bearing Knock",
            "description": (
                "Deep knocking from a worn connecting rod bearing. "
                "Lower frequency (100-500 Hz) than detonation knock. "
                "Worsens under load and with engine temperature."
            ),
            "category": "engine",
            "associated_codes": "",
        },
        {
            "name": "Piston Slap",
            "description": (
                "Hollow knocking or slapping sound at cold start "
                "from excessive piston-to-wall clearance. Usually "
                "quiets as the engine warms up. Most noticeable "
                "at low RPM idle."
            ),
            "category": "engine",
            "associated_codes": "",
        },
        {
            "name": "Timing Chain Rattle",
            "description": (
                "Metallic rattling from a stretched timing chain "
                "or worn chain tensioner. Most prominent at startup "
                "and idle. Comes from the front of the engine."
            ),
            "category": "engine",
            "associated_codes": "",
        },
        {
            "name": "Hydraulic Lifter Tick",
            "description": (
                "Rapid ticking from one or more hydraulic valve "
                "lifters. High-frequency metallic tick at the top "
                "of the engine, rate proportional to RPM. May "
                "improve once oil pressure builds."
            ),
            "category": "engine",
            "associated_codes": "",
        },

        # --- Accessory / Pulley (no trouble codes) ---
        {
            "name": "Idler Pulley Bearing Whine",
            "description": (
                "High-pitched whine or howl from a worn idler pulley "
                "bearing. Continuous tonal sound proportional to RPM. "
                "Pitch increases with engine speed. Common on high-"
                "mileage vehicles."
            ),
            "category": "accessory",
            "associated_codes": "",
        },
        {
            "name": "Tensioner Pulley Bearing Noise",
            "description": (
                "Grinding, chirping, or squealing from the belt "
                "tensioner pulley bearing. May be intermittent or "
                "constant. Often accompanied by belt flutter."
            ),
            "category": "accessory",
            "associated_codes": "",
        },
        {
            "name": "AC Compressor Clutch Rattle",
            "description": (
                "Rattling or clicking when the AC compressor clutch "
                "engages. Metallic rattle that starts and stops "
                "with AC cycling. May indicate worn clutch plate "
                "or failing compressor."
            ),
            "category": "accessory",
            "associated_codes": "",
        },
        {
            "name": "AC Compressor Bearing Noise",
            "description": (
                "Grinding or growling from the AC compressor bearing. "
                "Present even when AC is off since the pulley always "
                "spins. Gets louder under load when AC is engaged."
            ),
            "category": "accessory",
            "associated_codes": "",
        },
        {
            "name": "AC Compressor Internal Knock",
            "description": (
                "Knocking or clunking from internal AC compressor "
                "failure. Rhythmic metallic knock when AC is engaged, "
                "stops when AC is turned off."
            ),
            "category": "hvac",
            "associated_codes": "",
        },

        # --- Drivetrain (no trouble codes) ---
        {
            "name": "Differential Whine",
            "description": (
                "Gear whine from the differential. Tonal sound that "
                "varies with vehicle speed, not engine RPM. Pitch "
                "changes on acceleration vs deceleration (coast). "
                "Often a sign of worn ring and pinion gears."
            ),
            "category": "drivetrain",
            "associated_codes": "",
        },
        {
            "name": "Transfer Case Chain Noise",
            "description": (
                "Grinding or whirring from a worn transfer case chain "
                "in 4WD/AWD vehicles. Speed-dependent noise from "
                "under the center of the vehicle."
            ),
            "category": "drivetrain",
            "associated_codes": "",
        },
        {
            "name": "U-Joint Click / Vibration",
            "description": (
                "Clicking at low speed or vibration at highway speed "
                "from worn universal joints on the driveshaft. "
                "Click is rhythmic with wheel rotation."
            ),
            "category": "drivetrain",
            "associated_codes": "",
        },
        {
            "name": "Axle Bearing Hum",
            "description": (
                "Low-frequency humming from a failing axle bearing. "
                "Speed-dependent, louder on one side. Similar to "
                "wheel bearing but located further inboard."
            ),
            "category": "drivetrain",
            "associated_codes": "",
        },

        # --- Transmission ---
        {
            "name": "Transmission Whine (Manual)",
            "description": (
                "Gear whine in specific gears from worn synchronizers "
                "or gear teeth. Tonal noise present only in certain "
                "gears, changes with load."
            ),
            "category": "transmission",
            "associated_codes": "",
        },
        {
            "name": "Torque Converter Shudder",
            "description": (
                "Vibration or shudder during light acceleration at "
                "40-60 mph from torque converter clutch slipping. "
                "Low-frequency pulsation felt and heard."
            ),
            "category": "transmission",
            "associated_codes": "P0741",
        },
        {
            "name": "Throw-Out Bearing Squeal",
            "description": (
                "Squealing when the clutch pedal is pressed, from "
                "a worn throw-out (release) bearing. Noise appears "
                "only with clutch pedal movement."
            ),
            "category": "transmission",
            "associated_codes": "",
        },

        # --- Brakes (no trouble codes) ---
        {
            "name": "Brake Pad Wear Indicator Squeal",
            "description": (
                "High-pitched metallic squeal from brake pad wear "
                "indicators contacting the rotor. Continuous squeal "
                "while driving that stops when brakes are applied."
            ),
            "category": "brakes",
            "associated_codes": "",
        },
        {
            "name": "Brake Rotor Warp Pulsation",
            "description": (
                "Pulsation and rhythmic thumping when braking from "
                "warped brake rotors. Frequency proportional to "
                "wheel speed. Felt in the pedal and heard."
            ),
            "category": "brakes",
            "associated_codes": "",
        },
        {
            "name": "Brake Caliper Rattle",
            "description": (
                "Rattling over bumps from loose brake caliper "
                "hardware or worn slide pins. Metallic clatter "
                "from the wheel area."
            ),
            "category": "brakes",
            "associated_codes": "",
        },
        {
            "name": "Brake Grinding - Metal on Metal",
            "description": (
                "Harsh grinding sound when braking indicating pads "
                "are completely worn through to the backing plate. "
                "Loud, low-frequency metallic grinding."
            ),
            "category": "brakes",
            "associated_codes": "",
        },

        # --- Cooling System ---
        {
            "name": "Radiator Fan Bearing Noise",
            "description": (
                "Whirring or grinding from a failing radiator fan "
                "motor bearing. Heard at the front of the engine "
                "bay, may be intermittent as the fan cycles."
            ),
            "category": "cooling",
            "associated_codes": "",
        },
        {
            "name": "Coolant Boiling / Gurgling",
            "description": (
                "Bubbling or gurgling sound from the cooling system "
                "indicating air in the coolant, a blown head gasket, "
                "or overheating. Heard from the heater core or "
                "overflow tank area."
            ),
            "category": "cooling",
            "associated_codes": "P0217",
        },

        # --- Fuel System ---
        {
            "name": "Fuel Injector Tick",
            "description": (
                "Rapid ticking from fuel injectors. Normal at low "
                "volume, but loud ticking may indicate a leaking "
                "or stuck injector. Rate follows RPM."
            ),
            "category": "fuel",
            "associated_codes": "P0201,P0202,P0203,P0204",
        },
        {
            "name": "Fuel Pump Whine",
            "description": (
                "Whining from a failing in-tank fuel pump. Heard "
                "from the rear of the vehicle near the fuel tank. "
                "Gets louder as the pump weakens."
            ),
            "category": "fuel",
            "associated_codes": "P0230,P0231",
        },
        {
            "name": "EVAP System Hiss",
            "description": (
                "Hissing from the evaporative emissions system, "
                "often from a loose or cracked purge valve or "
                "vacuum line."
            ),
            "category": "fuel",
            "associated_codes": "P0440,P0455",
        },

        # --- Electrical (no codes) ---
        {
            "name": "Starter Motor Grind",
            "description": (
                "Grinding or whirring from a failing starter motor "
                "or worn starter gear not engaging the flywheel "
                "properly. Heard during cranking."
            ),
            "category": "electrical",
            "associated_codes": "",
        },
        {
            "name": "Relay Click / Chatter",
            "description": (
                "Rapid clicking from a relay chattering due to "
                "low voltage or a failing relay. Common with weak "
                "battery or alternator issues."
            ),
            "category": "electrical",
            "associated_codes": "",
        },

        # --- HVAC ---
        {
            "name": "Blower Motor Bearing Squeal",
            "description": (
                "Squealing or whirring from the HVAC blower motor "
                "bearing. Heard inside the cabin when the fan is "
                "running. Volume changes with fan speed setting."
            ),
            "category": "hvac",
            "associated_codes": "",
        },
        {
            "name": "Blend Door Actuator Click",
            "description": (
                "Repetitive clicking from behind the dashboard "
                "caused by a failing blend door actuator trying "
                "to move to position. Starts when climate controls "
                "are adjusted."
            ),
            "category": "hvac",
            "associated_codes": "",
        },
    ]
