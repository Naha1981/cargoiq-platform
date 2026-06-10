"""
CargoIQ — Internal Router
Endpoints called by background services (not user-facing).
Authenticated by internal secret key, not user JWT.
"""
import logging
from fastapi import APIRouter, HTTPException, Header
from ..core.config import settings
from ..core.supabase_client import get_supabase_admin

router = APIRouter(prefix="/internal", tags=["Internal"])
logger = logging.getLogger(__name__)


def verify_internal(x_internal_key: str = Header(...)):
    if x_internal_key != settings.SECRET_KEY[:16]:
        raise HTTPException(401, "Invalid internal key")


@router.post("/extract/{shipment_id}")
async def trigger_extraction(
    shipment_id: str,
    x_internal_key: str = Header(...)
):
    """
    Trigger the extraction pipeline for an existing shipment.
    Called by email agent after attaching documents.
    """
    verify_internal(x_internal_key)

    admin = get_supabase_admin()

    # Get shipment + documents
    docs_result = admin.table("shipment_documents")         .select("documents(*)")         .eq("shipment_id", shipment_id)         .execute()

    docs = [d["documents"] for d in docs_result.data if d.get("documents")]

    if not docs:
        raise HTTPException(400, "No documents attached to shipment")

    shipment = admin.table("shipments").select("org_id")         .eq("id", shipment_id).single().execute()

    if not shipment.data:
        raise HTTPException(404, "Shipment not found")

    org_id = shipment.data["org_id"]

    # Run pipeline as background task
    import asyncio
    from ..routers.shipments import run_extraction_pipeline
    asyncio.create_task(run_extraction_pipeline(shipment_id, docs, org_id))

    return {"message": "Extraction pipeline started", "shipment_id": shipment_id}


# ── Notification queue processor (called by n8n every 2 min) ──

@router.post("/notifications/process")
async def process_notifications(x_internal_key: str = Header(...)):
    verify_internal(x_internal_key)
    from ..services.notification_service import (
        send_compliance_alert, send_rla_suspension, send_shipment_approved
    )
    from datetime import datetime

    admin = get_supabase_admin()
    pending = admin.table("notification_queue") \
        .select("*").eq("status", "pending").limit(20).execute()

    sent = 0
    for notif in (pending.data or []):
        try:
            payload = notif.get("payload", {})
            org_id  = notif["org_id"]

            org_users = admin.table("users").select("email,full_name") \
                .eq("org_id", org_id).in_("role", ["admin","operations_manager"]) \
                .limit(1).execute()
            email = org_users.data[0]["email"] if org_users.data else None
            name  = org_users.data[0].get("full_name","") if org_users.data else ""

            if notif["type"] == "rla_suspension" and email:
                await send_rla_suspension(email, name,
                    payload.get("importerName","?"), payload.get("importerCode",""))

            elif notif["type"] == "demurrage_alert" and email:
                cn   = payload.get("containerNumber","?")
                risk = payload.get("demurrageExposureZAR", 0)
                days = payload.get("daysOverFreeTime", 0)
                await send_compliance_alert(
                    to=email, name=name, ref=cn, sid="",
                    module="port_demurrage",
                    resolution=f"Container {cn} has R{risk:,.0f} demurrage exposure ({days} days over free time).",
                    penalty=False,
                )

            admin.table("notification_queue").update({
                "status": "sent", "sent_at": datetime.utcnow().isoformat()
            }).eq("id", notif["id"]).execute()
            sent += 1

        except Exception as e:
            admin.table("notification_queue").update({
                "status": "failed", "error": str(e)[:300]
            }).eq("id", notif["id"]).execute()

    return {"processed": sent}
