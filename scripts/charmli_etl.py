"""
Charm.li ETL: load crawled records into repair_guides table (PostgreSQL).
Reads REPAIR_GUIDES_DB_URL or CARDIAGN_DB_URL from env. If not set, prints records as JSON.
Usage:
  python -m scripts.charmli_crawler --json | python -m scripts.charmli_etl
  or: python -m scripts.charmli_etl --crawl (run crawler and load in one go)
"""

import json
import os
import sys

def _get_conn():
    url = os.environ.get("REPAIR_GUIDES_DB_URL") or os.environ.get("CARDIAGN_DB_URL")
    if not url:
        return None
    try:
        import psycopg2
        from urllib.parse import urlparse
        parsed = urlparse(url)
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            dbname=parsed.path.lstrip("/") or "postgres",
            user=parsed.username,
            password=parsed.password,
        )
        return conn
    except Exception as e:
        print("DB connect failed:", e, file=sys.stderr)
        return None


def upsert_records(conn, records: list[dict]) -> int:
    cur = conn.cursor()
    n = 0
    for r in records:
        cur.execute(
            """
            INSERT INTO repair_guides (source, source_url, title, summary, content, vehicle_make, vehicle_model, year_min, year_max, category, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (source, source_url) DO UPDATE SET
                title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                content = EXCLUDED.content,
                vehicle_make = EXCLUDED.vehicle_make,
                vehicle_model = EXCLUDED.vehicle_model,
                year_min = EXCLUDED.year_min,
                year_max = EXCLUDED.year_max,
                category = EXCLUDED.category,
                updated_at = NOW()
            """,
            (
                r.get("source", "charm_li"),
                r["source_url"],
                r.get("title", ""),
                r.get("summary"),
                r.get("content"),
                r.get("vehicle_make"),
                r.get("vehicle_model"),
                r.get("year_min"),
                r.get("year_max"),
                r.get("category"),
            ),
        )
        n += 1
    conn.commit()
    cur.close()
    return n


def main():
    records = []
    if "--crawl" in sys.argv:
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from charmli_crawler import run_crawl
        records = run_crawl(delay=1.0, max_makes=None)
    else:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    if not records:
        print("No records to load.", file=sys.stderr)
        return
    conn = _get_conn()
    if not conn:
        print("REPAIR_GUIDES_DB_URL (or CARDIAGN_DB_URL) not set; skipping DB write.", file=sys.stderr)
        json.dump(records, sys.stdout, indent=2)
        return
    n = upsert_records(conn, records)
    conn.close()
    print(f"Upserted {n} records.", file=sys.stderr)


if __name__ == "__main__":
    main()
