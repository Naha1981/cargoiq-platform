"""
CargoIQ — Driver Check-In Waiting Time Tracker
=================================================
A lightweight, text-based version of the "Recovery Engine" idea —
no GPS devices, no Traccar, no PostGIS.

Flow:
  Driver sends WhatsApp message: "ARRIVED CIQ-2026-00247 Durban Pier 2"
  Driver later sends:            "DEPARTED CIQ-2026-00247"

CargoIQ pairs the two timestamps, subtracts free time (default 2h),
and calculates unbilled accessorial revenue at R350/hour.

This captures the same "found revenue" story as the GPS-based
Recovery Engine, using a channel every driver already has —
WhatsApp — and zero new infrastructure.
"""
import logging
import re
from datetime import datetime
from typing import Optional
from ..core.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)

# Matches: "ARRIVED CIQ-2026-00247 Durban Pier 2"
#          "DEPARTED CIQ-2026-00247"
#          "arrived ciq-2026-00247"
CHECKIN_PATTERN = re.compile(
    r"^\s*(ARRIVED|DEPARTED)\s+([A-Za-z0-9\-]+)\s*(.*)$",
    re.IGNORECASE,
)

DEFAULT_FREE_MINUTES = 120        # 2 hours free time
DEFAULT_RATE_PER_HOUR_ZAR = 350.0


def parse_checkin_message(text: str) -> Optional[dict]:
    """
    Parse a WhatsApp text message for an ARRIVED/DEPARTED check-in.
    Returns None if the message doesn't match the expected format.
    """
    match = CHECKIN_PATTERN.match(text.strip())
    if not match:
        return None

    event_word, reference, rest = match.groups()
    return {
        "event_type":    event_word.lower(),
        "reference":     reference.upper(),
        "location_name": rest.strip() or None,
    }


async def record_driver_checkin(
    org_id: str,
    driver_phone: str,
    raw_message: str,
    driver_name: Optional[str] = None,
) -> Optional[dict]:
    """
    Process an inbound WhatsApp message from a driver.
    If it matches the ARRIVED/DEPARTED pattern, record the check-in
    and — if this completes an arrived→departed pair — compute the
    waiting time finding.

    Returns the check-in record + finding (if computed), or None if
    the message wasn't a recognised check-in.
    """
    parsed = parse_checkin_message(raw_message)
    if not parsed:
        return None

    admin = get_supabase_admin()

    # Try to resolve to a real shipment by reference
    shipment_id = None
    shipment_lookup = admin.table("shipments") \
        .select("id") \
        .eq("org_id", org_id) \
        .eq("reference", parsed["reference"]) \
        .limit(1).execute()
    if shipment_lookup.data:
        shipment_id = shipment_lookup.data[0]["id"]

    record = {
        "org_id":        org_id,
        "shipment_id":   shipment_id,
        "reference":     parsed["reference"],
        "driver_phone":  driver_phone,
        "driver_name":   driver_name,
        "location_name": parsed["location_name"],
        "event_type":    parsed["event_type"],
        "raw_message":   raw_message,
        "event_time":    datetime.utcnow().isoformat(),
    }

    inserted = admin.table("driver_checkins").insert(record).execute()
    checkin = inserted.data[0] if inserted.data else record

    finding = None
    if parsed["event_type"] == "departed":
        finding = await _try_compute_waiting_time(org_id, parsed["reference"], driver_phone)

    return {"checkin": checkin, "finding": finding}


async def _try_compute_waiting_time(
    org_id: str, reference: str, driver_phone: str
) -> Optional[dict]:
    """
    Find the most recent unmatched "arrived" check-in for this
    reference + driver, pair it with the just-recorded "departed",
    and compute the waiting time finding if free time was exceeded.
    """
    admin = get_supabase_admin()

    # Most recent arrived check-in for this reference that hasn't
    # already produced a finding (simple heuristic: just take the
    # latest arrived event before now)
    arrived = admin.table("driver_checkins") \
        .select("*") \
        .eq("org_id", org_id) \
        .eq("reference", reference) \
        .eq("driver_phone", driver_phone) \
        .eq("event_type", "arrived") \
        .order("event_time", desc=True) \
        .limit(1).execute()

    departed = admin.table("driver_checkins") \
        .select("*") \
        .eq("org_id", org_id) \
        .eq("reference", reference) \
        .eq("driver_phone", driver_phone) \
        .eq("event_type", "departed") \
        .order("event_time", desc=True) \
        .limit(1).execute()

    if not arrived.data or not departed.data:
        return None

    arrived_at  = datetime.fromisoformat(arrived.data[0]["event_time"].replace("Z", "+00:00"))
    departed_at = datetime.fromisoformat(departed.data[0]["event_time"].replace("Z", "+00:00"))

    if departed_at <= arrived_at:
        return None  # malformed pair — ignore

    total_minutes    = int((departed_at - arrived_at).total_seconds() / 60)
    billable_minutes = max(0, total_minutes - DEFAULT_FREE_MINUTES)
    unbilled_revenue = round((billable_minutes / 60) * DEFAULT_RATE_PER_HOUR_ZAR, 2)

    record = {
        "org_id":              org_id,
        "shipment_id":         arrived.data[0].get("shipment_id"),
        "reference":           reference,
        "driver_phone":        driver_phone,
        "location_name":       arrived.data[0].get("location_name"),
        "arrived_at":          arrived.data[0]["event_time"],
        "departed_at":         departed.data[0]["event_time"],
        "free_minutes":        DEFAULT_FREE_MINUTES,
        "billable_minutes":    billable_minutes,
        "rate_per_hour_zar":   DEFAULT_RATE_PER_HOUR_ZAR,
        "unbilled_revenue_zar": unbilled_revenue,
        "status":              "identified",
    }

    inserted = admin.table("waiting_time_findings").insert(record).execute()
    result = inserted.data[0] if inserted.data else record

    if unbilled_revenue > 0:
        logger.info(
            f"Waiting time finding: {reference} — "
            f"{billable_minutes}min billable, R{unbilled_revenue} unbilled revenue"
        )

    return result


async def get_waiting_time_summary(org_id: str) -> dict:
    """Summary for the dashboard / Savings Certificate."""
    admin = get_supabase_admin()
    findings = admin.table("waiting_time_findings") \
        .select("unbilled_revenue_zar,status") \
        .eq("org_id", org_id).execute()

    rows = findings.data or []
    total_unbilled = sum(float(r.get("unbilled_revenue_zar") or 0) for r in rows)
    identified     = [r for r in rows if r["status"] == "identified"]

    return {
        "findings_count":        len(rows),
        "pending_count":         len(identified),
        "total_unbilled_zar":    round(total_unbilled, 2),
        "pending_unbilled_zar":  round(sum(float(r.get("unbilled_revenue_zar") or 0) for r in identified), 2),
    }
