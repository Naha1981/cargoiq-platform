"""
CargoIQ — Onboarding Checklist
================================
A self-serve checklist for new clients: connect email, upload
first shipments, add rate cards, run first shadow audit. Each
step's completion is COMPUTED from real data — not a manual
checkbox — so it can never drift out of sync with reality.

Designed so a new client can complete onboarding without the
founder sitting next to them.
"""
import logging
from fastapi import APIRouter, Depends, Body
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])
logger = logging.getLogger(__name__)

SHIPMENT_TARGET = 20


@router.get("/status")
async def onboarding_status(current_user: dict = Depends(get_current_user_with_org)):
    """
    Computed onboarding checklist. Each step reflects whether the
    underlying data exists — connect the email inbox, upload
    shipments, add a rate card, run a shadow audit, view Sentinel.
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    # 1. Email inbox connected
    email_conn = admin.table("email_connections").select("id") \
        .eq("org_id", org_id).eq("status", "active").limit(1).execute()
    email_connected = len(email_conn.data or []) > 0

    # 2. Shipments uploaded
    shipment_count = admin.table("shipments").select("id", count="exact") \
        .eq("org_id", org_id).execute()
    shipments_uploaded = shipment_count.count or 0

    # 3. Carrier rate card added (optional, unlocks CarrierInvoice Auditor)
    rate_cards = admin.table("carrier_rate_cards").select("id") \
        .eq("org_id", org_id).limit(1).execute()
    rate_card_added = len(rate_cards.data or []) > 0

    # 4. Shadow audit run at least once
    shadow = admin.table("shadow_audits").select("id") \
        .eq("org_id", org_id).limit(1).execute()
    shadow_audit_run = len(shadow.data or []) > 0

    # 5. Sentinel dashboard viewed (frontend pings this on first visit)
    org = admin.table("organisations").select("settings").eq("id", org_id).single().execute()
    settings = (org.data or {}).get("settings", {}) or {}
    sentinel_viewed = bool(settings.get("onboarding_sentinel_viewed", False))

    steps = [
        {
            "id":          "connect_email",
            "title":       "Connect your email inbox",
            "description": "CargoIQ's Email Agent watches your operations inbox and "
                            "extracts shipment documents automatically.",
            "action_path": "/settings",
            "action_label": "Go to Settings → Email Connection",
            "complete":    email_connected,
        },
        {
            "id":          "upload_shipments",
            "title":       f"Upload your first {SHIPMENT_TARGET} shipments",
            "description": "Upload recent shipment PDFs so CargoIQ can extract and "
                            "audit them. This also seeds your first Shadow Audit.",
            "action_path": "/queue/upload",
            "action_label": "Go to Upload",
            "complete":    shipments_uploaded >= SHIPMENT_TARGET,
            "progress":    f"{min(shipments_uploaded, SHIPMENT_TARGET)}/{SHIPMENT_TARGET}",
        },
        {
            "id":          "add_rate_card",
            "title":       "Add a carrier rate card",
            "description": "Add at least one negotiated carrier rate so the "
                            "CarrierInvoice Auditor can detect overcharges. Optional, "
                            "but unlocks a key feature.",
            "action_path": "/carrier-audit",
            "action_label": "Go to Carrier Auditor",
            "complete":    rate_card_added,
            "optional":    True,
        },
        {
            "id":          "run_shadow_audit",
            "title":       "Run your first Shadow Audit",
            "description": "Once you've uploaded shipments, run a Shadow Audit to see "
                            "what CargoIQ finds in your historical data — no cost, "
                            "no commitment.",
            "action_path": "/shadow-audit",
            "action_label": "Go to Shadow Audit",
            "complete":    shadow_audit_run,
        },
        {
            "id":          "view_sentinel",
            "title":       "Open the Sentinel dashboard",
            "description": "Your live, boardroom-ready view of value delivered and "
                            "revenue at risk. This is the screen to leave open in your "
                            "operations room.",
            "action_path": "/sentinel",
            "action_label": "Go to Sentinel",
            "complete":    sentinel_viewed,
        },
    ]

    required_steps = [s for s in steps if not s.get("optional")]
    completed_required = sum(1 for s in required_steps if s["complete"])

    return {
        "steps":            steps,
        "completed_count":  sum(1 for s in steps if s["complete"]),
        "total_count":      len(steps),
        "required_completed": completed_required,
        "required_total":     len(required_steps),
        "all_required_complete": completed_required == len(required_steps),
    }


@router.post("/sentinel-viewed")
async def mark_sentinel_viewed(current_user: dict = Depends(get_current_user_with_org)):
    """Called once by the frontend when a user first opens /sentinel."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    org = admin.table("organisations").select("settings").eq("id", org_id).single().execute()
    settings = (org.data or {}).get("settings", {}) or {}

    if not settings.get("onboarding_sentinel_viewed"):
        settings["onboarding_sentinel_viewed"] = True
        admin.table("organisations").update({"settings": settings}).eq("id", org_id).execute()

    return {"message": "ok"}
