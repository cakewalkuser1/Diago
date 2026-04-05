"""
Fetch NHTSA recalls and complaints for a list of vehicles and populate the
technical_service_bulletins table in the local Diago database.

NHTSA provides two complementary free APIs:
  - Recalls:    https://api.nhtsa.gov/recalls/recallsByVehicle
  - Complaints: https://api.nhtsa.gov/complaints/complaintsByVehicle

Recalls map well to TSBs (they're safety-related service actions with campaign
numbers, affected VINs, component info, and fix summaries).  Complaints provide
additional symptom/component context.

This script writes recalls to technical_service_bulletins and stores the NHTSA
campaign number as nhtsa_id, the NHTSA components field as component, and the
consequence + remedy text as the summary. The remedy text is the closest NHTSA
has to a repair procedure summary.

Usage:
    python scripts/fetch_nhtsa_recalls.py
    python scripts/fetch_nhtsa_recalls.py --makes honda toyota ford --years 2018 2019 2020
    python scripts/fetch_nhtsa_recalls.py --vehicle-file vehicles.csv  # CSV: year,make,model

Options:
    --makes     Space-separated list of makes (default: top 20 by volume)
    --models    Space-separated models to filter to (default: all models per make)
    --years     Space-separated model years (default: 2015-2024)
    --vehicle-file  Path to a CSV file with columns: year, make, model
    --db        Path to the SQLite database (default: auto-detect from config)
    --dry-run   Print records without writing to database
    --delay     Seconds between API requests (default: 0.5, be kind to NHTSA)
"""

import argparse
import csv
import logging
import sys
import time
from pathlib import Path
from typing import Iterator

import httpx

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fetch_nhtsa")

NHTSA_BASE = "https://api.nhtsa.gov"

# Default target makes (ordered by US market share)
DEFAULT_MAKES = [
    "Ford", "Chevrolet", "Toyota", "Honda", "Ram", "Jeep", "GMC",
    "Nissan", "Subaru", "Hyundai", "Kia", "Volkswagen", "BMW", "Mercedes-Benz",
    "Audi", "Dodge", "Chrysler", "Buick", "Cadillac", "Lexus",
]

DEFAULT_YEARS = list(range(2015, 2025))


# ---------------------------------------------------------------------------
# NHTSA API helpers
# ---------------------------------------------------------------------------

def fetch_recalls(make: str, model: str, year: int, client: httpx.Client, delay: float = 0.5) -> list[dict]:
    """Fetch recall records for a single year/make/model from NHTSA."""
    url = f"{NHTSA_BASE}/recalls/recallsByVehicle"
    params = {"make": make, "model": model, "modelYear": year}
    try:
        r = client.get(url, params=params, timeout=20.0)
        r.raise_for_status()
        data = r.json()
        results = data.get("results") or data.get("Results") or []
        time.sleep(delay)
        return results if isinstance(results, list) else []
    except httpx.HTTPStatusError as e:
        logger.warning("HTTP %s for %s %s %s", e.response.status_code, year, make, model)
        return []
    except Exception as e:
        logger.warning("Error fetching recalls for %s %s %s: %s", year, make, model, e)
        return []


def fetch_models_for_make_year(make: str, year: int, client: httpx.Client) -> list[str]:
    """Return a list of model names for a given make and year from NHTSA vPIC."""
    url = f"https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/{make}/modelyear/{year}"
    try:
        r = client.get(url, params={"format": "json"}, timeout=15.0)
        r.raise_for_status()
        data = r.json()
        results = data.get("Results") or []
        return [r.get("Model_Name", "") for r in results if r.get("Model_Name")]
    except Exception as e:
        logger.debug("Could not fetch models for %s %s: %s", make, year, e)
        return []


# ---------------------------------------------------------------------------
# Record transformation
# ---------------------------------------------------------------------------

def recall_to_tsb_dict(recall: dict, make: str, model: str, year: int) -> dict:
    """
    Map an NHTSA recall result to the TSB record format expected by
    DatabaseManager.insert_tsb_extended().
    """
    campaign = recall.get("NHTSACampaignNumber") or recall.get("nhtsaCampaignNumber") or ""
    component = recall.get("Component") or recall.get("component") or ""
    consequence = recall.get("Consequence") or recall.get("consequence") or ""
    remedy = recall.get("Remedy") or recall.get("remedy") or ""
    summary = recall.get("Summary") or recall.get("summary") or ""

    # Build summary from consequence + remedy (more useful than raw summary alone)
    full_summary = " | ".join(filter(None, [summary, consequence, remedy]))[:2000]

    report_date = recall.get("ReportReceivedDate") or recall.get("reportReceivedDate") or ""
    # Normalize date: NHTSA returns formats like "20190315" or "2019-03-15"
    bulletin_date = ""
    if report_date:
        rd = str(report_date).replace("/", "-").strip()
        if len(rd) == 8 and rd.isdigit():
            bulletin_date = f"{rd[:4]}-{rd[4:6]}-{rd[6:8]}"
        else:
            bulletin_date = rd[:10]

    return {
        "model_year": year,
        "make": make,
        "model": model,
        "component": component[:255],
        "summary": full_summary,
        "nhtsa_id": campaign,
        "document_id": campaign,
        "bulletin_date": bulletin_date,
        "affected_mileage_range": "",
        "affected_codes": "",
        "document_url": (
            f"https://www.nhtsa.gov/vehicle/{year}/{make.replace(' ', '%20')}"
            f"/{model.replace(' ', '%20')}/PC/consumer"
        ),
        "manufacturer_id": recall.get("ManufacturerCampaignNumber") or "",
        "severity": _severity_from_recall(recall),
        "source": "nhtsa",
    }


def _severity_from_recall(recall: dict) -> str:
    """Heuristically determine severity from recall consequence text."""
    consequence = (recall.get("Consequence") or "").lower()
    if any(w in consequence for w in ["crash", "fire", "injury", "death", "fatal"]):
        return "critical"
    if any(w in consequence for w in ["accident", "loss of control", "brake fail"]):
        return "high"
    if any(w in consequence for w in ["may", "can", "could", "risk"]):
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Vehicle list generators
# ---------------------------------------------------------------------------

def vehicles_from_args(makes: list[str], models: list[str] | None, years: list[int], client: httpx.Client) -> Iterator[tuple[int, str, str]]:
    """Yield (year, make, model) tuples from CLI arguments."""
    for make in makes:
        for year in years:
            if models:
                for model in models:
                    yield year, make, model
            else:
                fetched_models = fetch_models_for_make_year(make, year, client)
                if not fetched_models:
                    logger.debug("No models found for %s %s via vPIC", make, year)
                    continue
                for model in fetched_models:
                    yield year, make, model


def vehicles_from_csv(csv_path: str) -> Iterator[tuple[int, str, str]]:
    """Yield (year, make, model) tuples from a CSV file (columns: year, make, model)."""
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                year = int(row.get("year") or row.get("Year") or 0)
                make = (row.get("make") or row.get("Make") or "").strip()
                model = (row.get("model") or row.get("Model") or "").strip()
                if year and make and model:
                    yield year, make, model
            except (ValueError, KeyError):
                continue


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch NHTSA recalls into Diago TSB database")
    parser.add_argument("--makes", nargs="+", default=None, help="List of vehicle makes")
    parser.add_argument("--models", nargs="+", default=None, help="Filter to specific models")
    parser.add_argument("--years", nargs="+", type=int, default=None, help="Model years to fetch")
    parser.add_argument("--vehicle-file", default=None, help="CSV file with year,make,model columns")
    parser.add_argument("--db", default=None, help="Path to SQLite database (auto-detected if omitted)")
    parser.add_argument("--dry-run", action="store_true", help="Print records without writing")
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between API requests")
    parser.add_argument("--limit", type=int, default=0, help="Max records to insert (0 = unlimited)")
    args = parser.parse_args()

    # Resolve DB path
    db_path = args.db
    if not db_path:
        try:
            from core.config import get_settings
            db_path = get_settings().db_path
        except Exception:
            db_path = Path.home() / "AppData" / "Roaming" / "Diago" / "auto_audio.db"

    logger.info("Using database: %s", db_path)

    db = None
    if not args.dry_run:
        from database.db_manager import DatabaseManager
        db = DatabaseManager(str(db_path))
        db.initialize()
        before = db.get_tsb_count()
        logger.info("TSB count before fetch: %d", before)

    makes = args.makes or DEFAULT_MAKES
    years = args.years or DEFAULT_YEARS

    total_fetched = 0
    total_inserted = 0
    seen_campaigns: set[str] = set()  # deduplicate by campaign number

    with httpx.Client() as client:
        if args.vehicle_file:
            vehicle_iter = vehicles_from_csv(args.vehicle_file)
        else:
            vehicle_iter = vehicles_from_args(makes, args.models, years, client)

        for year, make, model in vehicle_iter:
            recalls = fetch_recalls(make, model, year, client, delay=args.delay)
            if not recalls:
                continue

            logger.info("  %d %s %s: %d recall(s)", year, make, model, len(recalls))
            for recall in recalls:
                campaign = recall.get("NHTSACampaignNumber") or recall.get("nhtsaCampaignNumber") or ""
                if campaign and campaign in seen_campaigns:
                    continue  # same campaign already written for another model year/trim
                if campaign:
                    seen_campaigns.add(campaign)

                record = recall_to_tsb_dict(recall, make, model, year)
                total_fetched += 1

                if args.dry_run:
                    print(f"[DRY RUN] {record['model_year']} {record['make']} {record['model']} "
                          f"| {record['nhtsa_id']} | {record['component'][:60]} | {record['severity']}")
                else:
                    try:
                        db.insert_tsb_extended(**record)
                        total_inserted += 1
                    except Exception as e:
                        logger.debug("Insert failed for campaign %s: %s", campaign, e)

                if args.limit and total_inserted >= args.limit:
                    logger.info("Reached limit of %d records", args.limit)
                    break
            else:
                continue
            break  # inner loop hit limit

    if args.dry_run:
        logger.info("Dry run complete. Would have inserted %d records.", total_fetched)
    else:
        after = db.get_tsb_count()
        logger.info(
            "Done. Fetched %d recall records. TSB count: %d → %d (+%d)",
            total_fetched, before, after, after - before,
        )
        db.close()


if __name__ == "__main__":
    main()
