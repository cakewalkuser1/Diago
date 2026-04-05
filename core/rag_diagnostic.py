"""
RAG (Retrieval-Augmented Generation) for diagnostic chat.
Provides ASE-aligned reference chunks so DiagBot answers are grounded in trusted procedures.
Uses in-memory curated chunks; optional pgvector/Chroma later.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Curated ASE-style diagnostic/safety procedures (citable guidance)
ASE_CURATED_CHUNKS = [
    {
        "title": "OBD-II code diagnosis steps",
        "body": "When diagnosing OBD-II codes: (1) Record the code(s) and freeze-frame data if available. (2) Clear codes and run a test drive to see if the code returns. (3) Follow the manufacturer's flow chart or service manual for that code. (4) Verify related sensors and wiring before replacing parts. Do not assume a code means replace the named component—it indicates the circuit or system range.",
    },
    {
        "title": "When to recommend a professional",
        "body": "Recommend a professional technician when: the repair requires lifting the vehicle or removing safety-critical components; the customer lacks tools or a safe workspace; the diagnosis points to hybrid/EV high-voltage systems, airbags, or steering/suspension structural work; or the customer is unsure about their ability to complete the repair safely.",
    },
    {
        "title": "Safe vehicle lifting",
        "body": "When lifting a vehicle: use only approved jack stands on a level, solid surface after raising with a floor jack. Never work under a vehicle supported only by a jack. Set the parking brake and chock the wheels. ASE best practice: use manufacturer-specified lift points and verify the vehicle is stable before going underneath.",
    },
    {
        "title": "Belt and pulley inspection",
        "body": "For belt drive noise: inspect the serpentine/accessory belt for cracks, glazing, and tension. Check all pulleys for smooth rotation and bearing noise. A chirp that increases with RPM often indicates a worn belt or misaligned pulley. Replace the belt per interval or if damaged; replace idler/tensioner pulleys if bearings are rough or noisy.",
    },
    {
        "title": "Battery and electrical safety",
        "body": "When working on battery or electrical systems: disconnect the negative cable first and reconnect it last. Avoid creating sparks near the battery. If testing with the engine running, keep clear of moving parts and the fan. For hybrid/EV, follow the manufacturer procedure to confirm the high-voltage system is disabled before any high-voltage contact.",
    },
]


@dataclass
class RAGChunk:
    title: str
    body: str
    source: str = "ase_curated"


# Minimum word-overlap score for a chunk to be considered relevant.
# Avoids attributing sources when only one common word matches (e.g. "the", "vehicle").
_MIN_RELEVANCE_SCORE = 2


def retrieve(query: str, context: dict | None, k: int = 5) -> list[RAGChunk]:
    """
    Return up to k relevant chunks for the user query and context.
    Uses simple keyword overlap for now; can be replaced with embedding similarity.
    Only returns chunks with score >= _MIN_RELEVANCE_SCORE so source attribution
    reflects actual relevance; avoids misleading "Based on: all 5" when few/none apply.
    """
    combined = (query or "") + " " + " ".join(
        str(v) for v in (context or {}).values() if v
    )
    combined_stripped = (combined or "").strip()
    if not combined_stripped:
        return []  # No query/context: don't attribute any sources
    combined_lower = combined_stripped.lower()
    scored = []
    for c in ASE_CURATED_CHUNKS:
        text = (c["title"] + " " + c["body"]).lower()
        score = sum(1 for w in combined_lower.split() if len(w) > 2 and w in text)
        scored.append((score, RAGChunk(title=c["title"], body=c["body"])))
    scored.sort(key=lambda x: -x[0])
    return [chunk for score, chunk in scored[:k] if score >= _MIN_RELEVANCE_SCORE]


def build_rag_prompt(
    chunks: list[RAGChunk],
    user_message: str,
    context: dict | None,
) -> str:
    """Build the reference block to append to the system prompt."""
    if not chunks:
        return ""
    parts = [
        "\n\nUse the following reference material (ASE-aligned procedures and repair guidance) when relevant:"
    ]
    for i, c in enumerate(chunks, 1):
        parts.append(f"\n--- [{c.title}] ---\n{c.body}")
    parts.append("\n--- End reference ---\nAnswer based on the above when it applies; otherwise use your training.")
    return "".join(parts)
