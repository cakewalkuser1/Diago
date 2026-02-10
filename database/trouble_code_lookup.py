"""
Trouble Code Lookup Module
Provides intelligent OBD-II code lookup, symptom-based search,
and mechanical class boost computation for the diagnostic pipeline.

Works with the trouble_code_definitions table populated from
database/obd2_codes.json (SAE J2012 pre-2002 + common generic codes).
"""

from dataclasses import dataclass, field


@dataclass
class CodeDefinition:
    """Represents a single OBD-II trouble code definition."""
    code: str
    description: str
    system: str
    subsystem: str
    mechanical_classes: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    severity: str = "medium"


# ---------------------------------------------------------------------------
# Single / batch lookup
# ---------------------------------------------------------------------------

def lookup_code(code: str, db_manager) -> CodeDefinition | None:
    """
    Look up a single OBD-II code from the database.

    Args:
        code: OBD-II code string (e.g. "P0301").
        db_manager: DatabaseManager instance.

    Returns:
        CodeDefinition or None if not found.
    """
    cursor = db_manager.connection.execute(
        "SELECT * FROM trouble_code_definitions WHERE code = ?",
        (code.upper(),),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return _row_to_definition(row)


def lookup_codes(codes: list[str], db_manager) -> list[CodeDefinition]:
    """
    Look up multiple OBD-II codes.

    Args:
        codes: List of code strings.
        db_manager: DatabaseManager instance.

    Returns:
        List of CodeDefinition for codes that were found.
    """
    if not codes:
        return []

    placeholders = ",".join("?" * len(codes))
    cursor = db_manager.connection.execute(
        f"SELECT * FROM trouble_code_definitions WHERE code IN ({placeholders})",
        [c.upper() for c in codes],
    )
    return [_row_to_definition(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Symptom-based search
# ---------------------------------------------------------------------------

def suggest_codes_for_symptoms(
    symptom_keywords: list[str],
    db_manager,
    limit: int = 20,
) -> list[CodeDefinition]:
    """
    Find codes whose symptom list matches any of the given keywords.

    Uses LIKE matching against the symptoms column (comma-separated keywords).

    Args:
        symptom_keywords: List of symptom keywords to search for.
        db_manager: DatabaseManager instance.
        limit: Maximum results to return.

    Returns:
        List of matching CodeDefinition objects, highest relevance first.
    """
    if not symptom_keywords:
        return []

    # Build OR conditions for each keyword
    conditions = []
    params = []
    for kw in symptom_keywords:
        kw_clean = kw.strip().lower()
        if kw_clean:
            conditions.append("LOWER(symptoms) LIKE ?")
            params.append(f"%{kw_clean}%")

    if not conditions:
        return []

    # Count how many keywords match each code (relevance ranking)
    # We use a UNION approach for simplicity
    where_clause = " OR ".join(conditions)
    cursor = db_manager.connection.execute(
        f"""SELECT *, (
                {' + '.join(f"(CASE WHEN LOWER(symptoms) LIKE ? THEN 1 ELSE 0 END)" for _ in symptom_keywords)}
            ) as relevance
            FROM trouble_code_definitions
            WHERE {where_clause}
            ORDER BY relevance DESC, severity DESC
            LIMIT ?""",
        [f"%{kw.strip().lower()}%" for kw in symptom_keywords] + params + [limit],
    )
    return [_row_to_definition(row) for row in cursor.fetchall()]


def search_codes(
    query: str,
    db_manager,
    limit: int = 30,
) -> list[CodeDefinition]:
    """
    Free-text search across code, description, symptoms, and subsystem.

    Args:
        query: Search string.
        db_manager: DatabaseManager instance.
        limit: Maximum results.

    Returns:
        List of matching CodeDefinition objects.
    """
    if not query or not query.strip():
        return []

    q = f"%{query.strip().lower()}%"
    cursor = db_manager.connection.execute(
        """SELECT * FROM trouble_code_definitions
           WHERE LOWER(code) LIKE ?
              OR LOWER(description) LIKE ?
              OR LOWER(symptoms) LIKE ?
              OR LOWER(subsystem) LIKE ?
           ORDER BY code
           LIMIT ?""",
        (q, q, q, q, limit),
    )
    return [_row_to_definition(row) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Mechanical class boosts for the diagnostic engine
# ---------------------------------------------------------------------------

def get_mechanical_class_boosts(
    user_codes: list[str],
    db_manager,
    boost_per_code: float = 0.15,
) -> dict[str, float]:
    """
    Compute additive score boosts per mechanical class based on the
    user's entered trouble codes.

    Each code maps to one or more mechanical classes. If a user enters
    multiple codes pointing to the same class, boosts stack (with
    diminishing returns).

    Args:
        user_codes: List of OBD-II codes from the user.
        db_manager: DatabaseManager instance.
        boost_per_code: Base boost value per code-class association.

    Returns:
        Dict mapping mechanical class -> total boost value.
    """
    if not user_codes:
        return {}

    definitions = lookup_codes(user_codes, db_manager)
    if not definitions:
        return {}

    # Accumulate boosts per class
    class_hits: dict[str, int] = {}
    for defn in definitions:
        for cls in defn.mechanical_classes:
            cls_clean = cls.strip()
            if cls_clean:
                class_hits[cls_clean] = class_hits.get(cls_clean, 0) + 1

    # Apply diminishing returns: boost = base * (1 + 0.5*(n-1))
    # So 1 code = 0.15, 2 codes = 0.225, 3 codes = 0.30, etc.
    boosts: dict[str, float] = {}
    for cls, count in class_hits.items():
        boosts[cls] = boost_per_code * (1.0 + 0.5 * (count - 1))

    return boosts


def get_severity_weight(codes: list[str], db_manager) -> float:
    """
    Return an aggregate severity weight (0.0 - 1.0) for a set of codes.
    Useful for confidence calibration.

    Severity mapping: low=0.25, medium=0.5, high=0.75, critical=1.0
    """
    if not codes:
        return 0.0

    definitions = lookup_codes(codes, db_manager)
    if not definitions:
        return 0.0

    severity_map = {
        "low": 0.25,
        "medium": 0.5,
        "high": 0.75,
        "critical": 1.0,
    }

    weights = [severity_map.get(d.severity, 0.5) for d in definitions]
    return max(weights)  # Use the most severe code's weight


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_definition(row) -> CodeDefinition:
    """Convert a database row to a CodeDefinition dataclass."""
    mc_raw = row["mechanical_classes"] or ""
    symptoms_raw = row["symptoms"] or ""

    return CodeDefinition(
        code=row["code"],
        description=row["description"],
        system=row["system"],
        subsystem=row["subsystem"] or "",
        mechanical_classes=[c.strip() for c in mc_raw.split(",") if c.strip()],
        symptoms=[s.strip() for s in symptoms_raw.split(",") if s.strip()],
        severity=row["severity"] or "medium",
    )


def get_code_count(db_manager) -> int:
    """Get total number of trouble code definitions in the database."""
    cursor = db_manager.connection.execute(
        "SELECT COUNT(*) FROM trouble_code_definitions"
    )
    return cursor.fetchone()[0]
