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


# ── Proof Page (no-login share link) ────────────────────────
# "Text Karel-Jan a link before the call instead of describing it."
# Renders a redacted summary: aggregate numbers in full, but the
# CargoIQ commission split and internal IDs are hidden, and each
# finding's third-party names (shipper/consignee) are stripped —
# only the reference, the issue, and the fix are shown.

def generate_proof_page_html(audit: dict, org_name: str) -> str:
    """Generate a public, no-login 'Proof Page' for a shadow audit."""
    summary  = audit.get("summary", {})
    findings = audit.get("findings", []) or []

    def zar(amount) -> str:
        return f"R{abs(float(amount or 0)):,.0f}"

    def mask_ref(ref: str) -> str:
        if not ref or len(ref) < 4:
            return ref or "—"
        return ref[:-3] + "•••"

    total_value   = summary.get("total_value_identified_zar", 0)
    errors_found  = summary.get("errors_found", 0)
    audited       = summary.get("shipments_audited", 0)
    pass_rate     = summary.get("pass_rate_pct", 0)
    penalties     = summary.get("penalties_prevented_zar", 0)
    unbilled      = summary.get("unbilled_waiting_zar", 0)

    finding_rows = ""
    for f in findings[:5]:
        issues = ", ".join(
            m["module"].replace("_", " ").title() for m in f.get("modules_failed", [])
        ) or "Compliance flag"
        top_resolution = ""
        for m in f.get("modules_failed", []):
            if m.get("resolution"):
                top_resolution = m["resolution"]
                break
        finding_rows += f"""
        <tr>
          <td class="ref">{mask_ref(f.get('reference',''))}</td>
          <td>{issues}</td>
          <td class="muted">{top_resolution or '—'}</td>
          <td class="amount">{zar(f.get('total_penalty_zar', 0))}</td>
        </tr>"""

    generated_at = datetime.utcnow().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CargoIQ — Shadow Audit Findings for {org_name}</title>
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,Arial,sans-serif; background:#F1F4F8; color:#0D1B2A; padding: 32px 16px; }}
  .page {{ max-width: 760px; margin: 0 auto; background:#fff; border-radius:12px; overflow:hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
  .header {{ background:linear-gradient(135deg,#1A2332 0%,#243447 100%); color:#F1F4F8; padding: 32px 36px; }}
  .logo {{ font-family:monospace; font-size:18px; font-weight:700; margin-bottom: 16px; }}
  .logo span {{ color:#B8860B; }}
  .header h1 {{ font-size: 13px; font-weight:600; letter-spacing:0.1em; text-transform:uppercase; color:#C8D3DF; }}
  .header .org {{ font-size: 24px; font-weight:700; margin-top:6px; }}
  .hero {{ padding: 32px 36px; border-bottom:1px solid #EEF1F4; }}
  .hero-value {{ font-family:monospace; font-size: 44px; font-weight:700; color:#B8860B; line-height:1; }}
  .hero-label {{ font-size: 12px; color:#6B7E92; margin-top: 8px; }}
  .grid {{ display:grid; grid-template-columns: repeat(3,1fr); gap:1px; background:#EEF1F4; }}
  .stat {{ background:#fff; padding:20px 24px; }}
  .stat-value {{ font-family:monospace; font-size: 22px; font-weight:700; color:#0D1B2A; }}
  .stat-label {{ font-size: 11px; color:#9AAAB8; text-transform:uppercase; letter-spacing:0.06em; margin-top:4px; }}
  .findings {{ padding: 28px 36px; }}
  .findings h2 {{ font-size: 11px; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#6B7E92; margin-bottom:14px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:0.06em; color:#9AAAB8; padding-bottom:8px; border-bottom:1px solid #EEF1F4; }}
  td {{ padding: 10px 0; font-size:13px; border-bottom:1px solid #F6F8FA; vertical-align:top; }}
  .ref {{ font-family:monospace; color:#B8860B; font-weight:600; white-space:nowrap; }}
  .amount {{ font-family:monospace; color:#9B1C1C; font-weight:600; text-align:right; white-space:nowrap; }}
  .muted {{ color:#6B7E92; font-size:12px; }}
  .cta {{ padding: 28px 36px; background:#F1F4F8; text-align:center; }}
  .cta p {{ font-size: 13px; color:#0D1B2A; line-height:1.6; margin-bottom: 4px; }}
  .cta .small {{ font-size:11px; color:#9AAAB8; margin-top:12px; }}
  .footer {{ text-align:center; font-size:10px; color:#9AAAB8; padding: 16px; }}
</style></head>
<body>
  <div class="page">
    <div class="header">
      <div class="logo">Cargo<span>IQ</span></div>
      <h1>Shadow Audit — Sample Findings</h1>
      <div class="org">{org_name}</div>
    </div>

    <div class="hero">
      <div class="hero-value">{zar(total_value)}</div>
      <div class="hero-label">in identified value across {audited} historical shipments — found automatically, at no cost, before any contract was signed.</div>
    </div>

    <div class="grid">
      <div class="stat"><div class="stat-value">{audited}</div><div class="stat-label">Shipments Audited</div></div>
      <div class="stat"><div class="stat-value">{errors_found}</div><div class="stat-label">Issues Found</div></div>
      <div class="stat"><div class="stat-value">{pass_rate}%</div><div class="stat-label">Clean Pass Rate</div></div>
      <div class="stat"><div class="stat-value">{zar(penalties)}</div><div class="stat-label">Penalty Risk Identified</div></div>
      <div class="stat"><div class="stat-value">{zar(unbilled)}</div><div class="stat-label">Unbilled Revenue Found</div></div>
      <div class="stat"><div class="stat-value">{generated_at}</div><div class="stat-label">Audit Date</div></div>
    </div>

    {f'''<div class="findings">
      <h2>Sample Findings (top {min(5,len(findings))} of {len(findings)})</h2>
      <table>
        <thead><tr><th>Reference</th><th>Issue</th><th>Recommended Fix</th><th>Risk</th></tr></thead>
        <tbody>{finding_rows}</tbody>
      </table>
    </div>''' if findings else ''}

    <div class="cta">
      <p><strong>This was generated automatically from {org_name}'s own historical shipment data.</strong></p>
      <p>No software was installed and no workflow was changed to produce this report.</p>
      <p class="small">To see the full findings report and discuss a pilot, contact the CargoIQ team.</p>
    </div>

    <div class="footer">Generated by CargoIQ · cargoiq.co.za · {generated_at}</div>
  </div>
</body></html>"""
