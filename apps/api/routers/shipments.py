"""
CargoIQ — Shipments Router
Create, list, retrieve, approve, reject shipments.
Full extraction + compliance pipeline.
"""
import uuid
import logging
from datetime import datetime, date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..models.schemas import (
    ShipmentSummary, ShipmentDetail, ShipmentApproveRequest,
    ShipmentRejectRequest, ShipmentUpdateRequest, PaginatedResponse
)
from ..services.extraction_service import (
    extract_shipment_fields, extraction_to_shipment_dict, extraction_to_line_items
)
from ..services.compliance_service import run_compliance_shield
from ..services.queue_service import enqueue_cw_execution, get_queue_stats
from ..services.notification_service import (
    send_compliance_alert, send_shipment_approved,
    send_extraction_complete, whatsapp_compliance, whatsapp_rla
)

router = APIRouter(prefix="/shipments", tags=["Shipments"])
logger = logging.getLogger(__name__)


@router.get("/", response_model=PaginatedResponse)
async def list_shipments(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    confidence: Optional[str] = Query(None),
    shield: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user_with_org)
):
    """List shipments with filtering and pagination."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    query = admin.table("shipments") \
        .select(
            "id,reference,shipper_name,consignee_name,origin_port,"
            "destination_port,shipment_type,overall_confidence,"
            "shield_status,shield_results,status,source,created_at,updated_at"
        ) \
        .eq("org_id", org_id)

    if status_filter:
        query = query.eq("status", status_filter)
    if confidence:
        query = query.eq("overall_confidence", confidence)
    if shield:
        query = query.eq("shield_status", shield)
    if search:
        query = query.or_(
            f"shipper_name.ilike.%{search}%,"
            f"consignee_name.ilike.%{search}%,"
            f"reference.ilike.%{search}%,"
            f"awb_or_bl_number.ilike.%{search}%"
        )

    result = query.order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    count_q = admin.table("shipments").select("id", count="exact").eq("org_id", org_id)
    if status_filter:
        count_q = count_q.eq("status", status_filter)
    total = count_q.execute().count or 0

    return PaginatedResponse(
        data=result.data,
        total=total,
        page=page,
        limit=limit,
        has_more=(offset + limit) < total
    )


@router.get("/{shipment_id}")
async def get_shipment(
    shipment_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get full shipment detail including compliance results and line items."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("shipments") \
        .select("*") \
        .eq("id", shipment_id) \
        .eq("org_id", org_id) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Shipment not found")

    shipment = result.data

    # Get associated documents
    docs = admin.table("shipment_documents") \
        .select("documents(id,filename,doc_type,status)") \
        .eq("shipment_id", shipment_id) \
        .execute()
    shipment["documents"] = [d["documents"] for d in docs.data if d.get("documents")]

    # Get line items
    items = admin.table("cargo_line_items") \
        .select("*") \
        .eq("shipment_id", shipment_id) \
        .order("line_number") \
        .execute()
    shipment["line_items"] = items.data

    # Get compliance events
    events = admin.table("compliance_events") \
        .select("*") \
        .eq("shipment_id", shipment_id) \
        .order("created_at") \
        .execute()
    shipment["compliance_events"] = events.data

    return shipment


@router.post("/from-documents", status_code=status.HTTP_201_CREATED)
async def create_shipment_from_documents(
    document_ids: list[str],
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Create a new shipment by running AI extraction on specified documents.
    Triggers full pipeline: extract → compliance shield → queue for review.
    """
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    if not document_ids:
        raise HTTPException(status_code=400, detail="At least one document ID required")

    # Verify documents belong to this org
    docs = admin.table("documents") \
        .select("*") \
        .in_("id", document_ids) \
        .eq("org_id", org_id) \
        .execute()

    if len(docs.data) != len(document_ids):
        raise HTTPException(status_code=404, detail="One or more documents not found")

    unprocessed = [d for d in docs.data if d["status"] != "processed" or not d.get("raw_text")]
    if unprocessed:
        raise HTTPException(
            status_code=400,
            detail=f"{len(unprocessed)} document(s) not yet processed. Wait for OCR to complete."
        )

    # Create shipment record
    shipment_id = str(uuid.uuid4())
    shipment_record = {
        "id": shipment_id,
        "org_id": org_id,
        "status": "extracting",
        "source": "manual_upload",
        "processing_started_at": datetime.utcnow().isoformat(),
    }
    admin.table("shipments").insert(shipment_record).execute()

    # Link documents to shipment
    for doc in docs.data:
        admin.table("shipment_documents").insert({
            "shipment_id": shipment_id,
            "document_id": doc["id"],
            "role": doc.get("doc_type", "unknown")
        }).execute()

    # Queue extraction as background task
    background_tasks.add_task(
        run_extraction_pipeline,
        shipment_id=shipment_id,
        docs=docs.data,
        org_id=org_id
    )

    return {
        "shipment_id": shipment_id,
        "status": "extracting",
        "message": "Extraction pipeline started. Check status in a few seconds."
    }


@router.patch("/{shipment_id}")
async def update_shipment(
    shipment_id: str,
    payload: ShipmentUpdateRequest,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Human reviewer edits shipment fields. Logs all changes to audit trail."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    existing = admin.table("shipments") \
        .select("*") \
        .eq("id", shipment_id) \
        .eq("org_id", org_id) \
        .single() \
        .execute()

    if not existing.data:
        raise HTTPException(status_code=404, detail="Shipment not found")

    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = admin.table("shipments").update(updates).eq("id", shipment_id).execute()

    # Audit log
    admin.table("audit_log").insert({
        "org_id": org_id,
        "entity_type": "shipment",
        "entity_id": shipment_id,
        "action": "human_edit",
        "actor_type": "user",
        "actor_id": current_user["id"],
        "before_state": {k: existing.data.get(k) for k in updates.keys()},
        "after_state": updates,
    }).execute()

    return result.data[0] if result.data else {"message": "Updated"}


@router.post("/{shipment_id}/approve")
async def approve_shipment(
    shipment_id: str,
    payload: ShipmentApproveRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Approve shipment for CargoWise execution.
    Validates: shield status allows approval (no unacknowledged FAILs).
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

    s = shipment.data

    # Cannot approve if shield has FAILs (unless acknowledged)
    if s.get("shield_status") == "fail" and not payload.acknowledged_risks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Shipment has compliance failures. Set acknowledged_risks=true "
                "to override — this creates an audit record of your decision."
            )
        )

    # Cannot approve if still extracting
    if s.get("status") in ("extracting", "shield_running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shipment is still being processed. Wait for extraction to complete."
        )

    # Update to approved
    admin.table("shipments").update({
        "status": "approved",
        "reviewed_by": current_user["id"],
        "reviewed_at": datetime.utcnow().isoformat(),
        "review_notes": payload.notes,
    }).eq("id", shipment_id).execute()

    # Audit log
    admin.table("audit_log").insert({
        "org_id": org_id,
        "entity_type": "shipment",
        "entity_id": shipment_id,
        "action": "approved",
        "actor_type": "user",
        "actor_id": current_user["id"],
        "metadata": {
            "shield_status": s.get("shield_status"),
            "acknowledged_risks": payload.acknowledged_risks,
            "notes": payload.notes,
        }
    }).execute()

    # Queue CargoWise execution (if CW credentials configured)
    org = admin.table("organisations") \
        .select("cw_server_url,cw_credentials_enc") \
        .eq("id", org_id) \
        .single() \
        .execute()

    if org.data and org.data.get("cw_server_url"):
        background_tasks.add_task(
            queue_cargowise_execution,
            shipment_id=shipment_id,
            org_id=org_id
        )
        return {"message": "Approved. CargoWise execution queued.", "status": "pushing_to_cw"}

    return {"message": "Approved. Configure CargoWise in Settings to enable auto-execution.", "status": "approved"}


@router.post("/{shipment_id}/reject")
async def reject_shipment(
    shipment_id: str,
    payload: ShipmentRejectRequest,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Reject a shipment with a mandatory reason."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("shipments").update({
        "status": "rejected",
        "reviewed_by": current_user["id"],
        "reviewed_at": datetime.utcnow().isoformat(),
        "review_notes": payload.reason,
    }).eq("id", shipment_id).eq("org_id", org_id).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Shipment not found")

    admin.table("audit_log").insert({
        "org_id": org_id,
        "entity_type": "shipment",
        "entity_id": shipment_id,
        "action": "rejected",
        "actor_type": "user",
        "actor_id": current_user["id"],
        "metadata": {"reason": payload.reason}
    }).execute()

    return {"message": "Shipment rejected", "status": "rejected"}


@router.get("/{shipment_id}/audit")
async def get_shipment_audit(
    shipment_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get full audit trail for a shipment."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("audit_log") \
        .select("*") \
        .eq("entity_id", shipment_id) \
        .eq("org_id", org_id) \
        .order("created_at") \
        .execute()

    return result.data




@router.get("/queue/stats")
async def queue_stats(current_user: dict = Depends(get_current_user_with_org)):
    """Get BullMQ queue statistics for the CW execution worker."""
    return get_queue_stats()

# ============================================================
# BACKGROUND TASKS
# ============================================================

async def run_extraction_pipeline(shipment_id: str, docs: list, org_id: str):
    """
    Full AI extraction + compliance shield pipeline.
    Runs as background task after shipment creation.
    """
    admin = get_supabase_admin()

    try:
        # Combine raw text from all documents
        combined_text = ""
        doc_types = []
        for doc in docs:
            if doc.get("raw_text"):
                combined_text += f"\n\n=== {doc.get('doc_type', 'DOCUMENT').upper()} ===\n"
                combined_text += doc["raw_text"]
                if doc.get("doc_type"):
                    doc_types.append(doc["doc_type"])

        if not combined_text.strip():
            admin.table("shipments").update({
                "status": "error",
                "extracted_fields": {"error": "No text extracted from documents"}
            }).eq("id", shipment_id).execute()
            return

        # Run AI extraction
        extraction = await extract_shipment_fields(
            raw_text=combined_text,
            doc_types=doc_types,
            filename=docs[0].get("filename", "") if docs else ""
        )

        # Convert to DB dict
        shipment_data = extraction_to_shipment_dict(extraction)

        # Determine status based on confidence
        confidence = shipment_data.get("overall_confidence", "low")
        conf_pct = shipment_data.get("confidence_percentage", 0)

        if confidence == "high" and conf_pct >= 90:
            pre_shield_status = "extracted"
        else:
            pre_shield_status = "review_required"

        # Update shipment with extracted data
        admin.table("shipments").update({
            **shipment_data,
            "status": "shield_running",
        }).eq("id", shipment_id).execute()

        # Run Compliance Shield
        shield_report = run_compliance_shield(
            shipment=shipment_data,
            documents=docs,
            org_id=org_id,
            run_da65=True,
            run_da179=True,
        )

        # Store shield results
        admin.table("shipments").update({
            "shield_status": shield_report.overall,
            "shield_results": shield_report.to_dict(),
            "shield_run_at": shield_report.run_at.isoformat(),
            "status": "review_required" if shield_report.overall in ("hold", "fail") else pre_shield_status,
            "processing_completed_at": datetime.utcnow().isoformat(),
        }).eq("id", shipment_id).execute()

        # Store individual compliance events
        for module_result in shield_report.modules:
            if module_result.result != "pass":
                admin.table("compliance_events").insert({
                    "shipment_id": shipment_id,
                    "org_id": org_id,
                    "module": module_result.module,
                    "result": module_result.result,
                    "detail": module_result.detail,
                    "penalty_risk": module_result.penalty_risk,
                    "resolution": module_result.resolution,
                }).execute()

        # Store line items
        line_items = extraction_to_line_items(extraction, shipment_id)
        if line_items:
            admin.table("cargo_line_items").insert(line_items).execute()

        # Audit log
        admin.table("audit_log").insert({
            "org_id": org_id,
            "entity_type": "shipment",
            "entity_id": shipment_id,
            "action": "extracted",
            "actor_type": "ai_system",
            "metadata": {
                "confidence": confidence,
                "confidence_pct": conf_pct,
                "shield_status": shield_report.overall,
                "penalty_risk": shield_report.penalty_risk_detected,
                "doc_types": doc_types,
            }
        }).execute()

        logger.info(
            f"Pipeline complete: {shipment_id} | "
            f"confidence={confidence} ({conf_pct}%) | "
            f"shield={shield_report.overall} | "
            f"penalty_risk={shield_report.penalty_risk_detected}"
        )

        # Fire notifications for non-auto-approved shipments
        try:
            # Get org admin email
            org_users = admin.table("users")\
                .select("email,full_name")\
                .eq("org_id", org_id)\
                .in_("role", ["admin","operations_manager"])\
                .limit(1)\
                .execute()

            if org_users.data:
                ops_email = org_users.data[0]["email"]
                ops_name  = org_users.data[0].get("full_name","")

                # Extraction complete notification (only for review/fail)
                flags_count = len([m for m in shield_report.modules if m.result != "pass"])
                await send_extraction_complete(
                    to=ops_email, ref=shipment_data.get("reference",""),
                    sid=shipment_id, confidence=confidence,
                    shield=shield_report.overall, flags=flags_count
                )

                # Penalty risk alert — immediate notification
                if shield_report.penalty_risk_detected:
                    for mod in shield_report.modules:
                        if mod.penalty_risk and mod.result in ("hold","fail"):
                            await send_compliance_alert(
                                to=ops_email, name=ops_name,
                                ref=shipment_data.get("reference",""),
                                sid=shipment_id, module=mod.module,
                                resolution=mod.resolution or "",
                                penalty=True
                            )
                            break  # Send once for the first penalty module
        except Exception as notif_err:
            logger.warning(f"Notification failed (non-critical): {notif_err}")

    except Exception as e:
        logger.error(f"Extraction pipeline failed for {shipment_id}: {e}")
        admin.table("shipments").update({
            "status": "error",
            "extracted_fields": {"pipeline_error": str(e)[:500]}
        }).eq("id", shipment_id).execute()


async def queue_cargowise_execution(shipment_id: str, org_id: str):
    """
    Create a cw_executions record and push to BullMQ.
    The cw-worker Node.js service picks it up and runs Playwright.
    """
    admin = get_supabase_admin()
    import uuid as _uuid

    exec_id = str(_uuid.uuid4())
    exec_record = {
        "id":           exec_id,
        "org_id":       org_id,
        "shipment_id":  shipment_id,
        "execution_type": "playwright",
        "status":       "queued",
    }
    admin.table("cw_executions").insert(exec_record).execute()
    admin.table("shipments").update({"status": "pushing_to_cw"}).eq("id", shipment_id).execute()

    # Push to BullMQ — cw-worker will pick up within seconds
    try:
        job_id = enqueue_cw_execution(
            execution_id=exec_id,
            shipment_id=shipment_id,
            org_id=org_id,
            execution_type="playwright",
        )
        logger.info(f"CargoWise job enqueued: {job_id} for shipment {shipment_id}")
    except Exception as e:
        # Queue unavailable — job still in DB, worker will retry
        logger.error(f"BullMQ enqueue failed (job still in DB): {e}")
