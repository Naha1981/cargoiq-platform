"""
CargoIQ — Inbox Router
Manages the AI inbox agent: status, mode toggle, approve/skip emails.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Body
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..services.email_agent_service import (
    start_agents_for_org, stop_agent, get_agent_status
)

router = APIRouter(prefix="/inbox", tags=["Inbox Agent"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def inbox_status(current_user: dict = Depends(get_current_user_with_org)):
    """Get status of all inbox agents for this org + current mode setting."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    org = admin.table("organisations").select("settings").eq("id", org_id).single().execute()
    mode = "manual"
    if org.data:
        mode = org.data.get("settings", {}).get("inbox_mode", "manual")

    connections = admin.table("email_connections")         .select("id,email_address,type,status,last_synced_at")         .eq("org_id", org_id).execute()

    agents = get_agent_status()

    return {
        "inbox_mode": mode,
        "connections": [
            {**c, "agent_running": c["id"] in agents}
            for c in (connections.data or [])
        ],
    }


@router.post("/mode")
async def set_inbox_mode(
    mode: str = Body(..., embed=True),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Toggle inbox processing mode:
    - auto:   AI processes every freight email immediately
    - manual: AI detects + queues, human decides in Inbox page
    """
    if mode not in ("auto", "manual"):
        raise HTTPException(400, "mode must be 'auto' or 'manual'")

    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    org = admin.table("organisations").select("settings").eq("id", org_id).single().execute()
    current_settings = (org.data or {}).get("settings", {})
    current_settings["inbox_mode"] = mode

    admin.table("organisations").update({"settings": current_settings}).eq("id", org_id).execute()
    logger.info(f"Org {org_id} inbox mode set to: {mode}")
    return {"inbox_mode": mode, "message": f"Inbox mode updated to {mode}"}


@router.post("/start")
async def start_inbox_agents(current_user: dict = Depends(get_current_user_with_org)):
    """Start inbox polling agents for all connected email accounts."""
    await start_agents_for_org(current_user["org_id"])
    return {"message": "Inbox agents started"}


@router.post("/stop/{connection_id}")
async def stop_inbox_agent(
    connection_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Stop a specific inbox agent."""
    stop_agent(connection_id)
    return {"message": f"Agent stopped for connection {connection_id}"}


@router.get("/emails")
async def list_inbox_emails(
    page: int = 1,
    limit: int = 20,
    status: str = None,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    List emails the agent has found.
    status=processing → awaiting human decision (manual mode)
    status=processed  → already handled
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    q = admin.table("inbound_emails")         .select("id,from_address,subject,body_preview,classification,status,received_at,raw_headers")         .eq("org_id", org_id)

    if status:
        q = q.eq("status", status)

    result = q.order("received_at", desc=True).range(offset, offset + limit - 1).execute()
    count  = admin.table("inbound_emails").select("id", count="exact")         .eq("org_id", org_id).execute()

    return {
        "data":     result.data,
        "total":    count.count or 0,
        "page":     page,
        "limit":    limit,
        "has_more": (offset + limit) < (count.count or 0),
    }


@router.post("/emails/{email_id}/process")
async def process_email(
    email_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Human approves: process this email's attachments through the extraction pipeline.
    Used when inbox_mode = manual.
    """
    import uuid
    from ..services.document_service import extract_text_from_pdf, classify_document_type

    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    email_rec = admin.table("inbound_emails")         .select("*").eq("id", email_id).eq("org_id", org_id).single().execute()
    if not email_rec.data:
        raise HTTPException(404, "Email not found")

    headers  = email_rec.data.get("raw_headers", {})
    attachments = headers.get("attachments", [])

    if not attachments:
        raise HTTPException(400, "No attachments found on this email")

    # Get document IDs that were pre-stored
    doc_ids = [a["doc_id"] for a in attachments if "doc_id" in a]

    if not doc_ids:
        raise HTTPException(400, "Attachments not yet stored — try again in a moment")

    # Run OCR on docs that haven't been processed yet
    for doc_id in doc_ids:
        doc = admin.table("documents").select("*").eq("id", doc_id).single().execute()
        if doc.data and doc.data.get("status") == "pending":
            try:
                file_bytes = admin.storage.from_("documents").download(doc.data["storage_path"])
                raw_text, method, pages = extract_text_from_pdf(file_bytes, doc.data.get("filename",""))
                doc_type = classify_document_type(raw_text or "", doc.data.get("filename",""))
                admin.table("documents").update({
                    "raw_text":   (raw_text or "")[:100000],
                    "doc_type":   doc_type,
                    "page_count": pages,
                    "ocr_method": method,
                    "status":     "processed" if raw_text else "failed",
                }).eq("id", doc_id).execute()
            except Exception as e:
                logger.error(f"OCR failed for doc {doc_id}: {e}")

    # Create shipment and trigger extraction
    shipment_id = str(uuid.uuid4())
    admin.table("shipments").insert({
        "id":              shipment_id,
        "org_id":          org_id,
        "status":          "extracting",
        "source":          "email",
        "source_email_id": email_id,
        "processing_started_at": __import__("datetime").datetime.utcnow().isoformat(),
    }).execute()

    for doc_id in doc_ids:
        admin.table("shipment_documents").insert({
            "shipment_id": shipment_id,
            "document_id": doc_id,
        }).execute()

    admin.table("inbound_emails").update({"status": "processed"}).eq("id", email_id).execute()

    # Trigger pipeline via internal endpoint
    import httpx
    from ..core.config import settings
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                f"http://localhost:8000/api/v1/internal/extract/{shipment_id}",
                headers={"x-internal-key": settings.SECRET_KEY[:16]}
            )
    except Exception:
        pass

    return {
        "message":     "Processing started",
        "shipment_id": shipment_id,
        "doc_count":   len(doc_ids),
    }


@router.post("/emails/{email_id}/skip")
async def skip_email(
    email_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Human skips: mark as ignored, no shipment created."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("inbound_emails").update({"status": "ignored"})         .eq("id", email_id).eq("org_id", org_id).execute()

    if not result.data:
        raise HTTPException(404, "Email not found")

    return {"message": "Email skipped"}
