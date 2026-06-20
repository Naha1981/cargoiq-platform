"""
CargoIQ — Compliance Tools Router
===================================
  GET  /compliance-tools/classify-hs        — classify single cargo description
  POST /compliance-tools/classify-hs/{id}   — classify a specific shipment
  GET  /compliance-tools/liability-ledger   — Section 99(2) exposure report
  GET  /compliance-tools/liability/{name}   — drill into one importer's exposure
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from ..core.security import get_current_user_with_org
from ..services.hs_classifier_service import classify_hs_code, bulk_classify
from ..services.liability_tracker_service import (
    get_liability_ledger, get_importer_exposure
)

router = APIRouter(prefix="/compliance-tools", tags=["Compliance Tools"])
logger = logging.getLogger(__name__)


# ── HS Code Classifier ───────────────────────────────────────

class HSClassifyRequest(BaseModel):
    cargo_description:  str
    country_of_origin:  str = "CN"
    current_hs_code:    Optional[str] = None
    additional_context: Optional[str] = None


@router.post("/classify-hs")
async def classify_hs(
    body: HSClassifyRequest,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Suggest the correct SARS 8-digit HS code for a cargo description.

    Particularly valuable for:
      - Fine art / designer furniture (JLog profile) — 0% vs 45% duty gap
      - Solar / lithium batteries — DG classification + duty rate
      - Textiles — SARS's highest seizure category in 2023/24

    Returns: suggested code, duty rate estimate, risk level, alternative code
    if ambiguous, and specific action required before submission.

    This is a pre-submission advisory, not a binding tariff ruling.
    For high-risk classifications, recommend the operator obtain a BTR
    from SARS Customs before the declaration is submitted.
    """
    return await classify_hs_code(
        cargo_description=body.cargo_description,
        country_of_origin=body.country_of_origin,
        current_hs_code=body.current_hs_code,
        additional_context=body.additional_context,
    )


@router.post("/classify-hs/{shipment_id}")
async def classify_hs_for_shipment(
    shipment_id: str,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Run HS classification on a specific shipment using its cargo description.
    If a mismatch or high-risk classification is found, creates a compliance
    event for operator review.
    """
    return await bulk_classify(shipment_id, current_user["org_id"])


# ── Section 99(2) Personal Liability Tracker ─────────────────

@router.get("/liability-ledger")
async def liability_ledger(
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Section 99(2) Personal Liability Report.

    Shows every active importer the clearing agent has processed in the
    last 12 months, with an estimated duty exposure if that importer
    defaults or cannot be found during a SARS audit.

    Critical for:
      - Ghameeda Idalene (G Idalene Accounting) — personally liable
        for every shipment she signs as clearing agent
      - Any combined accounting + clearing firm
      - Insurance brokers calculating professional indemnity cover

    Importers flagged as RLA-suspended are marked CRITICAL — a suspended
    importer is already in SARS's crosshairs and an audit is likely.
    """
    return await get_liability_ledger(current_user["org_id"])


@router.get("/liability/{importer_name}")
async def importer_liability_detail(
    importer_name: str,
    current_user: dict = Depends(get_current_user_with_org),
):
    """Drill into one importer's shipment history and estimated exposure."""
    return await get_importer_exposure(current_user["org_id"], importer_name)


# ── Tariff Amendment Watch (zero-cost SARS tariff alerts) ───
# The manual, zero-API-cost alternative to a paid scraping
# service. Add a row whenever SARS publishes a tariff change —
# the HS Classifier picks it up immediately, no redeploy needed.

class TariffAmendmentCreate(BaseModel):
    effective_date:      str   # YYYY-MM-DD
    category:             str
    keywords:             List[str]
    hs_chapters:          List[str] = []
    change_description:   str
    source:                Optional[str] = None


@router.post("/tariff-amendments", status_code=201)
async def add_tariff_amendment(
    body: TariffAmendmentCreate,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Log a new SARS tariff amendment. Costs nothing — no scraping
    service, no API call. Takes 30 seconds: read the SARS notice,
    fill in the category and keywords, submit. The HS Classifier
    immediately starts flagging matching cargo descriptions.
    """
    from ..core.supabase_client import get_supabase_admin
    admin  = get_supabase_admin()
    record = body.model_dump()
    record["added_by"] = current_user.get("email", "unknown")
    result = admin.table("tariff_amendments").insert(record).execute()
    return result.data[0]


@router.get("/tariff-amendments")
async def list_tariff_amendments(
    current_user: dict = Depends(get_current_user_with_org),
):
    """List all logged tariff amendments, most recent first."""
    from ..core.supabase_client import get_supabase_admin
    admin  = get_supabase_admin()
    result = admin.table("tariff_amendments") \
        .select("*").order("effective_date", desc=True).execute()
    return result.data
