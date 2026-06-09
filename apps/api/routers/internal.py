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
