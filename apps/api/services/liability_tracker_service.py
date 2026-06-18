"""
CargoIQ — Section 99(2) Personal Liability Tracker
=====================================================
The single most anxiety-inducing feature for a clearing agent who
also does accounting (Ghameeda Idalene profile exactly).

Section 99(2) of the Customs and Excise Act: a clearing agent is
personally liable for customs duties, VAT, and excise if:
  1. The importer provided incorrect information, AND
  2. The importer cannot be found or has no assets when SARS audits

This isn't a theoretical risk. SARS conducted 6,980 seizures worth
R6.7B in 2023/24. Many originated from misdeclarations where the
agent held the bag.

What this tracker does:
  - Maintains a ledger of active importers and their open shipments
  - Estimates the potential duty exposure per importer
  - Flags importers whose RLA status is at risk (suspended = audit trigger)
  - Generates a personal liability report the agent can give their insurer

No new infrastructure — pure Supabase queries over existing tables.
"""
import logging
from datetime import datetime, timedelta
from ..core.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)

# Duty rate estimates by HS chapter for exposure calculation
# When we don't have the exact rate, use the chapter average
HS_CHAPTER_DUTY_ESTIMATES = {
    "01": 0.12, "02": 0.40, "03": 0.20, "04": 0.25,
    "08": 0.15, "09": 0.10, "10": 0.05, "11": 0.10,
    "16": 0.25, "17": 0.20, "18": 0.20, "19": 0.25,
    "20": 0.25, "21": 0.25, "22": 0.20, "24": 0.50,
    "25": 0.05, "27": 0.05, "28": 0.05, "29": 0.05,
    "30": 0.05, "31": 0.05, "32": 0.10, "33": 0.15,
    "34": 0.10, "35": 0.05, "38": 0.05, "39": 0.10,
    "40": 0.10, "42": 0.30, "44": 0.10, "48": 0.10,
    "49": 0.10, "50": 0.45, "51": 0.45, "52": 0.45,
    "53": 0.45, "54": 0.45, "55": 0.45, "56": 0.45,
    "57": 0.45, "58": 0.45, "59": 0.45, "60": 0.45,
    "61": 0.45, "62": 0.45, "63": 0.45,
    "64": 0.30, "65": 0.20, "70": 0.10, "73": 0.10,
    "76": 0.10, "84": 0.05, "85": 0.10, "87": 0.25,
    "90": 0.05, "94": 0.20, "95": 0.15,
    "97": 0.00,  # Artworks — zero duty
}


def _estimate_duty_rate(hs_code: str) -> float:
    """Estimate duty rate from HS chapter when exact rate unknown."""
    if not hs_code or len(hs_code) < 2:
        return 0.15  # Conservative fallback: 15% average
    chapter = hs_code[:2]
    return HS_CHAPTER_DUTY_ESTIMATES.get(chapter, 0.15)


async def get_liability_ledger(org_id: str) -> dict:
    """
    Generate a full Section 99(2) personal liability report
    for a clearing agent.

    Shows:
      - Every active importer code they have cleared for
      - Open/recent shipments per importer
      - Estimated duty exposure if importer defaults or disappears
      - RLA risk flag (suspended importers = highest risk)
      - Total agent liability estimate
    """
    admin = get_supabase_admin()
    since = (datetime.utcnow() - timedelta(days=365)).isoformat()

    # Get all unique importer codes from shipments in the last 12 months
    shipments = admin.table("shipments") \
        .select(
            "id,reference,shipper_name,consignee_name,"
            "hs_code_primary,invoice_value_usd,invoice_currency,"
            "status,created_at,origin_country_code"
        ) \
        .eq("org_id", org_id) \
        .gte("created_at", since) \
        .order("created_at", desc=True) \
        .execute()

    # Get all RLA statuses for this org
    rla_statuses = admin.table("rla_statuses") \
        .select("importer_code,rla_status,last_checked_at") \
        .eq("org_id", org_id) \
        .execute()

    rla_by_code = {
        r["importer_code"]: r
        for r in (rla_statuses.data or [])
    }

    # Group shipments by consignee (proxy for importer)
    by_importer: dict = {}
    for s in (shipments.data or []):
        key = s.get("consignee_name") or "Unknown Importer"
        if key not in by_importer:
            by_importer[key] = {
                "importer_name":     key,
                "shipments":         [],
                "open_shipments":    0,
                "total_value_usd":   0.0,
                "estimated_duty_zar": 0.0,
                "rla_status":        "unknown",
                "last_rla_check":    None,
                "risk_level":        "low",
            }
        by_importer[key]["shipments"].append(s)

        if s["status"] in ("pending", "review_required", "approved"):
            by_importer[key]["open_shipments"] += 1

        if s.get("invoice_value_usd"):
            val_usd = float(s["invoice_value_usd"])
            by_importer[key]["total_value_usd"] += val_usd

            # Estimated duty: value × duty rate × ZAR exchange rate
            duty_rate = _estimate_duty_rate(s.get("hs_code_primary", ""))
            # Use approximate exchange rate — R19.20/USD as baseline
            by_importer[key]["estimated_duty_zar"] += round(
                val_usd * duty_rate * 19.20, 2
            )

    # Apply RLA statuses and risk ratings
    for importer_name, data in by_importer.items():
        # Try to match by importer code in RLA table
        # (In future, store importer_code on shipments directly)
        for code, rla in rla_by_code.items():
            if code.lower() in importer_name.lower():
                data["rla_status"]    = rla["rla_status"]
                data["last_rla_check"] = rla.get("last_checked_at")
                break

        # Risk rating logic
        duty_exposure = data["estimated_duty_zar"]
        rla = data["rla_status"]

        if rla == "suspended":
            data["risk_level"] = "critical"
        elif duty_exposure > 500_000:
            data["risk_level"] = "high"
        elif duty_exposure > 100_000:
            data["risk_level"] = "medium"
        else:
            data["risk_level"] = "low"

        # Remove raw shipment list — too much data for the response
        data["shipment_count"] = len(data.pop("shipments"))

    # Sort by risk then exposure
    risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    importers = sorted(
        by_importer.values(),
        key=lambda x: (risk_order.get(x["risk_level"], 4), -x["estimated_duty_zar"])
    )

    total_exposure = round(sum(i["estimated_duty_zar"] for i in importers), 2)
    critical_count = sum(1 for i in importers if i["risk_level"] == "critical")
    high_count     = sum(1 for i in importers if i["risk_level"] == "high")

    return {
        "generated_at":       datetime.utcnow().isoformat(),
        "period_days":        365,
        "importers":          importers,
        "total_importers":    len(importers),
        "critical_risk_count": critical_count,
        "high_risk_count":    high_count,
        "total_exposure_zar": total_exposure,
        "disclaimer": (
            "Estimated liability under Section 99(2) of the Customs and Excise Act. "
            "Duty rates are estimates based on HS chapter averages. Actual exposure "
            "depends on SARS audit findings. Consult your insurance broker and legal "
            "counsel regarding professional indemnity cover for this exposure."
        ),
    }


async def get_importer_exposure(org_id: str, importer_name: str) -> dict:
    """Drill down into a specific importer's shipment history and exposure."""
    admin = get_supabase_admin()
    since = (datetime.utcnow() - timedelta(days=365)).isoformat()

    shipments = admin.table("shipments") \
        .select("*") \
        .eq("org_id", org_id) \
        .ilike("consignee_name", f"%{importer_name}%") \
        .gte("created_at", since) \
        .order("created_at", desc=True) \
        .execute()

    items = []
    for s in (shipments.data or []):
        val_usd   = float(s.get("invoice_value_usd") or 0)
        duty_rate = _estimate_duty_rate(s.get("hs_code_primary", ""))
        duty_zar  = round(val_usd * duty_rate * 19.20, 2)

        items.append({
            "reference":     s.get("reference"),
            "status":        s.get("status"),
            "origin":        s.get("origin_country_code"),
            "hs_code":       s.get("hs_code_primary"),
            "invoice_usd":   val_usd,
            "duty_rate_est": f"{duty_rate*100:.0f}%",
            "duty_zar_est":  duty_zar,
            "created_at":    s.get("created_at"),
        })

    total_exposure = round(sum(i["duty_zar_est"] for i in items), 2)

    return {
        "importer_name":   importer_name,
        "shipment_count":  len(items),
        "shipments":       items,
        "total_exposure_zar": total_exposure,
    }
