"""
Repair guide lookup (CarDiagn + charm.li).
Queries cloud PostgreSQL when REPAIR_GUIDES_DB_URL is set; otherwise returns empty.
No separate public API for charm.li — Diago backend is the only consumer.
"""

import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)


def _get_conn():
    url = (get_settings().repair_guides_db_url or "").strip()
    if not url:
        return None
    try:
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/") or "postgres",
            user=parsed.username,
            password=parsed.password,
        )
    except Exception as e:
        logger.warning("Repair guides DB connect failed: %s", e)
        return None


def search(
    q: str | None = None,
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
    source: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Search repair_guides by free text and/or vehicle.
    Returns list of {id, source, source_url, title, summary, vehicle_make, vehicle_model, year_min, year_max}.
    """
    conn = _get_conn()
    if not conn:
        return []
    try:
        cur = conn.cursor()
        conditions = []
        args = []
        if source:
            conditions.append("source = %s")
            args.append(source)
        if make:
            conditions.append("vehicle_make ILIKE %s")
            args.append(f"%{make}%")
        if model:
            conditions.append("vehicle_model ILIKE %s")
            args.append(f"%{model}%")
        if year is not None:
            conditions.append("(year_min IS NULL OR year_min <= %s) AND (year_max IS NULL OR year_max >= %s)")
            args.extend([year, year])
        if q:
            conditions.append("(title ILIKE %s OR summary ILIKE %s OR content ILIKE %s)")
            args.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        where = " AND ".join(conditions) if conditions else "1=1"
        args.append(limit)
        cur.execute(
            f"""
            SELECT id, source, source_url, title, summary, vehicle_make, vehicle_model, year_min, year_max
            FROM repair_guides
            WHERE {where}
            ORDER BY year_min DESC NULLS LAST
            LIMIT %s
            """,
            args,
        )
        rows = cur.fetchall()
        cur.close()
        return [
            {
                "id": r[0],
                "source": r[1],
                "source_url": r[2],
                "title": r[3],
                "summary": r[4],
                "vehicle_make": r[5],
                "vehicle_model": r[6],
                "year_min": r[7],
                "year_max": r[8],
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Repair guides search failed: %s", e)
        return []
    finally:
        conn.close()


def for_diagnosis(
    symptoms_summary: str | None = None,
    make: str | None = None,
    model: str | None = None,
    year: int | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return a few relevant guides for the current diagnosis context."""
    return search(
        q=symptoms_summary,
        make=make,
        model=model,
        year=year,
        limit=limit,
    )
