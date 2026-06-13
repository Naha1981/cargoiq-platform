"""
CargoIQ — Analytics Router
Dashboard KPIs, processing volume, compliance summary.
"""
import logging
from datetime import datetime, timedelta, date
from fastapi import APIRouter, Depends, Query
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin

router = APIRouter(prefix="/analytics", tags=["Analytics"])
logger = logging.getLogger(__name__)


@router.get("/dashboard")
async def get_dashboard_kpis(
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Main dashboard KPIs:
    - Queue size (pending + review_required)
    - Processed today
    - Automation rate (auto-approved / total)
    - Exceptions requiring review
    - Compliance flags today
    """
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()

    # Queue size
    queue = admin.table("shipments") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .in_("status", ["pending", "review_required", "extracted"]) \
        .execute()
    queue_size = queue.count or 0

    # Processed today
    processed = admin.table("shipments") \
        .select("id,status", count="exact") \
        .eq("org_id", org_id) \
        .in_("status", ["approved", "in_cargowise", "rejected"]) \
        .gte("updated_at", today_start) \
        .execute()
    processed_today = processed.count or 0

    # Auto-approved today (approved without human edits — high confidence)
    # Proxy: approved shipments where overall_confidence = high
    auto_approved = admin.table("shipments") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .eq("status", "approved") \
        .eq("overall_confidence", "high") \
        .gte("updated_at", today_start) \
        .execute()
    auto_approved_count = auto_approved.count or 0

    automation_rate = (
        round((auto_approved_count / processed_today) * 100, 1)
        if processed_today > 0 else 0.0
    )

    # Exceptions requiring review
    exceptions = admin.table("shipments") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .eq("status", "review_required") \
        .execute()
    exceptions_count = exceptions.count or 0

    # Compliance flags today
    flags = admin.table("compliance_events") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .in_("result", ["hold", "fail"]) \
        .gte("created_at", today_start) \
        .execute()
    compliance_flags = flags.count or 0

    # Average processing time (last 7 days)
    avg_result = admin.table("shipments") \
        .select("processing_duration_ms") \
        .eq("org_id", org_id) \
        .not_.is_("processing_duration_ms", "null") \
        .gte("created_at", (datetime.utcnow() - timedelta(days=7)).isoformat()) \
        .execute()

    avg_time = None
    if avg_result.data:
        times = [r["processing_duration_ms"] for r in avg_result.data if r.get("processing_duration_ms")]
        if times:
            avg_time = round(sum(times) / len(times) / 1000, 1)  # Convert to seconds

    return {
        "queue_size": queue_size,
        "processed_today": processed_today,
        "automation_rate": automation_rate,
        "exceptions_requiring_review": exceptions_count,
        "compliance_flags_today": compliance_flags,
        "avg_processing_time_seconds": avg_time,
        "generated_at": datetime.utcnow().isoformat(),
    }


@router.get("/volume")
async def get_processing_volume(
    days: int = Query(30, ge=7, le=90),
    current_user: dict = Depends(get_current_user_with_org)
):
    """Daily shipment processing volume for the last N days."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    result = admin.table("shipments") \
        .select("created_at,status,overall_confidence") \
        .eq("org_id", org_id) \
        .gte("created_at", since) \
        .execute()

    # Aggregate by day
    daily: dict = {}
    for row in result.data:
        day = row["created_at"][:10]
        if day not in daily:
            daily[day] = {"date": day, "total": 0, "auto_approved": 0, "manual_reviewed": 0, "failed": 0}
        daily[day]["total"] += 1
        if row["status"] in ("approved", "in_cargowise") and row.get("overall_confidence") == "high":
            daily[day]["auto_approved"] += 1
        elif row["status"] in ("approved", "in_cargowise"):
            daily[day]["manual_reviewed"] += 1
        elif row["status"] in ("error", "rejected"):
            daily[day]["failed"] += 1

    # Fill missing days with zeros
    chart_data = []
    for i in range(days):
        day = (datetime.utcnow() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        chart_data.append(daily.get(day, {
            "date": day, "total": 0, "auto_approved": 0, "manual_reviewed": 0, "failed": 0
        }))

    return {"data": chart_data, "days": days}


@router.get("/compliance-summary")
async def get_compliance_summary(
    days: int = Query(30, ge=7, le=90),
    current_user: dict = Depends(get_current_user_with_org)
):
    """Compliance Shield results breakdown for the last N days."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    # Shield status breakdown
    shields = admin.table("shipments") \
        .select("shield_status") \
        .eq("org_id", org_id) \
        .not_.is_("shield_status", "null") \
        .gte("created_at", since) \
        .execute()

    counts = {"pass": 0, "hold": 0, "fail": 0, "pending": 0}
    for row in shields.data:
        s = row.get("shield_status", "pending")
        counts[s] = counts.get(s, 0) + 1

    total = sum(counts.values())
    pass_rate = round((counts["pass"] / total * 100), 1) if total > 0 else 0

    # Top compliance modules causing failures
    events = admin.table("compliance_events") \
        .select("module,result") \
        .eq("org_id", org_id) \
        .in_("result", ["hold", "fail"]) \
        .gte("created_at", since) \
        .execute()

    module_counts: dict = {}
    for ev in events.data:
        m = ev["module"]
        module_counts[m] = module_counts.get(m, 0) + 1

    top_modules = sorted(
        [{"module": m, "count": c} for m, c in module_counts.items()],
        key=lambda x: x["count"],
        reverse=True
    )

    # Penalty risk count
    penalty_risks = admin.table("compliance_events") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .eq("penalty_risk", True) \
        .gte("created_at", since) \
        .execute()

    return {
        "period_days": days,
        "shield_breakdown": counts,
        "total_shipments": total,
        "pass_rate_pct": pass_rate,
        "penalty_risk_events": penalty_risks.count or 0,
        "top_failing_modules": top_modules,
    }


@router.get("/roi")
async def get_roi_summary(
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    ROI metrics: time saved, errors prevented, estimated financial impact.
    Based on industry benchmarks:
    - Manual entry: 42 minutes per shipment
    - Avg SA operations staff cost: R180/hour
    - SARS penalty per error: R4,500
    """
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    MANUAL_MINUTES_PER_SHIPMENT = 42
    AI_MINUTES_PER_SHIPMENT = 3
    STAFF_COST_PER_HOUR_ZAR = 180
    SARS_PENALTY_PER_ERROR_ZAR = 4500

    # Total processed shipments
    total = admin.table("shipments") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .in_("status", ["approved", "in_cargowise"]) \
        .execute()
    total_count = total.count or 0

    # Compliance events prevented (hold + fail = would have been errors)
    prevented = admin.table("compliance_events") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .eq("penalty_risk", True) \
        .execute()
    errors_prevented = prevented.count or 0

    # Calculate savings
    time_saved_minutes = total_count * (MANUAL_MINUTES_PER_SHIPMENT - AI_MINUTES_PER_SHIPMENT)
    time_saved_hours = time_saved_minutes / 60
    labour_saved_zar = round(time_saved_hours * STAFF_COST_PER_HOUR_ZAR, 2)
    penalties_prevented_zar = errors_prevented * SARS_PENALTY_PER_ERROR_ZAR

    return {
        "total_shipments_processed": total_count,
        "errors_prevented": errors_prevented,
        "time_saved_minutes": time_saved_minutes,
        "time_saved_hours": round(time_saved_hours, 1),
        "labour_cost_saved_zar": labour_saved_zar,
        "sars_penalties_prevented_zar": penalties_prevented_zar,
        "total_value_delivered_zar": round(labour_saved_zar + penalties_prevented_zar, 2),
        "benchmarks": {
            "manual_minutes_per_shipment": MANUAL_MINUTES_PER_SHIPMENT,
            "ai_minutes_per_shipment": AI_MINUTES_PER_SHIPMENT,
            "staff_cost_per_hour_zar": STAFF_COST_PER_HOUR_ZAR,
            "sars_penalty_per_error_zar": SARS_PENALTY_PER_ERROR_ZAR,
        }
    }


@router.get("/waiting-time")
async def waiting_time_analytics(
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Unbilled waiting-time revenue identified via WhatsApp driver
    check-ins (ARRIVED/DEPARTED). No GPS or Traccar required —
    drivers text the gate times, CargoIQ does the rest.
    """
    from ..services.driver_checkin_service import get_waiting_time_summary
    return await get_waiting_time_summary(current_user["org_id"])


@router.get("/waiting-time/findings")
async def waiting_time_findings(
    status: str = Query("identified"),
    current_user: dict = Depends(get_current_user_with_org)
):
    """List individual waiting-time findings for review/invoicing."""
    admin  = get_supabase_admin()
    org_id = current_user["org_id"]

    q = admin.table("waiting_time_findings").select("*").eq("org_id", org_id)
    if status:
        q = q.eq("status", status)

    result = q.order("created_at", desc=True).limit(50).execute()
    return result.data
