"""
CargoIQ — Compliance Router
Standalone compliance audits and event management.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..services.compliance_service import run_compliance_shield

router = APIRouter(prefix="/compliance", tags=["Compliance"])
logger = logging.getLogger(__name__)


@router.post("/audit")
async def run_compliance_audit(
    shipment_id: str = Body(...),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Re-run the full Compliance Shield on an existing shipment.
    Useful after human edits to check if issues are resolved.
    """
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    shipment = admin.table("shipments") \
        .select("*") \
        .eq("id", shipment_id) \
        .eq("org_id", org_id) \
        .single() \
        .execute()

    if not shipment.data:
        raise HTTPException(status_code=404, detail="Shipment not found")

    docs = admin.table("shipment_documents") \
        .select("documents(*)") \
        .eq("shipment_id", shipment_id) \
        .execute()
    doc_list = [d["documents"] for d in docs.data if d.get("documents")]

    report = run_compliance_shield(
        shipment=shipment.data,
        documents=doc_list,
        org_id=org_id,
        run_da65=True,
        run_da179=True,
    )

    # Update shipment shield status
    admin.table("shipments").update({
        "shield_status": report.overall,
        "shield_results": report.to_dict(),
        "shield_run_at": report.run_at.isoformat(),
    }).eq("id", shipment_id).execute()

    return report.to_dict()


@router.get("/events/{shipment_id}")
async def get_compliance_events(
    shipment_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get all compliance events for a shipment."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("compliance_events") \
        .select("*") \
        .eq("shipment_id", shipment_id) \
        .eq("org_id", org_id) \
        .order("created_at") \
        .execute()

    return result.data


@router.post("/events/{event_id}/resolve")
async def resolve_compliance_event(
    event_id: str,
    resolution_note: str = Body(...),
    current_user: dict = Depends(get_current_user_with_org)
):
    """Mark a compliance event as resolved with a note."""
    from datetime import datetime
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("compliance_events").update({
        "resolved_by": current_user["id"],
        "resolved_at": datetime.utcnow().isoformat(),
        "resolution_note": resolution_note,
        "auto_resolved": False,
    }).eq("id", event_id).eq("org_id", org_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Compliance event not found")

    return result.data[0]


@router.get("/rla-statuses")
async def get_rla_statuses(
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get all RLA importer statuses for this organisation."""
    admin = get_supabase_admin()
    result = admin.table("rla_statuses") \
        .select("*") \
        .eq("org_id", current_user["org_id"]) \
        .order("rla_status") \
        .execute()
    return result.data
