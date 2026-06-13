"""
CargoIQ — Shadow Audit & Savings Certificate Router
The forensic proof layer that closes deals.
"""
import logging
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..services.shadow_audit_service import run_shadow_audit
from ..services.savings_certificate_service import generate_savings_certificate, get_success_story

router = APIRouter(prefix="/audit", tags=["Shadow Audit & Certificates"])
logger = logging.getLogger(__name__)


@router.post("/shadow")
async def trigger_shadow_audit(
    days_back:      int = Query(30, ge=7, le=90),
    max_shipments:  int = Query(100, ge=10, le=500),
    current_user: dict  = Depends(get_current_user_with_org),
):
    """
    Run a shadow audit on historical shipments.
    Finds errors the team missed — proof for the sales demo.

    Returns: forensic report with penalties found + value identified.
    """
    org_id = current_user["org_id"]
    result = await run_shadow_audit(
        org_id=org_id,
        days_back=days_back,
        max_shipments=max_shipments,
    )
    return result


@router.get("/shadow")
async def list_shadow_audits(
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get all shadow audit results for this organisation."""
    admin  = get_supabase_admin()
    result = admin.table("shadow_audits")         .select("id,summary,status,created_at,completed_at")         .eq("org_id", current_user["org_id"])         .order("created_at", desc=True)         .limit(10)         .execute()
    return result.data


@router.get("/shadow/{audit_id}")
async def get_shadow_audit(
    audit_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get detailed findings of a specific shadow audit."""
    admin  = get_supabase_admin()
    result = admin.table("shadow_audits")         .select("*")         .eq("id", audit_id)         .eq("org_id", current_user["org_id"])         .single()         .execute()
    if not result.data:
        raise HTTPException(404, "Shadow audit not found")
    return result.data


@router.get("/certificate", response_class=HTMLResponse)
async def get_savings_certificate(
    month:        Optional[str] = Query(None, description="e.g. 'May 2026'"),
    current_user: dict          = Depends(get_current_user_with_org),
):
    """
    Generate and return the monthly Savings Certificate as print-ready HTML.
    Open in browser → File → Print → Save as PDF for the CFO meeting.
    """
    result = await generate_savings_certificate(
        org_id=current_user["org_id"],
        month_label=month,
    )
    # Return HTML directly — browser can print/save as PDF
    return HTMLResponse(
        content=result["html"],
        headers={
            "Content-Disposition": f'inline; filename="cargoiq-savings-certificate-{result["period"].replace(" ", "-")}.html"',
            "X-Total-Value-ZAR":   str(result["total_value_zar"]),
            "X-ROI-Multiple":      str(result["roi_multiple"]),
        }
    )


@router.get("/certificate/data")
async def get_certificate_data(
    month:        Optional[str] = Query(None),
    current_user: dict          = Depends(get_current_user_with_org),
):
    """Get certificate metrics without the HTML (for dashboard widgets)."""
    result = await generate_savings_certificate(
        org_id=current_user["org_id"],
        month_label=month,
    )
    # Return everything except the full HTML
    return {k: v for k, v in result.items() if k != "html"}


# ── Proof Page sharing ───────────────────────────────────────

@router.post("/shadow/{audit_id}/share")
async def enable_shadow_audit_share(
    audit_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Generate (or re-fetch) a no-login share link for this shadow
    audit. Send this link to the prospect before the call — it
    shows a redacted summary of their own findings, generated
    automatically from their own data.
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    audit = admin.table("shadow_audits").select("id,share_token,share_enabled") \
        .eq("id", audit_id).eq("org_id", org_id).single().execute()
    if not audit.data:
        raise HTTPException(404, "Shadow audit not found")

    token = audit.data.get("share_token") or secrets.token_urlsafe(24)

    admin.table("shadow_audits").update({
        "share_token":   token,
        "share_enabled": True,
    }).eq("id", audit_id).execute()

    return {
        "share_token": token,
        "share_path":  f"/api/v1/public/proof/{token}",
        "message":     "Share this link — no login required. Anyone with the link can view this page.",
    }


@router.delete("/shadow/{audit_id}/share")
async def disable_shadow_audit_share(
    audit_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Disable the public proof-page link for this audit."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("shadow_audits").update({"share_enabled": False}) \
        .eq("id", audit_id).eq("org_id", org_id).execute()
    if not result.data:
        raise HTTPException(404, "Shadow audit not found")
    return {"message": "Proof page link disabled"}


# ── Client Success Story ────────────────────────────────────

@router.get("/success-story", response_class=HTMLResponse)
async def success_story(
    anonymized:   bool = Query(True, description="If true, replace org name with a generic industry descriptor"),
    month:        Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_with_org),
):
    """
    Generate a one-page Client Success Story from this org's
    Savings Certificate. Open in browser, screenshot or print to
    PDF, and show it to the next prospect.
    """
    html = await get_success_story(
        org_id=current_user["org_id"],
        anonymized=anonymized,
        month_label=month,
    )
    return HTMLResponse(content=html)
