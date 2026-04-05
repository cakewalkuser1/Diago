"""
Technical Service Bulletins API Routes
Search TSBs by vehicle (year/make/model) and component; import from CSV.
"""

import csv
import io
import logging
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TSBItem(BaseModel):
    """Single TSB record."""
    id: int
    model_year: int
    make: str
    model: str
    component: str = ""
    summary: str = ""
    nhtsa_id: str = ""
    document_id: str = ""
    # Extended fields (populated by fetch_nhtsa_recalls.py and insert_tsb_extended)
    bulletin_date: str = ""
    affected_mileage_range: str = ""
    affected_codes: str = ""
    document_url: str = ""
    manufacturer_id: str = ""
    severity: str = "medium"
    source: str = "nhtsa"
    created_at: str = ""


class TSBSearchResponse(BaseModel):
    """TSB search results."""
    count: int
    results: list[TSBItem]


class TSBImportResponse(BaseModel):
    """Result of CSV import."""
    imported: int
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/search", response_model=TSBSearchResponse)
async def search_tsbs(
    model_year: int | None = Query(None, description="Model year"),
    make: str | None = Query(None, description="Make (partial match)"),
    model: str | None = Query(None, description="Model (partial match)"),
    component: str | None = Query(None, description="Component (partial match)"),
    limit: int = Query(100, ge=1, le=500),
):
    """Search technical service bulletins by vehicle and optional component."""
    db = get_db_manager()
    rows = db.search_tsbs(
        model_year=model_year,
        make=make or None,
        model=model or None,
        component=component or None,
        limit=limit,
    )
    results = [
        TSBItem(
            id=r["id"],
            model_year=r["model_year"],
            make=r["make"],
            model=r["model"],
            component=r.get("component") or "",
            summary=r.get("summary") or "",
            nhtsa_id=r.get("nhtsa_id") or "",
            document_id=r.get("document_id") or "",
            bulletin_date=r.get("bulletin_date") or "",
            affected_mileage_range=r.get("affected_mileage_range") or "",
            affected_codes=r.get("affected_codes") or "",
            document_url=r.get("document_url") or "",
            manufacturer_id=r.get("manufacturer_id") or "",
            severity=r.get("severity") or "medium",
            source=r.get("source") or "nhtsa",
            created_at=r.get("created_at") or "",
        )
        for r in rows
    ]
    return TSBSearchResponse(count=len(results), results=results)


@router.get("/count")
async def get_tsb_count():
    """Return total number of TSB records in the database."""
    db = get_db_manager()
    return {"count": db.get_tsb_count()}


@router.post("/import", response_model=TSBImportResponse)
async def import_tsb_csv(file: UploadFile = File(...)):
    """
    Import TSBs from a CSV file.

    Expected columns: model_year, make, model, component, summary, nhtsa_id, document_id
    (component, summary, nhtsa_id, document_id optional).
    Header row required.
    """
    db = get_db_manager()
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload a CSV file")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    fieldnames_lower = [f.strip().lower().replace(" ", "_") for f in (reader.fieldnames or [])]
    if not reader.fieldnames or "make" not in fieldnames_lower or "model" not in fieldnames_lower:
        raise HTTPException(
            status_code=400,
            detail="CSV must have columns: make, model, and model_year (or Model Year).",
        )
    year_ok = "model_year" in fieldnames_lower or "modelyear" in "".join(fieldnames_lower)
    if not year_ok:
        for f in reader.fieldnames or []:
            if "year" in f.lower():
                year_ok = True
                break
    if not year_ok:
        raise HTTPException(
            status_code=400,
            detail="CSV must include a model year column (model_year or Model Year).",
        )

    imported = 0
    errors = []
    for i, row in enumerate(reader):
        try:
            year_val = row.get("model_year") or row.get("Model Year") or ""
            make_val = row.get("make") or row.get("Make") or ""
            model_val = row.get("model") or row.get("Model") or ""
            if not year_val or not make_val or not model_val:
                errors.append(f"Row {i + 2}: missing year/make/model")
                continue
            year = int(year_val)
            if year < 1990 or year > 2030:
                errors.append(f"Row {i + 2}: invalid year {year_val}")
                continue
        except ValueError:
            errors.append(f"Row {i + 2}: invalid model_year")
            continue

        component = row.get("component") or row.get("Component") or row.get("NHTSA Components") or ""
        summary = row.get("summary") or row.get("Summary") or ""
        nhtsa_id = row.get("nhtsa_id") or row.get("NHTSA ID Number") or row.get("nhtsaId") or ""
        document_id = row.get("document_id") or row.get("TSB/Document ID") or row.get("documentId") or ""

        try:
            db.insert_tsb(
                model_year=year,
                make=make_val.strip(),
                model=model_val.strip(),
                component=component.strip(),
                summary=summary.strip(),
                nhtsa_id=str(nhtsa_id).strip(),
                document_id=str(document_id).strip(),
            )
            imported += 1
        except Exception as e:
            errors.append(f"Row {i + 2}: {e}")

    return TSBImportResponse(imported=imported, errors=errors[:50])
