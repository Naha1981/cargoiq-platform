"""
CargoIQ — CarrierInvoice Auditor Router
Upload carrier invoices, manage negotiated rate cards,
view overcharge findings, generate dispute notices.
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..services.carrier_audit_service import (
    process_carrier_invoice_upload,
    generate_dispute_notice_html,
)

router = APIRouter(prefix="/carrier-audit", tags=["Carrier Invoice Auditor"])
logger = logging.getLogger(__name__)


# ── Rate cards ───────────────────────────────────────────────

class RateCardInput(BaseModel):
    carrier_name: str
    charge_type:  str   # ocean_freight | air_freight | baf | caf | thc | documentation | demurrage | detention | other
    lane:         Optional[str] = None
    unit:         str = "per_shipment"
    agreed_rate:  float
    currency:     str = "USD"
    valid_from:   Optional[str] = None  # YYYY-MM-DD
    valid_to:     Optional[str] = None
    notes:        Optional[str] = None


@router.get("/rate-cards")
async def list_rate_cards(
    carrier: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    q = admin.table("carrier_rate_cards").select("*").eq("org_id", org_id)
    if carrier:
        q = q.ilike("carrier_name", carrier)
    result = q.order("carrier_name").order("charge_type").execute()
    return result.data


@router.post("/rate-cards", status_code=201)
async def create_rate_card(
    body: RateCardInput,
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    valid_charge_types = [
        "ocean_freight","air_freight","baf","caf","thc",
        "documentation","demurrage","detention","other"
    ]
    if body.charge_type not in valid_charge_types:
        raise HTTPException(400, f"charge_type must be one of {valid_charge_types}")

    record = body.model_dump(exclude_none=True)
    record["org_id"] = org_id
    if not record.get("valid_from"):
        record["valid_from"] = datetime.utcnow().date().isoformat()

    result = admin.table("carrier_rate_cards").insert(record).execute()
    return result.data[0]


@router.delete("/rate-cards/{rate_card_id}")
async def delete_rate_card(
    rate_card_id: str,
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    admin.table("carrier_rate_cards").delete() \
        .eq("id", rate_card_id).eq("org_id", org_id).execute()
    return {"message": "Rate card deleted"}


# ── Invoice upload + audit ──────────────────────────────────

@router.post("/upload")
async def upload_carrier_invoice(
    file: UploadFile = File(...),
    shipment_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Upload a carrier invoice PDF. CargoIQ extracts every line item,
    compares against your rate cards, and flags overcharges.
    """
    if not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise HTTPException(400, "Only PDF or image files are supported")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "File too large (max 25MB)")

    org_id = current_user["org_id"]
    result = await process_carrier_invoice_upload(
        org_id=org_id,
        file_content=content,
        filename=file.filename,
        shipment_id=shipment_id,
    )

    if result.get("status") == "error":
        raise HTTPException(422, result.get("error", "Extraction failed"))

    return result


# ── List + detail ────────────────────────────────────────────

@router.get("/")
async def list_carrier_audits(
    status: Optional[str] = Query(None),
    page:   int = Query(1, ge=1),
    limit:  int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    q = admin.table("carrier_invoice_audits") \
        .select("id,carrier_name,invoice_number,invoice_currency,invoice_total,"
                "agreed_total,variance_total,variance_zar,status,dispute_generated,created_at") \
        .eq("org_id", org_id)
    if status:
        q = q.eq("status", status)

    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    count  = admin.table("carrier_invoice_audits").select("id", count="exact") \
        .eq("org_id", org_id).execute()

    return {
        "data":     result.data,
        "total":    count.count or 0,
        "page":     page,
        "limit":    limit,
        "has_more": (offset + limit) < (count.count or 0),
    }


@router.get("/summary")
async def carrier_audit_summary(
    current_user: dict = Depends(get_current_user_with_org)
):
    """Total overcharges recovered/identified — feeds the Savings Certificate."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("carrier_invoice_audits") \
        .select("status,variance_zar") \
        .eq("org_id", org_id).execute()

    rows = result.data or []
    total_overcharge_zar = sum(
        float(r.get("variance_zar") or 0) for r in rows
        if r["status"] == "overcharge_detected" and (r.get("variance_zar") or 0) > 0
    )
    return {
        "invoices_audited":      len(rows),
        "overcharges_found":     sum(1 for r in rows if r["status"] == "overcharge_detected"),
        "clean_invoices":        sum(1 for r in rows if r["status"] == "clean"),
        "no_rate_card":          sum(1 for r in rows if r["status"] == "no_rate_card"),
        "total_overcharge_zar":  round(total_overcharge_zar, 2),
    }


@router.get("/{audit_id}")
async def get_carrier_audit(
    audit_id: str,
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    result = admin.table("carrier_invoice_audits").select("*") \
        .eq("id", audit_id).eq("org_id", org_id).single().execute()
    if not result.data:
        raise HTTPException(404, "Audit not found")
    return result.data


@router.get("/{audit_id}/dispute", response_class=HTMLResponse)
async def get_dispute_notice(
    audit_id: str,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Generate the printable Rate Dispute Notice for an audit with
    overcharges. Open in browser → File → Print → Save as PDF →
    attach to the carrier dispute email.
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    audit = admin.table("carrier_invoice_audits").select("*") \
        .eq("id", audit_id).eq("org_id", org_id).single().execute()
    if not audit.data:
        raise HTTPException(404, "Audit not found")

    if audit.data["status"] != "overcharge_detected":
        raise HTTPException(400, "No overcharges found on this invoice — nothing to dispute")

    org = admin.table("organisations").select("name").eq("id", org_id).single().execute()
    org_name = org.data.get("name", "") if org.data else ""

    html = generate_dispute_notice_html(audit.data, org_name)

    # Mark dispute as generated
    admin.table("carrier_invoice_audits").update({"dispute_generated": True}) \
        .eq("id", audit_id).execute()

    return HTMLResponse(content=html)
