"""
Local RAG Knowledge Base (Vector-Free)
Provides context-injection for the ASE Mechanic Agent using structured
JSON knowledge chunks with keyword + TF-IDF retrieval.

No external ML dependencies required -- uses pure Python + math for
TF-IDF scoring. Optional scikit-learn integration for better performance.

Knowledge Categories:
- common_failures: Frequent issues by vehicle type/mileage
- diagnostic_trees: Step-by-step diagnostic decision trees
- repair_procedures: Repair instructions and difficulty ratings
- symptom_patterns: Symptom-to-diagnosis mapping patterns
"""

import json
import math
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeChunk:
    """A single retrievable knowledge chunk."""
    id: str
    title: str
    content: str
    category: str  # common_failures, diagnostic_trees, etc.
    keywords: list[str] = field(default_factory=list)
    vehicle_types: list[str] = field(default_factory=list)
    mileage_range: str = ""
    relevance: float = 0.0  # Set during retrieval


# ---------------------------------------------------------------------------
# Built-in Knowledge (embedded so no external files needed)
# ---------------------------------------------------------------------------

_BUILTIN_KNOWLEDGE: list[dict] = [
    # ---- Common Failures ----
    {
        "id": "cf_wheel_bearing",
        "title": "Wheel Bearing Failure Patterns",
        "category": "common_failures",
        "keywords": ["wheel bearing", "hum", "growl", "speed dependent", "turns"],
        "content": (
            "Wheel bearings typically fail between 75,000-150,000 miles. "
            "Symptoms: humming or growling that increases with speed and "
            "changes tone when turning (loading/unloading the bearing). "
            "Front bearings fail more often due to steering loads. "
            "Common causes: water intrusion, impacts (potholes), "
            "overloaded vehicles. Vehicles with press-in bearings "
            "(most modern vehicles) require a press for replacement. "
            "Hub-integrated bearings are bolt-on. Always check for "
            "play by rocking the wheel at 12 and 6 o'clock positions."
        ),
    },
    {
        "id": "cf_serpentine_belt",
        "title": "Serpentine Belt and Tensioner Issues",
        "category": "common_failures",
        "keywords": ["belt", "squeal", "chirp", "tensioner", "cold start", "accessory"],
        "content": (
            "Serpentine belts last 60,000-100,000 miles. Signs of wear: "
            "squealing at cold start, chirping during turns (power steering "
            "load), visible cracking or glazing. The automatic tensioner "
            "weakens over time -- test by checking belt deflection (should "
            "be ~1/2 inch). A failing tensioner causes belt flutter and "
            "chirp. Idler pulley bearings also wear and create whining. "
            "Replace belt and tensioner together as a maintenance item."
        ),
    },
    {
        "id": "cf_brake_noise",
        "title": "Brake Noise Diagnosis Guide",
        "category": "common_failures",
        "keywords": ["brake", "squeal", "grind", "pulsation", "rotor", "pad"],
        "content": (
            "Brake noises by type: "
            "SQUEAL: Wear indicators contacting rotor = pads need replacement. "
            "GRINDING: Metal-on-metal = pads completely worn, rotor damage likely. "
            "PULSATION: Warped rotors = felt in pedal during braking, "
            "often after aggressive braking or improper torquing of lugs. "
            "RATTLE: Loose caliper hardware or anti-rattle clips. "
            "INTERMITTENT SQUEAK: Possible glazed pads or surface rust "
            "(normal after sitting overnight). "
            "Minimum rotor thickness is stamped on the rotor casting."
        ),
    },
    {
        "id": "cf_timing_chain",
        "title": "Timing Chain Stretch and Failure",
        "category": "common_failures",
        "keywords": ["timing chain", "rattle", "startup", "VVT", "check engine"],
        "content": (
            "Timing chain stretch is common on high-mileage engines, "
            "especially with poor oil change intervals. Symptoms: "
            "rattle at cold startup that fades after oil pressure builds, "
            "P0016/P0017 cam-crank correlation codes, rough idle. "
            "VVT (Variable Valve Timing) engines are more sensitive to "
            "chain stretch as the VVT actuator relies on oil pressure. "
            "Common affected vehicles: GM 2.2L Ecotec, BMW N20/N26, "
            "Hyundai/Kia Theta II. Repair requires chain, tensioner, "
            "and guide replacement -- typically 8-12 hour labor job."
        ),
    },
    {
        "id": "cf_exhaust_leak",
        "title": "Exhaust Leak Diagnosis",
        "category": "common_failures",
        "keywords": ["exhaust", "tick", "leak", "manifold", "gasket", "cold start"],
        "content": (
            "Exhaust manifold leaks are common on engines with cast iron "
            "manifolds (thermal cycling causes cracks). Symptoms: ticking "
            "noise at cold start that fades as the manifold expands and "
            "seals. Loudest under hood, rhythmic with engine speed. "
            "GM 5.3L V8, Subaru EJ25, and Ford 4.6L are notorious for this. "
            "Flex pipes fail from normal flexing. Donut gaskets at the "
            "manifold-to-downpipe joint are a cheap, common fix."
        ),
    },
    {
        "id": "cf_power_steering",
        "title": "Power Steering Noise Issues",
        "category": "common_failures",
        "keywords": ["power steering", "whine", "groan", "pump", "fluid", "steering"],
        "content": (
            "Power steering pump whine indicates low fluid or a failing pump. "
            "Check fluid level first -- low fluid causes cavitation (whine "
            "and groan, especially at full lock). Dark or burnt-smelling "
            "fluid means contamination. The pump's flow control valve can "
            "stick, causing variable whine. Rack and pinion leaks are common "
            "at the input shaft seal and tie rod boot seals. Electric power "
            "steering (EPS) vehicles may have motor or module issues instead."
        ),
    },
    {
        "id": "cf_alternator",
        "title": "Alternator Failure Patterns",
        "category": "common_failures",
        "keywords": ["alternator", "whine", "charging", "battery", "electrical"],
        "content": (
            "Alternator bearings typically fail at 100k-150k miles. "
            "Symptoms: whining proportional to RPM (not vehicle speed), "
            "possible electrical interference in audio system. "
            "Diode failure causes AC ripple -- test with a multimeter "
            "on AC voltage scale at battery terminals (should be <0.5V AC). "
            "Voltage regulator failure causes over/undercharging. "
            "Normal output: 13.8-14.4V at battery with engine running. "
            "Below 13.5V = undercharging. Above 15.0V = overcharging."
        ),
    },
    {
        "id": "cf_cv_joint",
        "title": "CV Joint and Axle Issues",
        "category": "common_failures",
        "keywords": ["cv joint", "click", "popping", "axle", "boot", "turn"],
        "content": (
            "Outer CV joints click during turns due to worn ball bearings "
            "in the joint -- torn boot lets grease out and water in. "
            "Inner CV (tripod) joints cause vibration or clunk during "
            "acceleration from a stop. Boot inspection is the best "
            "preventive check -- torn boots = imminent joint failure. "
            "Full axle replacement is often more cost-effective than "
            "individual joint/boot replacement. Typical cost: $150-400 "
            "per axle (parts + labor)."
        ),
    },

    # ---- Diagnostic Trees ----
    {
        "id": "dt_noise_diagnosis",
        "title": "Noise Diagnosis Decision Tree",
        "category": "diagnostic_trees",
        "keywords": ["noise", "diagnosis", "decision tree", "sound"],
        "content": (
            "STEP 1: When does the noise occur?\n"
            "  - At idle only -> Go to Engine Idle Noise\n"
            "  - Speed dependent (not RPM) -> Go to Wheel/Drivetrain Noise\n"
            "  - RPM dependent -> Go to Engine/Accessory Noise\n"
            "  - Only when braking -> Go to Brake Noise\n"
            "  - Only when turning -> Go to Steering/CV Noise\n\n"
            "STEP 2: What does it sound like?\n"
            "  - Whine/howl -> Bearing or pump cavitation\n"
            "  - Knock/tap -> Combustion or valvetrain\n"
            "  - Rattle -> Loose component or heat shield\n"
            "  - Grind -> Metal-on-metal contact\n"
            "  - Squeal -> Belt slip or brake indicator\n"
            "  - Click -> CV joint or relay\n\n"
            "STEP 3: Reproduce and isolate:\n"
            "  - Use a mechanics stethoscope on suspected components\n"
            "  - Remove serpentine belt to isolate belt-driven accessories\n"
            "  - Road test: note speed, RPM, load, and steering input"
        ),
    },
    {
        "id": "dt_misfire_diagnosis",
        "title": "Engine Misfire Diagnostic Tree",
        "category": "diagnostic_trees",
        "keywords": ["misfire", "rough idle", "P0300", "ignition", "coil"],
        "content": (
            "STEP 1: Read codes -- single cylinder or random?\n"
            "  - Single cylinder (P0301-P0308) -> Go to Step 2\n"
            "  - Random/multiple (P0300) -> Go to Step 4\n\n"
            "STEP 2: Swap ignition coil to different cylinder\n"
            "  - If misfire follows coil -> Replace coil\n"
            "  - If misfire stays -> Go to Step 3\n\n"
            "STEP 3: Check spark plug condition\n"
            "  - Fouled plug -> Check injector and compression\n"
            "  - Normal plug -> Compression test\n"
            "  - Low compression -> Head gasket or valve issue\n\n"
            "STEP 4: Random misfire checks\n"
            "  - Check for vacuum leaks (smoke test)\n"
            "  - Check fuel pressure and injector balance\n"
            "  - Check for intake gasket leaks\n"
            "  - Check MAF sensor (clean or replace)"
        ),
    },
    {
        "id": "dt_overheating",
        "title": "Engine Overheating Diagnostic Tree",
        "category": "diagnostic_trees",
        "keywords": ["overheat", "coolant", "radiator", "thermostat", "head gasket"],
        "content": (
            "STEP 1: Check coolant level\n"
            "  - Low -> Find the leak (pressure test system)\n"
            "  - Full -> Go to Step 2\n\n"
            "STEP 2: Check cooling fans\n"
            "  - Not running at temp -> Check relay, fuse, fan motor\n"
            "  - Running -> Go to Step 3\n\n"
            "STEP 3: Check thermostat\n"
            "  - Feel upper hose: should be hot when at temp\n"
            "  - Cold hose = stuck-closed thermostat\n"
            "  - Hot hose -> Go to Step 4\n\n"
            "STEP 4: Check for head gasket failure\n"
            "  - Bubbles in coolant overflow\n"
            "  - White exhaust smoke\n"
            "  - Oil milkshake on dipstick/oil cap\n"
            "  - Combustion gas test (block test) on coolant"
        ),
    },

    # ---- Repair Procedures ----
    {
        "id": "rp_brake_pad_replacement",
        "title": "Brake Pad Replacement Overview",
        "category": "repair_procedures",
        "keywords": ["brake pad", "replace", "rotor", "caliper", "DIY"],
        "content": (
            "Difficulty: DIY-friendly (beginner-intermediate)\n"
            "Time: 1-2 hours per axle\n"
            "Tools: Jack, jack stands, lug wrench, C-clamp, "
            "brake caliper tool, torque wrench\n\n"
            "PROCEDURE:\n"
            "1. Loosen lug nuts, raise vehicle, remove wheel\n"
            "2. Remove caliper bolts (usually 2 slide pins)\n"
            "3. Support caliper (don't hang by brake hose)\n"
            "4. Remove old pads, check rotor thickness\n"
            "5. Compress piston with C-clamp (open bleeder first on rear)\n"
            "6. Install new pads with anti-rattle hardware\n"
            "7. Reinstall caliper, torque bolts to spec\n"
            "8. Pump brake pedal before driving!\n\n"
            "TIPS: Bed in new pads with 10 moderate stops from 35 mph. "
            "Replace hardware clips. Use brake-specific grease on slide pins."
        ),
    },
    {
        "id": "rp_belt_replacement",
        "title": "Serpentine Belt Replacement",
        "category": "repair_procedures",
        "keywords": ["serpentine belt", "replace", "tensioner", "routing"],
        "content": (
            "Difficulty: Beginner-Intermediate\n"
            "Time: 30-60 minutes\n"
            "Tools: Serpentine belt tool or breaker bar/socket\n\n"
            "PROCEDURE:\n"
            "1. Note belt routing (photo or diagram under hood)\n"
            "2. Release tensioner with tool (direction varies by vehicle)\n"
            "3. Slip belt off one pulley while tensioner is released\n"
            "4. Route new belt per diagram (ribbed side on grooved pulleys)\n"
            "5. Release tensioner, belt seats automatically\n"
            "6. Verify all pulleys are tracked correctly\n"
            "7. Start engine, verify no squealing or misalignment\n\n"
            "Replace tensioner if: spring is weak, pulley wobbles, "
            "or bearing is noisy. Always spin idler pulleys by hand "
            "to check for roughness."
        ),
    },

    # ---- Symptom Patterns ----
    {
        "id": "sp_cold_start_noises",
        "title": "Cold Start Noise Patterns",
        "category": "symptom_patterns",
        "keywords": ["cold start", "morning", "startup noise", "goes away"],
        "content": (
            "Noises that appear at cold start and fade as the engine warms:\n\n"
            "TICKING (top of engine): Hydraulic lifters bleeding down "
            "overnight -- oil drains back. Usually resolves in 5-30 seconds. "
            "More common with old oil. Not typically harmful.\n\n"
            "RATTLING (front of engine): Timing chain tensioner needs oil "
            "pressure to take up slack. Brief rattle at startup is the "
            "chain slapping guides. Extended rattle = stretched chain.\n\n"
            "TICKING (exhaust area): Exhaust manifold leak at a cracked "
            "joint or gasket. Metal contracts when cold, expands to seal warm.\n\n"
            "SQUEALING (belt area): Cold belt is stiff and slips. Usually "
            "resolves in 30-60 seconds. Belt dressing is a temporary fix.\n\n"
            "KNOCK (deep): Piston slap from excessive clearance. Cold "
            "pistons are smaller. If it goes away warm, monitor but not urgent."
        ),
    },
    {
        "id": "sp_speed_dependent",
        "title": "Speed-Dependent Noise Patterns",
        "category": "symptom_patterns",
        "keywords": ["speed", "highway", "wheel", "tire", "drivetrain"],
        "content": (
            "Noises that change with vehicle speed (not engine RPM):\n\n"
            "HUMMING: Wheel bearing -- changes tone with turns. "
            "Right turn loads left bearing (increases if left is bad). "
            "Constant hum that doesn't change with turns = tire noise.\n\n"
            "ROARING: Aggressive tire tread pattern or uneven wear "
            "(cupping/scalloping from bad shocks). Rotate tires to test.\n\n"
            "CLICKING (low speed turns): Outer CV joint.\n\n"
            "VIBRATION (50-70 mph): Tire balance, bent wheel, or "
            "driveshaft balance/U-joint.\n\n"
            "WHINE (varies with accel/decel): Differential ring/pinion gear "
            "wear. Whines on acceleration = drive side. Coast = coast side.\n\n"
            "DRONE at specific speed: Could be exhaust resonance or "
            "driveshaft center bearing."
        ),
    },
    {
        "id": "sp_rpm_dependent",
        "title": "RPM-Dependent Noise Patterns",
        "category": "symptom_patterns",
        "keywords": ["rpm", "revving", "engine speed", "accessory"],
        "content": (
            "Noises that follow engine RPM regardless of vehicle speed:\n\n"
            "WHINE proportional to RPM: Accessory bearing (alternator, "
            "water pump, AC compressor, idler/tensioner pulley). "
            "Remove serpentine belt to isolate -- if noise stops, it's "
            "belt-driven. If noise continues, it's internal engine.\n\n"
            "TICK at all RPMs: Exhaust leak, injector noise, or "
            "valvetrain issue. Stethoscope test to pinpoint.\n\n"
            "KNOCK under load: Detonation (use higher octane fuel) "
            "or connecting rod bearing (stop driving immediately).\n\n"
            "RATTLE at idle, smooths at RPM: Loose heat shield, "
            "catalytic converter substrate, or exhaust component.\n\n"
            "WHISTLE at RPM: Vacuum/boost leak, PCV system issue."
        ),
    },
    {
        "id": "sp_transmission_noises",
        "title": "Transmission Noise Patterns",
        "category": "symptom_patterns",
        "keywords": ["transmission", "shift", "gear", "whine", "slipping"],
        "content": (
            "WHINE in all gears: Low transmission fluid, worn pump, "
            "or internal bearing failure.\n\n"
            "WHINE in specific gear: Worn gear teeth in that gear set.\n\n"
            "CLUNK on shift: Worn motor/transmission mounts or "
            "internal clutch pack issues.\n\n"
            "SHUDDER at 40-60 mph (light throttle): Torque converter "
            "clutch shudder -- fluid change may help, may need TCC.\n\n"
            "GRINDING shifting (manual): Synchronizer wear. Try "
            "double-clutching to confirm. Higher gears usually fail first.\n\n"
            "BUZZING in neutral: Input shaft bearing (manual trans).\n\n"
            "DELAYED engagement: Low fluid, worn clutch packs, or "
            "failing valve body solenoids."
        ),
    },
]


# ---------------------------------------------------------------------------
# KnowledgeBase class
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """
    Local RAG knowledge base with keyword + TF-IDF retrieval.
    No external ML libraries required.
    """

    def __init__(self, extra_chunks_dir: str | None = None):
        self._chunks: list[KnowledgeChunk] = []
        self._idf: dict[str, float] = {}
        self._doc_vectors: list[dict[str, float]] = []

        # Load built-in knowledge
        self._load_builtin()

        # Load any extra JSON files from disk
        if extra_chunks_dir:
            self._load_from_directory(extra_chunks_dir)

        # Build TF-IDF index
        self._build_index()

    def _load_builtin(self):
        """Load built-in knowledge chunks."""
        for entry in _BUILTIN_KNOWLEDGE:
            self._chunks.append(KnowledgeChunk(
                id=entry["id"],
                title=entry["title"],
                content=entry["content"],
                category=entry["category"],
                keywords=entry.get("keywords", []),
                vehicle_types=entry.get("vehicle_types", []),
                mileage_range=entry.get("mileage_range", ""),
            ))

    def _load_from_directory(self, dir_path: str):
        """Load additional knowledge chunks from JSON files in a directory."""
        path = Path(dir_path)
        if not path.exists():
            return

        for json_file in path.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    for entry in data:
                        self._chunks.append(KnowledgeChunk(
                            id=entry.get("id", json_file.stem),
                            title=entry.get("title", ""),
                            content=entry.get("content", ""),
                            category=entry.get("category", "custom"),
                            keywords=entry.get("keywords", []),
                            vehicle_types=entry.get("vehicle_types", []),
                            mileage_range=entry.get("mileage_range", ""),
                        ))
            except (json.JSONDecodeError, OSError):
                continue

    def _build_index(self):
        """Build TF-IDF index for all chunks."""
        # Tokenize all documents
        docs = []
        for chunk in self._chunks:
            text = f"{chunk.title} {chunk.content} {' '.join(chunk.keywords)}"
            tokens = _tokenize(text)
            docs.append(tokens)

        # Compute IDF
        n_docs = len(docs)
        df: dict[str, int] = {}
        for tokens in docs:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1

        self._idf = {
            token: math.log(n_docs / (count + 1)) + 1
            for token, count in df.items()
        }

        # Compute TF-IDF vectors
        self._doc_vectors = []
        for tokens in docs:
            tf = Counter(tokens)
            total = len(tokens) if tokens else 1
            vector = {
                token: (count / total) * self._idf.get(token, 1.0)
                for token, count in tf.items()
            }
            self._doc_vectors.append(vector)

    def retrieve(
        self,
        query: str,
        max_chunks: int = 5,
        category: str | None = None,
    ) -> list[KnowledgeChunk]:
        """
        Retrieve the most relevant knowledge chunks for a query.

        Args:
            query: Natural language query.
            max_chunks: Maximum chunks to return.
            category: Optional category filter.

        Returns:
            List of KnowledgeChunk with relevance scores, sorted by relevance.
        """
        if not query or not self._chunks:
            return []

        # Tokenize query
        query_tokens = _tokenize(query)
        query_tf = Counter(query_tokens)
        total = len(query_tokens) if query_tokens else 1
        query_vector = {
            token: (count / total) * self._idf.get(token, 1.0)
            for token, count in query_tf.items()
        }

        # Score each chunk
        scored: list[tuple[int, float]] = []
        for i, doc_vec in enumerate(self._doc_vectors):
            # Category filter
            if category and self._chunks[i].category != category:
                continue

            # Cosine similarity
            score = _cosine_similarity(query_vector, doc_vec)

            # Keyword bonus: boost if query tokens match chunk keywords
            keyword_bonus = 0.0
            chunk_keywords = set(
                kw.lower() for kw in self._chunks[i].keywords
            )
            for qt in query_tokens:
                if qt in chunk_keywords:
                    keyword_bonus += 0.1

            score += min(keyword_bonus, 0.3)  # Cap keyword bonus
            scored.append((i, score))

        # Sort by score
        scored.sort(key=lambda x: x[1], reverse=True)

        # Return top chunks
        results = []
        for idx, score in scored[:max_chunks]:
            chunk = self._chunks[idx]
            chunk.relevance = score
            results.append(chunk)

        return results

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


# ---------------------------------------------------------------------------
# Text processing helpers
# ---------------------------------------------------------------------------

# Common English stop words
_STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "should", "could", "may", "might", "can", "shall",
    "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "under", "again", "further", "then", "once",
    "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too",
    "very", "and", "but", "or", "if", "it", "its", "this", "that",
    "i", "me", "my", "we", "our", "you", "your", "he", "she",
    "they", "them", "their", "what", "which", "who", "whom",
}


def _tokenize(text: str) -> list[str]:
    """Tokenize text: lowercase, remove punctuation, remove stop words."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vectors."""
    if not vec_a or not vec_b:
        return 0.0

    # Dot product
    dot = sum(vec_a.get(k, 0) * vec_b.get(k, 0) for k in vec_a)

    # Magnitudes
    mag_a = math.sqrt(sum(v * v for v in vec_a.values()))
    mag_b = math.sqrt(sum(v * v for v in vec_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0

    return dot / (mag_a * mag_b)
