"""
CargoIQ — Portal Jobs Router
Trigger + monitor SARS, Transnet, and shipping line automation jobs.
"""
import uuid, logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from pydantic import BaseModel
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..core.config import settings
from ..services.queue_service import get_redis

router = APIRouter(prefix="/portals", tags=["Portal Automation"])
logger = logging.getLogger(__name__)

QUEUE_NAME = "portal-jobs"


# ── Schemas ─────────────────────────────────────────────────

class TriggerPortalJobRequest(BaseModel):
    job_type:     str          # e.g. "portal:sars:rla_check"
    params:       dict = {}
    shipment_id:  Optional[str] = None


# ── Queue helper ─────────────────────────────────────────────

def enqueue_portal_job(
    job_id: str, org_id: str, portal_job_id: str,
    job_type: str, params: dict,
    org_credentials: dict = None,
    priority: int = 1,
) -> str:
    """Push a portal job to BullMQ."""
    import json, time
    r   = get_redis()
    bid = str(uuid.uuid4())
    ts  = int(time.time() * 1000)

    # Look up encrypted portal credentials for this org
    admin = get_supabase_admin()
    portal_name = job_type.split(":")[1]   # "sars", "transnet", "shipping"

    creds_payload = None
    cred_rec = admin.table("portal_credentials").select("*")         .eq("org_id", org_id)         .eq("portal", portal_name)         .execute()
    if cred_rec.data:
        c = cred_rec.data[0]
        creds_payload = {
            "username_enc": c.get("username_enc", ""),
            "password_enc": c.get("password_enc", ""),
            "extra_enc":    c.get("extra_enc"),
        }

    job_data = {
        "job_type":      job_type,
        "org_id":        org_id,
        "portal_job_id": portal_job_id,
        "params":        params,
        "credentials":   creds_payload,
    }

    key = f"bull:{QUEUE_NAME}:{bid}"
    pipe = r.pipeline()
    pipe.hset(key, mapping={
        "id":           bid,
        "name":         "portal-automation",
        "data":         json.dumps(job_data),
        "opts":         json.dumps({
            "attempts": 2,
            "backoff":  {"type": "exponential", "delay": 10000},
            "removeOnComplete": 50,
            "removeOnFail": 25,
        }),
        "timestamp":    str(ts),
        "processedOn":  "", "finishedOn": "",
        "returnvalue":  "", "stacktrace": "[]",
        "attemptsMade": "0", "delay": "0",
        "priority":     str(priority),
    })
    pipe.zadd(f"bull:{QUEUE_NAME}:wait", {bid: ts})
    pipe.execute()

    logger.info(f"Portal job enqueued: {job_type} → {bid}")
    return bid


# ── Endpoints ────────────────────────────────────────────────

@router.post("/trigger", status_code=202)
async def trigger_portal_job(
    body: TriggerPortalJobRequest,
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Trigger a portal automation job.

    Job types:
      portal:sars:rla_check       params: {importerCode}
      portal:sars:submit_sad500   params: {sad500Data}
      portal:sars:release_check   params: {mrn}
      portal:transnet:container   params: {containerNumber}
      portal:transnet:demurrage   params: {containerNumber}
      portal:transnet:vessel_eta  params: {vesselName, voyageNumber?}
      portal:shipping:track       params: {containerNumber, line?}
      portal:shipping:release     params: {containerNumber, billOfLading?}
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    valid_prefixes = ("portal:sars:", "portal:transnet:", "portal:shipping:")
    if not any(body.job_type.startswith(p) for p in valid_prefixes):
        raise HTTPException(400, f"Invalid job_type. Must start with one of: {valid_prefixes}")

    portal_name = body.job_type.split(":")[1]

    # Create DB record
    portal_job_id = str(uuid.uuid4())
    admin.table("portal_jobs").insert({
        "id":          portal_job_id,
        "org_id":      org_id,
        "job_type":    body.job_type,
        "portal":      portal_name,
        "params":      body.params,
        "shipment_id": body.shipment_id,
        "status":      "queued",
    }).execute()

    # Push to BullMQ
    bullmq_id = enqueue_portal_job(
        job_id=str(uuid.uuid4()),
        org_id=org_id,
        portal_job_id=portal_job_id,
        job_type=body.job_type,
        params=body.params,
    )

    return {
        "portal_job_id": portal_job_id,
        "bullmq_id":     bullmq_id,
        "job_type":      body.job_type,
        "status":        "queued",
        "message":       f"Portal job queued — {body.job_type}",
    }


@router.get("/jobs")
async def list_portal_jobs(
    portal:  Optional[str] = Query(None),
    status:  Optional[str] = Query(None),
    page:    int           = Query(1, ge=1),
    limit:   int           = Query(20, ge=1, le=100),
    current_user: dict     = Depends(get_current_user_with_org)
):
    """List all portal automation jobs for this organisation."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    q = admin.table("portal_jobs")         .select("id,job_type,portal,status,params,result_data,error,duration_ms,created_at,completed_at")         .eq("org_id", org_id)

    if portal: q = q.eq("portal", portal)
    if status: q = q.eq("status", status)

    result = q.order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    count  = admin.table("portal_jobs").select("id", count="exact").eq("org_id", org_id).execute()

    return {
        "data":     result.data,
        "total":    count.count or 0,
        "page":     page,
        "limit":    limit,
        "has_more": (offset + limit) < (count.count or 0),
    }


@router.get("/jobs/{job_id}")
async def get_portal_job(
    job_id: str,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get result of a specific portal job including screenshot path."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    result = admin.table("portal_jobs").select("*")         .eq("id", job_id).eq("org_id", org_id).single().execute()

    if not result.data:
        raise HTTPException(404, "Portal job not found")

    return result.data


@router.get("/containers")
async def list_containers(
    released: Optional[bool] = Query(None),
    current_user: dict       = Depends(get_current_user_with_org)
):
    """List all tracked containers with latest status."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    q = admin.table("container_tracking").select("*").eq("org_id", org_id)
    if released is not None:
        q = q.eq("is_released", released)

    result = q.order("updated_at", desc=True).execute()
    return result.data


@router.post("/containers/bulk-track")
async def bulk_track_containers(
    container_numbers: list[str] = Body(...),
    current_user: dict           = Depends(get_current_user_with_org)
):
    """
    Queue tracking jobs for multiple containers at once.
    Auto-detects shipping line from container prefix.
    """
    from ..portals.shipping_line_helpers import detect_line_from_container

    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    queued = []

    for cn in container_numbers[:20]:  # Cap at 20 per request
        portal_job_id = str(uuid.uuid4())
        admin.table("portal_jobs").insert({
            "id": portal_job_id, "org_id": org_id,
            "job_type": "portal:shipping:track",
            "portal": "shipping", "status": "queued",
            "params": {"containerNumber": cn},
        }).execute()

        enqueue_portal_job(
            job_id=str(uuid.uuid4()), org_id=org_id,
            portal_job_id=portal_job_id,
            job_type="portal:shipping:track",
            params={"containerNumber": cn},
            priority=2,
        )
        queued.append({"containerNumber": cn, "portal_job_id": portal_job_id})

    return {"queued": len(queued), "jobs": queued}


@router.post("/rla/bulk-check")
async def bulk_rla_check(
    importer_codes: list[str] = Body(...),
    current_user: dict        = Depends(get_current_user_with_org)
):
    """
    Queue RLA status checks for multiple importers.
    This is what the 06:00 daily cron calls.
    """
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]
    queued = []

    for code in importer_codes[:50]:  # Cap at 50
        portal_job_id = str(uuid.uuid4())
        admin.table("portal_jobs").insert({
            "id": portal_job_id, "org_id": org_id,
            "job_type": "portal:sars:rla_check",
            "portal": "sars", "status": "queued",
            "params": {"importerCode": code},
        }).execute()

        enqueue_portal_job(
            job_id=str(uuid.uuid4()), org_id=org_id,
            portal_job_id=portal_job_id,
            job_type="portal:sars:rla_check",
            params={"importerCode": code},
            priority=1,
        )
        queued.append(code)

    return {"queued": len(queued), "importer_codes": queued}


@router.post("/credentials")
async def save_portal_credentials(
    portal:        str = Body(...),
    username:      str = Body(...),
    password:      str = Body(...),
    extra:         Optional[str] = Body(None),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Store encrypted portal credentials (SARS eFiling, Transnet, etc.)
    Credentials are AES-256 encrypted before storage.
    """
    from ..core.security import encrypt_value
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    valid_portals = ["sars", "transnet", "msc", "maersk", "hapag", "cma"]
    if portal not in valid_portals:
        raise HTTPException(400, f"Invalid portal. Valid: {valid_portals}")

    record = {
        "org_id":       org_id,
        "portal":       portal,
        "username_enc": encrypt_value(username),
        "password_enc": encrypt_value(password),
    }
    if extra:
        record["extra_enc"] = encrypt_value(extra)

    # Upsert
    existing = admin.table("portal_credentials").select("id")         .eq("org_id", org_id).eq("portal", portal).execute()

    if existing.data:
        admin.table("portal_credentials").update(record)             .eq("org_id", org_id).eq("portal", portal).execute()
    else:
        admin.table("portal_credentials").insert(record).execute()

    logger.info(f"Portal credentials saved: org={org_id} portal={portal}")
    return {"message": f"{portal} credentials saved and encrypted"}


@router.get("/stats")
async def portal_stats(current_user: dict = Depends(get_current_user_with_org)):
    """Summary stats for the portal automation dashboard."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    jobs      = admin.table("portal_jobs").select("status,portal")         .eq("org_id", org_id).execute()
    containers = admin.table("container_tracking").select("is_released,demurrage_zar")         .eq("org_id", org_id).execute()

    by_portal:  dict = {}
    by_status:  dict = {}
    for j in (jobs.data or []):
        by_portal[j["portal"]] = by_portal.get(j["portal"], 0) + 1
        by_status[j["status"]] = by_status.get(j["status"], 0) + 1

    total_demurrage  = sum(float(c.get("demurrage_zar") or 0) for c in (containers.data or []))
    released_count   = sum(1 for c in (containers.data or []) if c.get("is_released"))
    unreleased_count = sum(1 for c in (containers.data or []) if not c.get("is_released"))

    return {
        "jobs_by_portal":   by_portal,
        "jobs_by_status":   by_status,
        "total_jobs":        len(jobs.data or []),
        "containers_tracked":    len(containers.data or []),
        "containers_released":   released_count,
        "containers_unreleased": unreleased_count,
        "total_demurrage_exposure_zar": round(total_demurrage, 2),
    }
