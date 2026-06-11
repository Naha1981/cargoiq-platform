"""
CargoIQ — Shadow Audit Service
================================
The "Forensic Discovery" — run historical shipments through
the Compliance Shield and Extraction pipeline WITHOUT touching
live operations. Shows the CEO: "We found R18,600 in your
last 100 shipments. Your staff marked them as perfect."

This is the zero-risk proof that closes the deal.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional
from ..core.supabase_client import get_supabase_admin
from .compliance_service import run_compliance_shield

logger = logging.getLogger(__name__)


async def run_shadow_audit(
    org_id: str,
    shipment_ids: Optional[list] = None,
    days_back: int = 30,
    max_shipments: int = 100,
) -> dict:
    """
    Run compliance checks on historical (already-processed) shipments.
    Returns a forensic report showing what was missed.

    Used for:
      - Pre-sale demo: show prospect what their existing data missed
      - Monthly audit: verify compliance quality over time
    """
    admin    = get_supabase_admin()
    audit_id = str(uuid.uuid4())
    started  = datetime.utcnow()

    logger.info(f"Shadow audit started: org={org_id} max={max_shipments}")

    # ── Fetch shipments to audit ────────────────────────────
    if shipment_ids:
        q = admin.table("shipments").select("*")             .eq("org_id", org_id)             .in_("id", shipment_ids[:max_shipments])
    else:
        since = (datetime.utcnow() - timedelta(days=days_back)).isoformat()
        q = admin.table("shipments").select("*")             .eq("org_id", org_id)             .in_("status", ["approved", "in_cargowise", "rejected"])             .gte("created_at", since)             .order("created_at", desc=True)             .limit(max_shipments)

    shipments = q.execute()

    if not shipments.data:
        return {
            "audit_id": audit_id,
            "status":   "empty",
            "message":  "No completed shipments found for audit period",
        }

    total     = len(shipments.data)
    findings  = []
    penalties_prevented_zar = 0
    errors_found = 0

    # ── Run Compliance Shield on each ───────────────────────
    for s in shipments.data:
        report = run_compliance_shield(
            shipment=s,
            documents=[],
            org_id=org_id,
            run_da65=True,
            run_da179=True,
        )

        if report.overall != "pass":
            errors_found += 1
            penalty_total = 0

            failing_modules = [
                m for m in report.modules
                if m.result in ("fail", "hold")
            ]

            for m in failing_modules:
                if m.penalty_risk:
                    penalty_total += 4500  # R4,500 SARS standard fine

            penalties_prevented_zar += penalty_total

            findings.append({
                "shipment_id":   s["id"],
                "reference":     s.get("reference"),
                "shipper":       s.get("shipper_name"),
                "consignee":     s.get("consignee_name"),
                "shield_result": report.overall,
                "penalty_risk":  report.penalty_risk_detected,
                "modules_failed": [
                    {
                        "module":     m.module,
                        "result":     m.result,
                        "resolution": m.resolution,
                        "penalty_zar": 4500 if m.penalty_risk else 0,
                    }
                    for m in failing_modules
                ],
                "total_penalty_zar": penalty_total,
            })

    # ── Calculate summary metrics ───────────────────────────
    pass_count     = total - errors_found
    error_rate     = round(errors_found / total * 100, 1) if total > 0 else 0
    pass_rate      = round(pass_count / total * 100, 1) if total > 0 else 0

    # Estimate unbilled waiting time
    # Proxy: shipments that took > 7 days from creation to approval
    unbilled_waiting_zar = 0
    for s in shipments.data:
        if s.get("created_at") and s.get("reviewed_at"):
            created  = datetime.fromisoformat(s["created_at"].replace("Z",""))
            reviewed = datetime.fromisoformat(s["reviewed_at"].replace("Z",""))
            days     = (reviewed - created).days
            if days > 7:
                # Conservative: 2 hours unbilled wait per day over 7
                extra_hours          = (days - 7) * 2
                unbilled_waiting_zar += extra_hours * 550  # R550/hour

    total_value_zar = penalties_prevented_zar + unbilled_waiting_zar

    duration_seconds = (datetime.utcnow() - started).total_seconds()

    result = {
        "audit_id":    audit_id,
        "org_id":      org_id,
        "status":      "completed",
        "period_days": days_back,
        "summary": {
            "shipments_audited":         total,
            "errors_found":              errors_found,
            "clean_shipments":           pass_count,
            "error_rate_pct":            error_rate,
            "pass_rate_pct":             pass_rate,
            "penalties_prevented_zar":   penalties_prevented_zar,
            "unbilled_waiting_zar":      round(unbilled_waiting_zar, 2),
            "total_value_identified_zar": round(total_value_zar, 2),
            "cargoiq_commission_zar":     round(total_value_zar * 0.20, 2),
            "net_client_benefit_zar":     round(total_value_zar * 0.80, 2),
        },
        "findings":        findings[:20],  # Top 20 findings
        "findings_count":  len(findings),
        "duration_seconds": round(duration_seconds, 1),
        "generated_at":    datetime.utcnow().isoformat(),
    }

    # Store audit record
    admin.table("shadow_audits").upsert({
        "id":           audit_id,
        "org_id":       org_id,
        "summary":      result["summary"],
        "findings":     findings,
        "status":       "completed",
        "created_at":   started.isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
    }).execute()

    logger.info(
        f"Shadow audit complete: {total} shipments, "
        f"{errors_found} errors, R{total_value_zar:,.0f} identified"
    )

    return result
