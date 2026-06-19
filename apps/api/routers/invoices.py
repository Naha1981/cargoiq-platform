"""
CargoIQ — Invoices + VOC Tracker Router
=========================================
  POST /invoices/from-finding/{finding_id}  — generate invoice from waiting-time finding
  GET  /invoices/                           — list all invoices
  GET  /invoices/{id}                       — get invoice + HTML
  GET  /invoices/{id}/print                 — printable HTML (browser → PDF)
  PATCH /invoices/{id}/status               — mark sent / paid
  POST /invoices/voc                        — log a VOC from SARS
  GET  /invoices/voc                        — list all outstanding VOCs
  GET  /invoices/voc/summary                — total liability dashboard widget
"""
import logging
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..services.invoice_service import (
    create_invoice_from_finding,
    generate_invoice_html,
)

router = APIRouter(prefix="/invoices", tags=["Invoices & VOC"])
logger = logging.getLogger(__name__)


# ── Invoices ──────────────────────────────────────────────────

class InvoiceFromFindingRequest(BaseModel):
    bank_account: Optional[str] = None
    due_days:     int = 30


class InvoiceStatusUpdate(BaseModel):
    status:  str   # draft | sent | paid | cancelled
    paid_at: Optional[str] = None


@router.post("/from-finding/{finding_id}", status_code=201)
async def create_from_finding(
    finding_id: str,
    body:       InvoiceFromFindingRequest,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Generate a numbered tax invoice from a waiting-time finding.
    Automatically marks the finding as 'invoiced'.
    """
    try:
        result = await create_invoice_from_finding(
            org_id=current_user["org_id"],
            finding_id=finding_id,
            bank_account=body.bank_account,
            due_days=body.due_days,
        )
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/")
async def list_invoices(
    status:   Optional[str] = Query(None),
    page:     int = Query(1, ge=1),
    limit:    int = Query(25, ge=1, le=100),
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    q = admin.table("invoices") \
        .select(
            "id,invoice_number,invoice_type,client_name,subtotal_zar,"
            "vat_zar,total_zar,status,due_date,sent_at,paid_at,created_at"
        ).eq("org_id", org_id)
    if status:
        q = q.eq("status", status)

    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    count  = admin.table("invoices").select("id", count="exact").eq("org_id", org_id).execute()

    return {"data": result.data, "total": count.count or 0, "page": page, "limit": limit}


@router.get("/summary")
async def invoice_summary(current_user: dict = Depends(get_current_user_with_org)):
    """Totals by status — feeds the Sentinel dashboard."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    rows = admin.table("invoices").select("status,total_zar").eq("org_id", org_id).execute()
    by_status: dict = {}
    for r in (rows.data or []):
        s = r["status"]
        if s not in by_status:
            by_status[s] = {"count": 0, "total_zar": 0}
        by_status[s]["count"]     += 1
        by_status[s]["total_zar"] += float(r.get("total_zar") or 0)

    return {
        "by_status":   by_status,
        "total_count": len(rows.data or []),
        "total_outstanding_zar": round(
            sum(v["total_zar"] for k, v in by_status.items() if k in ("draft","sent")), 2
        ),
        "total_paid_zar": round(by_status.get("paid", {}).get("total_zar", 0), 2),
    }


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, current_user: dict = Depends(get_current_user_with_org)):
    admin  = get_supabase_admin()
    result = admin.table("invoices").select("*").eq("id", invoice_id) \
        .eq("org_id", current_user["org_id"]).single().execute()
    if not result.data:
        raise HTTPException(404, "Invoice not found")
    return result.data


@router.get("/{invoice_id}/print", response_class=HTMLResponse)
async def print_invoice(invoice_id: str, current_user: dict = Depends(get_current_user_with_org)):
    """Return printable HTML — open in browser, File → Print → Save as PDF."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    inv = admin.table("invoices").select("*").eq("id", invoice_id) \
        .eq("org_id", org_id).single().execute()
    if not inv.data:
        raise HTTPException(404, "Invoice not found")

    org = admin.table("organisations").select("name").eq("id", org_id).single().execute()
    org_name = org.data.get("name", "") if org.data else ""

    return HTMLResponse(content=generate_invoice_html(inv.data, org_name))


@router.patch("/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: str,
    body:       InvoiceStatusUpdate,
    current_user: dict = Depends(get_current_user_with_org),
):
    if body.status not in ("draft", "sent", "paid", "cancelled"):
        raise HTTPException(400, "Invalid status")

    admin  = get_supabase_admin()
    update = {"status": body.status}
    now    = datetime.utcnow().isoformat()

    if body.status == "sent":
        update["sent_at"] = now
    elif body.status == "paid":
        update["paid_at"] = body.paid_at or now

    result = admin.table("invoices").update(update) \
        .eq("id", invoice_id).eq("org_id", current_user["org_id"]).execute()
    if not result.data:
        raise HTTPException(404, "Invoice not found")
    return result.data[0]


# ── VOC Tracker ───────────────────────────────────────────────

class VOCCreate(BaseModel):
    voc_reference:          str
    mrn:                    Optional[str] = None
    shipment_id:            Optional[str] = None
    customs_value_original: Optional[float] = None
    customs_value_corrected: Optional[float] = None
    duty_original_zar:      Optional[float] = None
    duty_corrected_zar:     Optional[float] = None
    vat_difference_zar:     Optional[float] = None
    reason_code:            Optional[str] = None
    reason_description:     Optional[str] = None
    payment_deadline:       Optional[str] = None
    agent_liable:           bool = False
    notes:                  Optional[str] = None


@router.post("/voc", status_code=201)
async def log_voc(
    body: VOCCreate,
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Log a SARS Voucher of Correction. This creates a payment liability
    that must be settled before the deadline or penalty interest accrues.
    If agent_liable=True, the clearing agent is personally on the hook.
    """
    admin  = get_supabase_admin()
    record = body.model_dump(exclude_none=True)
    record["org_id"] = current_user["org_id"]
    record["status"] = "outstanding"

    result = admin.table("vouchers_of_correction").insert(record).execute()
    logger.info(f"VOC logged: {body.voc_reference}, agent_liable={body.agent_liable}")
    return result.data[0]


@router.get("/voc")
async def list_vocs(
    status:  Optional[str] = Query("outstanding"),
    current_user: dict = Depends(get_current_user_with_org),
):
    admin  = get_supabase_admin()
    q = admin.table("vouchers_of_correction").select("*") \
        .eq("org_id", current_user["org_id"])
    if status:
        q = q.eq("status", status)
    result = q.order("payment_deadline").execute()
    return result.data


@router.get("/voc/summary")
async def voc_summary(current_user: dict = Depends(get_current_user_with_org)):
    """
    Total outstanding VOC liability — feeds the Section 99(2)
    liability tracker and the Sentinel dashboard.
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    vocs = admin.table("vouchers_of_correction").select(
        "status,total_liability_zar,agent_liable,payment_deadline"
    ).eq("org_id", org_id).execute()

    outstanding = [v for v in (vocs.data or []) if v["status"] == "outstanding"]
    overdue     = [
        v for v in outstanding
        if v.get("payment_deadline") and v["payment_deadline"] < datetime.utcnow().date().isoformat()
    ]

    total_outstanding = sum(float(v.get("total_liability_zar") or 0) for v in outstanding)
    agent_exposure    = sum(
        float(v.get("total_liability_zar") or 0)
        for v in outstanding if v.get("agent_liable")
    )

    return {
        "outstanding_count":     len(outstanding),
        "overdue_count":         len(overdue),
        "total_outstanding_zar": round(total_outstanding, 2),
        "agent_exposure_zar":    round(agent_exposure, 2),  # Section 99(2)
        "total_vocs":            len(vocs.data or []),
    }


@router.patch("/voc/{voc_id}")
async def update_voc(
    voc_id: str,
    status: str = Query(...),
    current_user: dict = Depends(get_current_user_with_org),
):
    if status not in ("outstanding", "paid", "disputed", "written_off"):
        raise HTTPException(400, "Invalid status")

    admin  = get_supabase_admin()
    update: dict = {"status": status}
    if status == "paid":
        update["paid_at"] = datetime.utcnow().isoformat()

    result = admin.table("vouchers_of_correction").update(update) \
        .eq("id", voc_id).eq("org_id", current_user["org_id"]).execute()
    if not result.data:
        raise HTTPException(404, "VOC not found")
    return result.data[0]
