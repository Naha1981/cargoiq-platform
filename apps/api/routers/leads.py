"""
CargoIQ — Leads CRM Router
===========================
Stores Deal Hunter output (10 leads/night from Base44 Super Agent)
and tracks each lead through the sales pipeline.

Pipeline stages:
  new → messaged → replied → call_booked →
  audit_running → proposal_sent → won / lost / not_qualified
"""
import logging
from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin

router = APIRouter(prefix="/leads", tags=["Leads CRM"])
logger = logging.getLogger(__name__)

VALID_STATUSES = [
    "new", "messaged", "replied", "call_booked",
    "audit_running", "proposal_sent", "won", "lost", "not_qualified"
]

VALID_TYPES = [
    "3pl_fleet", "importer_wholesaler",
    "cross_border_trucker", "clearing_agent", "other"
]


class LeadCreate(BaseModel):
    company_name:            str
    company_website:         Optional[str] = None
    company_type:            Optional[str] = None
    location:                Optional[str] = None
    contact_name:            Optional[str] = None
    contact_title:           Optional[str] = None
    linkedin_url:            Optional[str] = None
    email:                   Optional[str] = None
    phone:                   Optional[str] = None
    primary_pain:            Optional[str] = None
    pain_estimate_zar_low:   Optional[float] = None
    pain_estimate_zar_high:  Optional[float] = None
    cargoiq_modules:         Optional[List[str]] = None
    hook:                    Optional[str] = None
    dm_draft:                Optional[str] = None
    source:                  str = "deal_hunter"
    notes:                   Optional[str] = None


class LeadStatusUpdate(BaseModel):
    status: str
    notes:  Optional[str] = None


@router.get("/")
async def list_leads(
    status:       Optional[str] = Query(None),
    company_type: Optional[str] = Query(None),
    source:       Optional[str] = Query(None),
    page:         int = Query(1, ge=1),
    limit:        int = Query(25, ge=1, le=100),
    current_user: dict = Depends(get_current_user_with_org),
):
    """List all leads, filterable by status/type/source."""
    admin  = get_supabase_admin()
    offset = (page - 1) * limit

    q = admin.table("leads").select(
        "id,company_name,company_type,location,contact_name,"
        "contact_title,linkedin_url,primary_pain,"
        "pain_estimate_zar_low,pain_estimate_zar_high,"
        "cargoiq_modules,status,source,messaged_at,replied_at,"
        "call_booked_at,created_at"
    )
    if status:       q = q.eq("status", status)
    if company_type: q = q.eq("company_type", company_type)
    if source:       q = q.eq("source", source)

    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    count  = admin.table("leads").select("id", count="exact")
    if status:       count = count.eq("status", status)
    if company_type: count = count.eq("company_type", company_type)
    total = count.execute()

    return {
        "data":     result.data,
        "total":    total.count or 0,
        "page":     page,
        "limit":    limit,
        "has_more": (offset + limit) < (total.count or 0),
    }


@router.get("/pipeline-summary")
async def pipeline_summary(current_user: dict = Depends(get_current_user_with_org)):
    """Counts by status — the Deal Hunter funnel at a glance."""
    admin  = get_supabase_admin()
    rows   = admin.table("leads").select("status").execute()

    summary: dict = {s: 0 for s in VALID_STATUSES}
    total_pain_low  = 0.0
    total_pain_high = 0.0

    for r in (rows.data or []):
        s = r.get("status", "new")
        summary[s] = summary.get(s, 0) + 1

    # Total addressable pain across all leads
    pain = admin.table("leads").select("pain_estimate_zar_low,pain_estimate_zar_high").execute()
    for r in (pain.data or []):
        total_pain_low  += float(r.get("pain_estimate_zar_low")  or 0)
        total_pain_high += float(r.get("pain_estimate_zar_high") or 0)

    won_leads = admin.table("leads").select("pain_estimate_zar_low,pain_estimate_zar_high") \
        .eq("status", "won").execute()
    won_pain = sum(float(r.get("pain_estimate_zar_low") or 0) for r in (won_leads.data or []))

    return {
        "by_status":           summary,
        "total_leads":         sum(summary.values()),
        "total_pain_zar_low":  round(total_pain_low, 2),
        "total_pain_zar_high": round(total_pain_high, 2),
        "won_count":           summary.get("won", 0),
        "won_pain_zar":        round(won_pain, 2),
        "conversion_rate_pct": round(
            summary.get("won", 0) / max(sum(summary.values()), 1) * 100, 1
        ),
    }


@router.get("/{lead_id}")
async def get_lead(lead_id: str, current_user: dict = Depends(get_current_user_with_org)):
    admin  = get_supabase_admin()
    result = admin.table("leads").select("*").eq("id", lead_id).single().execute()
    if not result.data:
        raise HTTPException(404, "Lead not found")
    return result.data


@router.post("/", status_code=201)
async def create_lead(
    body: LeadCreate,
    current_user: dict = Depends(get_current_user_with_org),
):
    """Create a single lead (also called by Deal Hunter batch import)."""
    admin  = get_supabase_admin()
    record = body.model_dump(exclude_none=True)
    record["status"] = "new"
    result = admin.table("leads").insert(record).execute()
    return result.data[0]


@router.post("/batch", status_code=201)
async def batch_import_leads(
    leads: List[LeadCreate] = Body(...),
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Import a batch of leads from the Deal Hunter nightly report.
    Skips duplicates (same company_name + contact_name).
    """
    admin   = get_supabase_admin()
    created = 0
    skipped = 0

    for lead in leads:
        # Check for duplicate
        existing = admin.table("leads") \
            .select("id") \
            .ilike("company_name", lead.company_name) \
            .execute()
        if existing.data:
            skipped += 1
            continue

        record = lead.model_dump(exclude_none=True)
        record["status"] = "new"
        admin.table("leads").insert(record).execute()
        created += 1

    logger.info(f"Lead batch import: {created} created, {skipped} skipped (duplicates)")
    return {"created": created, "skipped": skipped}


@router.patch("/{lead_id}/status")
async def update_lead_status(
    lead_id: str,
    body:    LeadStatusUpdate,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Advance a lead through the pipeline.
    Automatically sets timestamps (messaged_at, replied_at, etc.)
    """
    if body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status. Valid: {VALID_STATUSES}")

    admin  = get_supabase_admin()
    now    = datetime.utcnow().isoformat()

    update = {"status": body.status}
    if body.notes:
        update["notes"] = body.notes

    # Auto-set timestamps
    timestamp_map = {
        "messaged":    "messaged_at",
        "replied":     "replied_at",
        "call_booked": "call_booked_at",
    }
    if body.status in timestamp_map:
        update[timestamp_map[body.status]] = now

    result = admin.table("leads").update(update).eq("id", lead_id).execute()
    if not result.data:
        raise HTTPException(404, "Lead not found")

    logger.info(f"Lead {lead_id} status → {body.status}")
    return result.data[0]


@router.patch("/{lead_id}")
async def update_lead(
    lead_id: str,
    body:    dict = Body(...),
    current_user: dict = Depends(get_current_user_with_org),
):
    """Update any lead fields (notes, DM draft, contact info, etc.)."""
    admin  = get_supabase_admin()
    # Strip protected fields
    body.pop("id", None)
    body.pop("created_at", None)

    result = admin.table("leads").update(body).eq("id", lead_id).execute()
    if not result.data:
        raise HTTPException(404, "Lead not found")
    return result.data[0]


@router.delete("/{lead_id}")
async def delete_lead(lead_id: str, current_user: dict = Depends(get_current_user_with_org)):
    admin = get_supabase_admin()
    admin.table("leads").delete().eq("id", lead_id).execute()
    return {"message": "Lead deleted"}
