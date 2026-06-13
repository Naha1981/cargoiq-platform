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


# ── Charge Notice ("Double-Tap to Invoice") ─────────────────
# Same HTML→print pattern as the Savings Certificate and the
# Carrier Dispute Notice. One click on a pending waiting-time
# finding produces a printable accessorial charge notice the
# client can be billed against — no Excel, no "I'll do it later".

def generate_charge_notice_html(finding: dict, org_name: str, reference_label: str = "") -> str:
    """
    Generate a printable Accessorial Charge Notice for a single
    waiting-time finding. Open in browser, print to PDF, attach to
    the client invoice or send directly.
    """
    arrived_at  = datetime.fromisoformat(finding["arrived_at"].replace("Z", "+00:00"))
    departed_at = datetime.fromisoformat(finding["departed_at"].replace("Z", "+00:00"))
    total_minutes    = finding.get("total_minutes") or int((departed_at - arrived_at).total_seconds() / 60)
    free_minutes     = finding.get("free_minutes", DEFAULT_FREE_MINUTES)
    billable_minutes = finding.get("billable_minutes") or max(0, total_minutes - free_minutes)
    rate             = float(finding.get("rate_per_hour_zar", DEFAULT_RATE_PER_HOUR_ZAR))
    amount           = float(finding.get("unbilled_revenue_zar") or 0)

    def hm(minutes: int) -> str:
        h, m = divmod(int(minutes), 60)
        return f"{h}h {m}m"

    generated_at = datetime.utcnow().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
  * {{ box-sizing: border-box; margin:0; padding:0; }}
  body {{ font-family: -apple-system, Arial, sans-serif; font-size: 13px; color:#0D1B2A; padding: 48px 56px; }}
  .header {{ display:flex; justify-content:space-between; align-items:flex-start;
             padding-bottom: 24px; border-bottom: 3px solid #1A2332; margin-bottom: 28px; }}
  .logo {{ font-family: monospace; font-size: 20px; font-weight:700; color:#1A2332; }}
  .logo span {{ color:#B8860B; }}
  .title {{ text-align:right; }}
  .title h1 {{ font-size: 11px; letter-spacing:0.15em; text-transform:uppercase; color:#6B7E92; }}
  .title .ref {{ font-size: 16px; font-weight:700; margin-top:4px; }}
  .meta {{ margin-bottom: 24px; font-size: 13px; line-height:1.8; }}
  .meta strong {{ color:#6B7E92; font-weight:600; display:inline-block; width:180px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom: 24px; }}
  th {{ text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:0.08em;
        color:#6B7E92; padding-bottom:8px; border-bottom:1px solid #DDE3EA; }}
  th:last-child {{ text-align:right; }}
  td {{ padding: 8px 0; border-bottom:1px solid #EEF1F4; font-size:13px; }}
  td:last-child {{ text-align:right; font-family:monospace; }}
  .total-row td {{ border-top:2px solid #1A2332; border-bottom:none; font-weight:700; padding-top:12px; font-size:15px; }}
  .footer {{ margin-top: 40px; font-size:11px; color:#9AAAB8; border-top:1px solid #E8ECF1; padding-top:14px; }}
  .evidence {{ background:#F1F4F8; border-radius:4px; padding:12px 16px; font-size:12px;
               color:#6B7E92; margin-top: 8px; }}
</style></head>
<body>
  <div class="header">
    <div class="logo">Cargo<span>IQ</span></div>
    <div class="title">
      <h1>Accessorial Charge Notice</h1>
      <div class="ref">{finding.get('reference') or reference_label or '—'}</div>
    </div>
  </div>

  <div class="meta">
    <div><strong>Issued by</strong> {org_name}</div>
    <div><strong>Location</strong> {finding.get('location_name') or 'Not specified'}</div>
    <div><strong>Arrived</strong> {arrived_at.strftime('%d %b %Y, %H:%M')}</div>
    <div><strong>Departed</strong> {departed_at.strftime('%d %b %Y, %H:%M')}</div>
    <div><strong>Date Issued</strong> {generated_at}</div>
  </div>

  <table>
    <thead><tr><th>Description</th><th>Amount</th></tr></thead>
    <tbody>
      <tr><td>Total time on site</td><td>{hm(total_minutes)}</td></tr>
      <tr><td>Free time allowance</td><td>{hm(free_minutes)}</td></tr>
      <tr><td>Billable waiting time @ R{rate:,.2f}/hour</td><td>{hm(billable_minutes)}</td></tr>
      <tr class="total-row">
        <td>Total Accessorial Charge</td>
        <td>R{amount:,.2f}</td>
      </tr>
    </tbody>
  </table>

  <div class="evidence">
    <strong>Evidence:</strong> Driver check-in recorded via WhatsApp at the time of arrival
    and departure. Timestamps are system-generated and available on request.
  </div>

  <div class="footer">
    Generated by CargoIQ Driver Check-In · {org_name} · {generated_at}
  </div>
</body></html>"""
