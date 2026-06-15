"""
CargoIQ — Built-in Job Scheduler
==================================
Replaces the three n8n cron workflows entirely. Runs inside the
FastAPI lifespan as a background APScheduler instance — no separate
deployment, no n8n container, no Zapier, no Make, no Activepieces.

Three jobs, same logic as the old n8n workflows:

  Job 1  — daily_rla_check        (06:00 SAST = 04:00 UTC)
            Fetches every active org's importer codes and queues
            portal:sars:rla_check jobs for each one.

  Job 2  — container_tracker      (every 30 minutes)
            Fetches all unreleased containers across all orgs and
            queues portal:shipping:track + portal:transnet:container
            refresh jobs.

  Job 3  — notification_processor (every 2 minutes)
            Sends pending WhatsApp / email notifications from the
            notification_queue table.

Adding a new cron job is three lines of Python — no JSON workflow
files, no drag-and-drop, no YAML. Just add a function below and
register it in start_scheduler().
"""
import logging
import asyncio
import uuid
import time as _time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron    import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from .core.config          import settings
from .core.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)

# One shared scheduler instance, started in lifespan (main.py)
_scheduler: AsyncIOScheduler | None = None


# ── Job 1: Daily RLA check — 06:00 SAST (04:00 UTC) ─────────

async def daily_rla_check():
    """
    Queue a portal:sars:rla_check job for every importer code
    registered across all active organisations.

    Why here instead of n8n:
      The n8n workflow called GET /portals/rla/bulk-check which
      itself needed a long-lived Bearer token.  This function calls
      the same internal logic directly, no HTTP round-trip needed.
    """
    logger.info("[SCHED] daily_rla_check — starting")
    admin = get_supabase_admin()

    # Get all distinct importer codes from rla_statuses
    orgs = admin.table("organisations") \
        .select("id") \
        .eq("status", "active") \
        .execute()

    if not orgs.data:
        logger.info("[SCHED] daily_rla_check — no active orgs")
        return

    total_queued = 0
    for org in orgs.data:
        org_id = org["id"]

        codes = admin.table("rla_statuses") \
            .select("importer_code") \
            .eq("org_id", org_id) \
            .execute()

        if not codes.data:
            continue

        for row in codes.data:
            importer_code = row["importer_code"]
            portal_job_id = str(uuid.uuid4())

            admin.table("portal_jobs").insert({
                "id":         portal_job_id,
                "org_id":     org_id,
                "job_type":   "portal:sars:rla_check",
                "portal":     "sars",
                "params":     {"importerCode": importer_code},
                "status":     "queued",
                "scheduled_at": datetime.utcnow().isoformat(),
            }).execute()

            _enqueue_bullmq("portal-jobs", {
                "job_type":      "portal:sars:rla_check",
                "org_id":        org_id,
                "portal_job_id": portal_job_id,
                "params":        {"importerCode": importer_code},
            })
            total_queued += 1

    logger.info(f"[SCHED] daily_rla_check — {total_queued} RLA checks queued")


# ── Job 2: Container tracker — every 30 minutes ──────────────

async def container_tracker():
    """
    Queue container tracking jobs for every unreleased container
    across all orgs.
    """
    logger.info("[SCHED] container_tracker — starting")
    admin = get_supabase_admin()

    containers = admin.table("container_tracking") \
        .select("org_id,container_number") \
        .eq("is_released", False) \
        .execute()

    if not containers.data:
        logger.info("[SCHED] container_tracker — no unreleased containers")
        return

    queued = 0
    for c in containers.data:
        org_id          = c["org_id"]
        container_number = c["container_number"]
        portal_job_id   = str(uuid.uuid4())

        admin.table("portal_jobs").insert({
            "id":         portal_job_id,
            "org_id":     org_id,
            "job_type":   "portal:shipping:track",
            "portal":     "shipping",
            "params":     {"containerNumber": container_number},
            "status":     "queued",
            "scheduled_at": datetime.utcnow().isoformat(),
        }).execute()

        _enqueue_bullmq("portal-jobs", {
            "job_type":      "portal:shipping:track",
            "org_id":        org_id,
            "portal_job_id": portal_job_id,
            "params":        {"containerNumber": container_number},
        })
        queued += 1

    logger.info(f"[SCHED] container_tracker — {queued} container jobs queued")


# ── Job 3: Notification queue processor — every 2 minutes ────

async def notification_processor():
    """
    Send up to 20 pending notifications (WhatsApp + email) from
    the notification_queue table.  Same logic as the n8n workflow
    that called POST /internal/notifications/process.
    """
    admin = get_supabase_admin()

    pending = admin.table("notification_queue") \
        .select("*") \
        .eq("status", "pending") \
        .limit(20) \
        .execute()

    if not pending.data:
        return  # silent — fires every 2 minutes, usually empty

    logger.info(f"[SCHED] notification_processor — {len(pending.data)} pending")

    from .services.notification_service import (
        send_rla_suspension,
        send_compliance_alert,
        send_shipment_approved,
    )

    sent = 0
    for notif in pending.data:
        try:
            payload = notif.get("payload", {})
            org_id  = notif["org_id"]

            # Get the ops lead for this org
            contact = admin.table("users") \
                .select("email,full_name") \
                .eq("org_id", org_id) \
                .in_("role", ["admin", "operations_manager"]) \
                .limit(1).execute()

            email = contact.data[0]["email"]     if contact.data else None
            name  = contact.data[0].get("full_name", "") if contact.data else ""

            if notif["type"] == "rla_suspension" and email:
                await send_rla_suspension(
                    email, name,
                    payload.get("importerName", "Unknown"),
                    payload.get("importerCode", "")
                )
            elif notif["type"] == "demurrage_alert" and email:
                cn   = payload.get("containerNumber", "?")
                risk = payload.get("demurrageExposureZAR", 0)
                days = payload.get("daysOverFreeTime", 0)
                await send_compliance_alert(
                    to=email, name=name, ref=cn, sid="",
                    module="port_demurrage",
                    resolution=(
                        f"Container {cn} has R{risk:,.0f} demurrage "
                        f"exposure ({days} days over free time)."
                    ),
                    penalty=False,
                )
            elif notif["type"] == "container_released" and email:
                await send_shipment_approved(
                    to=email,
                    ref=payload.get("containerNumber", ""),
                    sid=payload.get("containerNumber", ""),
                    cw_job=None,
                )

            admin.table("notification_queue").update({
                "status":  "sent",
                "sent_at": datetime.utcnow().isoformat(),
            }).eq("id", notif["id"]).execute()
            sent += 1

        except Exception as e:
            logger.error(f"[SCHED] notification send failed: {e}")
            admin.table("notification_queue").update({
                "status": "failed",
                "error":  str(e)[:300],
            }).eq("id", notif["id"]).execute()

    if sent:
        logger.info(f"[SCHED] notification_processor — {sent} sent")


# ── Job 4: Shadow audit digest — Mondays 07:00 SAST ─────────
# Scans every org that has shipments but no shadow audit in the
# last 30 days and runs one automatically.  This is the "set and
# forget" version of the Shadow Audit that you'd otherwise trigger
# manually from the dashboard.

async def weekly_shadow_audit_sweep():
    """
    Run a shadow audit for any org that hasn't had one in 30 days
    and has at least 10 approved shipments.  Results appear in the
    dashboard automatically — the next client meeting starts with
    fresh numbers without anyone pressing a button.
    """
    logger.info("[SCHED] weekly_shadow_audit_sweep — starting")
    admin = get_supabase_admin()

    orgs = admin.table("organisations") \
        .select("id") \
        .eq("status", "active") \
        .execute()

    for org in (orgs.data or []):
        org_id = org["id"]

        # Skip if audited in the last 30 days
        cutoff = (datetime.utcnow() - timedelta(days=30)).isoformat()
        recent = admin.table("shadow_audits") \
            .select("id") \
            .eq("org_id", org_id) \
            .gte("created_at", cutoff) \
            .limit(1).execute()

        if recent.data:
            continue

        # Skip if fewer than 10 approved shipments
        ship_count = admin.table("shipments").select("id", count="exact") \
            .eq("org_id", org_id) \
            .in_("status", ["approved", "in_cargowise"]).execute()

        if (ship_count.count or 0) < 10:
            continue

        # Run in background — don't block the scheduler thread
        asyncio.create_task(_run_shadow_audit_for_org(org_id))

    logger.info("[SCHED] weekly_shadow_audit_sweep — sweep complete")


async def _run_shadow_audit_for_org(org_id: str):
    try:
        from .services.shadow_audit_service import run_shadow_audit
        result = await run_shadow_audit(org_id=org_id, days_back=30)
        logger.info(
            f"[SCHED] Auto shadow audit: org={org_id} "
            f"value=R{result['summary'].get('total_value_identified_zar', 0):,.0f}"
        )
    except Exception as e:
        logger.error(f"[SCHED] Auto shadow audit failed: org={org_id} err={e}")


# ── BullMQ enqueue (raw Redis) ────────────────────────────────

def _enqueue_bullmq(queue_name: str, job_data: dict, priority: int = 2):
    """
    Push a job directly to BullMQ via raw Redis commands.
    Same approach as queue_service.py / portals.py.
    """
    import json
    from .services.queue_service import get_redis

    r  = get_redis()
    bid = str(uuid.uuid4())
    ts  = int(_time.time() * 1000)

    key = f"bull:{queue_name}:{bid}"
    r.hset(key, mapping={
        "id":           bid,
        "name":         "scheduled",
        "data":         json.dumps(job_data),
        "opts":         json.dumps({"attempts": 2, "removeOnComplete": 50}),
        "timestamp":    str(ts),
        "processedOn":  "",
        "finishedOn":   "",
        "returnvalue":  "",
        "stacktrace":   "[]",
        "attemptsMade": "0",
        "delay":        "0",
        "priority":     str(priority),
    })
    r.zadd(f"bull:{queue_name}:wait", {bid: ts})


# ── Scheduler lifecycle ───────────────────────────────────────

def start_scheduler() -> AsyncIOScheduler:
    """
    Create and start the APScheduler instance.
    Call this from the FastAPI lifespan startup block.
    """
    global _scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")

    # ── Job 1: Daily RLA check — 04:00 UTC = 06:00 SAST ──────
    scheduler.add_job(
        daily_rla_check,
        CronTrigger(hour=4, minute=0, timezone="UTC"),
        id="daily_rla_check",
        name="Daily RLA sentinel check",
        replace_existing=True,
        misfire_grace_time=600,   # if API was down, run if we're within 10 min
    )

    # ── Job 2: Container tracker — every 30 min ───────────────
    scheduler.add_job(
        container_tracker,
        IntervalTrigger(minutes=30),
        id="container_tracker",
        name="Container tracking refresh",
        replace_existing=True,
        misfire_grace_time=120,
    )

    # ── Job 3: Notification processor — every 2 min ───────────
    scheduler.add_job(
        notification_processor,
        IntervalTrigger(minutes=2),
        id="notification_processor",
        name="Outbound notification sender",
        replace_existing=True,
        misfire_grace_time=30,
    )

    # ── Job 4: Weekly shadow audit sweep — Mon 05:00 UTC ──────
    scheduler.add_job(
        weekly_shadow_audit_sweep,
        CronTrigger(day_of_week="mon", hour=5, minute=0, timezone="UTC"),
        id="weekly_shadow_audit_sweep",
        name="Automatic weekly shadow audit",
        replace_existing=True,
        misfire_grace_time=1800,
    )

    scheduler.start()
    _scheduler = scheduler

    logger.info("✅ Scheduler started — 4 jobs registered")
    logger.info("   [1] Daily RLA check         — 06:00 SAST daily")
    logger.info("   [2] Container tracker        — every 30 min")
    logger.info("   [3] Notification processor   — every 2 min")
    logger.info("   [4] Shadow audit sweep       — Mon 07:00 SAST")

    return scheduler


def stop_scheduler():
    """Call from FastAPI lifespan shutdown."""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
