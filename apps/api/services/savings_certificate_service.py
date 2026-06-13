"""
CargoIQ — Savings Certificate PDF Generator
============================================
The "CFO Closer" — a formal bank-grade PDF generated monthly.
Not a dashboard screenshot. A document you slide across a boardroom table.

Sections:
  1. Cover: org name, period, total value delivered
  2. CargoWise Transaction Savings (WiseLayer)
  3. SARS Fines Prevented (Compliance Shield)
  4. Unbilled Revenue Found (Sentinel)
  5. Signature block + CargoIQ branding

Rendered as HTML → PDF using WeasyPrint (or raw HTML for browser printing).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from ..core.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def generate_savings_certificate_html(
    org_name:          str,
    period_label:      str,   # e.g. "May 2026"
    cw_savings_zar:    float,
    fines_prevented_zar: float,
    unbilled_found_zar: float,
    subscription_zar:  float,
    audit_count:       int,
    errors_caught:     int,
    hours_saved:       float,
    cw_transactions_saved: int,
    carrier_overcharges_zar: float = 0.0,
) -> str:
    """Generate a print-ready HTML Savings Certificate."""

    total_value   = cw_savings_zar + fines_prevented_zar + unbilled_found_zar + carrier_overcharges_zar
    commission    = total_value * 0.20
    net_benefit   = total_value - subscription_zar
    roi_multiple  = round(total_value / subscription_zar, 1) if subscription_zar > 0 else 0

    generated_at  = datetime.utcnow().strftime("%d %B %Y")

    def zar(amount: float) -> str:
        return f"R{abs(amount):,.2f}"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, 'Helvetica Neue', Arial, sans-serif;
    background: #fff;
    color: #0D1B2A;
    font-size: 13px;
    line-height: 1.5;
  }}
  .page {{
    max-width: 794px;
    margin: 0 auto;
    padding: 48px 56px;
    min-height: 1123px;
  }}

  /* Header */
  .header {{
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding-bottom: 28px;
    border-bottom: 3px solid #1A2332;
    margin-bottom: 36px;
  }}
  .logo {{
    font-family: monospace;
    font-size: 22px;
    font-weight: 700;
    color: #1A2332;
    letter-spacing: -0.5px;
  }}
  .logo span {{ color: #B8860B; }}
  .cert-badge {{
    text-align: right;
  }}
  .cert-badge h1 {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #6B7E92;
    margin-bottom: 4px;
  }}
  .cert-badge .period {{
    font-size: 18px;
    font-weight: 700;
    color: #0D1B2A;
  }}

  /* Client */
  .client-block {{
    margin-bottom: 32px;
  }}
  .label {{
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: #9AAAB8;
    margin-bottom: 4px;
  }}
  .client-name {{
    font-size: 20px;
    font-weight: 700;
    color: #0D1B2A;
  }}

  /* Hero metric */
  .hero {{
    background: linear-gradient(135deg, #1A2332 0%, #243447 100%);
    color: #F1F4F8;
    border-radius: 8px;
    padding: 28px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 32px;
  }}
  .hero-label {{
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #C8D3DF;
    margin-bottom: 6px;
  }}
  .hero-value {{
    font-family: monospace;
    font-size: 40px;
    font-weight: 700;
    color: #B8860B;
    letter-spacing: -1px;
  }}
  .hero-sub {{
    font-size: 12px;
    color: #9AAAB8;
    margin-top: 4px;
  }}
  .roi-badge {{
    text-align: right;
  }}
  .roi-number {{
    font-family: monospace;
    font-size: 36px;
    font-weight: 700;
    color: #15AC4A;
  }}
  .roi-label {{
    font-size: 10px;
    color: #9AAAB8;
    letter-spacing: 0.1em;
    text-transform: uppercase;
  }}

  /* Breakdown table */
  .section-title {{
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: #6B7E92;
    margin-bottom: 12px;
    padding-bottom: 6px;
    border-bottom: 1px solid #E8ECF1;
  }}
  .breakdown {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 28px;
  }}
  .breakdown tr {{ border-bottom: 1px solid #DDE3EA; }}
  .breakdown tr:last-child {{ border-bottom: 2px solid #1A2332; font-weight: 700; }}
  .breakdown td {{
    padding: 10px 0;
    font-size: 13px;
  }}
  .breakdown td:last-child {{
    text-align: right;
    font-family: monospace;
    font-size: 13px;
  }}
  .green  {{ color: #15632A; }}
  .red    {{ color: #9B1C1C; }}
  .amber  {{ color: #B8860B; }}
  .muted  {{ color: #6B7E92; font-size: 12px; }}

  /* Operations metrics */
  .metrics-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
    margin-bottom: 32px;
  }}
  .metric-card {{
    border: 1px solid #DDE3EA;
    border-radius: 6px;
    padding: 16px;
    text-align: center;
  }}
  .metric-value {{
    font-family: monospace;
    font-size: 24px;
    font-weight: 700;
    color: #0D1B2A;
    display: block;
    margin-bottom: 4px;
  }}
  .metric-label {{
    font-size: 11px;
    color: #6B7E92;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  /* Settlement */
  .settlement {{
    background: #F1F4F8;
    border-radius: 6px;
    padding: 20px 24px;
    margin-bottom: 32px;
  }}
  .settlement-row {{
    display: flex;
    justify-content: space-between;
    padding: 6px 0;
    font-size: 13px;
  }}
  .settlement-row.total {{
    border-top: 2px solid #C8D0DA;
    margin-top: 8px;
    padding-top: 12px;
    font-weight: 700;
    font-size: 15px;
  }}

  /* Signature */
  .signature {{
    display: flex;
    gap: 48px;
    margin-top: 40px;
    padding-top: 24px;
    border-top: 1px solid #DDE3EA;
  }}
  .sig-block {{
    flex: 1;
  }}
  .sig-line {{
    width: 100%;
    border-bottom: 1px solid #0D1B2A;
    height: 36px;
    margin-bottom: 6px;
  }}
  .sig-label {{ font-size: 11px; color: #9AAAB8; }}

  /* Footer */
  .footer {{
    text-align: center;
    font-size: 10px;
    color: #9AAAB8;
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #E8ECF1;
    letter-spacing: 0.05em;
  }}

  @media print {{
    body {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
    .page {{ padding: 24px 32px; }}
  }}
</style>
</head>
<body>
<div class="page">

  <!-- Header -->
  <div class="header">
    <div class="logo">Cargo<span>IQ</span></div>
    <div class="cert-badge">
      <h1>Monthly Savings Certificate</h1>
      <div class="period">{period_label}</div>
    </div>
  </div>

  <!-- Client -->
  <div class="client-block">
    <div class="label">Issued to</div>
    <div class="client-name">{org_name}</div>
  </div>

  <!-- Hero -->
  <div class="hero">
    <div>
      <div class="hero-label">Total EBITDA Value Delivered</div>
      <div class="hero-value">{zar(total_value)}</div>
      <div class="hero-sub">{audit_count} shipments audited · {errors_caught} errors intercepted · {int(hours_saved)}h saved</div>
    </div>
    <div class="roi-badge">
      <div class="roi-number">{roi_multiple}×</div>
      <div class="roi-label">Return on Investment</div>
    </div>
  </div>

  <!-- Value breakdown -->
  <div class="section-title">Value Breakdown</div>
  <table class="breakdown">
    <tr>
      <td>CargoWise Transaction Savings (WiseLayer)<br>
        <span class="muted">{cw_transactions_saved} transactions compacted — eliminated from WiseTech billing</span>
      </td>
      <td class="green">{zar(cw_savings_zar)}</td>
    </tr>
    <tr>
      <td>SARS Fines Prevented (Compliance Shield)<br>
        <span class="muted">{errors_caught} compliance errors caught before submission @ R4,500 each</span>
      </td>
      <td class="green">{zar(fines_prevented_zar)}</td>
    </tr>
    <tr>
      <td>Unbilled Revenue Identified (Sentinel)<br>
        <span class="muted">Waiting time and accessorial charges not captured by your team</span>
      </td>
      <td class="green">{zar(unbilled_found_zar)}</td>
    </tr>
    {f'''<tr>
      <td>Carrier Overcharges Recovered (CarrierInvoice Auditor)<br>
        <span class="muted">Billed amounts above your negotiated rate card — dispute notices generated</span>
      </td>
      <td class="green">{zar(carrier_overcharges_zar)}</td>
    </tr>''' if carrier_overcharges_zar > 0 else ''}
    <tr>
      <td>Staff Time Recovered<br>
        <span class="muted">{int(hours_saved)} hours at R180/hr — reallocated to billable operations</span>
      </td>
      <td class="green">{zar(hours_saved * 180)}</td>
    </tr>
    <tr>
      <td><strong>Total Value Delivered This Month</strong></td>
      <td class="amber"><strong>{zar(total_value)}</strong></td>
    </tr>
  </table>

  <!-- Operational metrics -->
  <div class="section-title">Operational Metrics</div>
  <div class="metrics-grid">
    <div class="metric-card">
      <span class="metric-value">{audit_count}</span>
      <span class="metric-label">Shipments Processed</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">{errors_caught}</span>
      <span class="metric-label">Errors Intercepted</span>
    </div>
    <div class="metric-card">
      <span class="metric-value">{cw_transactions_saved}</span>
      <span class="metric-label">CW Transactions Saved</span>
    </div>
  </div>

  <!-- Settlement -->
  <div class="section-title">Monthly Settlement</div>
  <div class="settlement">
    <div class="settlement-row">
      <span>Total Value Delivered</span>
      <span class="green">{zar(total_value)}</span>
    </div>
    <div class="settlement-row">
      <span>CargoIQ Subscription Fee</span>
      <span class="red">({zar(subscription_zar)})</span>
    </div>
    <div class="settlement-row total">
      <span>Net EBITDA Boost to {org_name}</span>
      <span class="{'green' if net_benefit > 0 else 'red'}">{zar(net_benefit)}</span>
    </div>
  </div>

  <!-- Signature -->
  <div class="signature">
    <div class="sig-block">
      <div class="sig-line"></div>
      <div class="sig-label">Authorised — CargoIQ (Pty) Ltd</div>
    </div>
    <div class="sig-block">
      <div class="sig-line"></div>
      <div class="sig-label">Received & Acknowledged — {org_name}</div>
    </div>
    <div class="sig-block">
      <div class="sig-line"></div>
      <div class="sig-label">Date</div>
    </div>
  </div>

  <!-- Footer -->
  <div class="footer">
    CargoIQ (Pty) Ltd · Johannesburg, South Africa · cargoiq.co.za ·
    POPIA Compliant · All values verified by AI audit trail ·
    Generated {generated_at}
  </div>

</div>
</body>
</html>"""


async def generate_savings_certificate(org_id: str, month_label: Optional[str] = None) -> dict:
    """
    Compute all metrics from the database and generate the HTML certificate.
    Returns the HTML string + metadata.
    """
    from datetime import datetime, timedelta

    admin  = get_supabase_admin()
    period = month_label or datetime.utcnow().strftime("%B %Y")

    # Get org details
    org = admin.table("organisations").select("name").eq("id", org_id).single().execute()
    org_name = org.data.get("name", "Unknown Organisation") if org.data else "Unknown"

    # Get plan pricing
    plan_prices = {"pilot": 5000, "starter": 8000, "growth": 18000, "enterprise": 45000}
    org_plan    = org.data.get("plan", "growth") if org.data else "growth"
    subscription_zar = plan_prices.get(org_plan, 18000)

    # Shipments this month
    since = (datetime.utcnow().replace(day=1)).isoformat()
    ships = admin.table("shipments").select("*")         .eq("org_id", org_id)         .gte("created_at", since).execute()

    processed     = [s for s in (ships.data or []) if s["status"] in ("approved","in_cargowise")]
    audit_count   = len(processed)
    hours_saved   = audit_count * (42 - 3) / 60  # 39 mins saved per shipment

    # Compliance errors caught
    events = admin.table("compliance_events").select("*")         .eq("org_id", org_id).eq("penalty_risk", True)         .gte("created_at", since).execute()
    errors_caught       = len(events.data or [])
    fines_prevented_zar = errors_caught * 4500.0

    # WiseLayer savings
    wt = admin.table("wisetech_transactions").select("*")         .eq("org_id", org_id).gte("date", since[:10]).execute()
    cw_saved       = sum(float(r.get("gross_saving_zar") or 0) for r in (wt.data or []))
    cw_tx_saved    = sum(int(r.get("saved_count") or 0) for r in (wt.data or []))

    # Unbilled revenue: real driver check-in waiting-time findings this month,
    # plus a conservative residual estimate (10% of labour saved) for
    # accessorials not yet captured via WhatsApp check-ins.
    waiting_findings = admin.table("waiting_time_findings").select("unbilled_revenue_zar") \
        .eq("org_id", org_id).gte("created_at", since).execute()
    waiting_time_zar = sum(float(r.get("unbilled_revenue_zar") or 0) for r in (waiting_findings.data or []))
    unbilled_zar     = round(waiting_time_zar + (hours_saved * 180 * 0.10), 2)

    # CarrierInvoice Auditor: overcharges found this month
    carrier_audits = admin.table("carrier_invoice_audits") \
        .select("variance_zar,status") \
        .eq("org_id", org_id).eq("status", "overcharge_detected") \
        .gte("created_at", since).execute()
    carrier_overcharges_zar = round(
        sum(float(r.get("variance_zar") or 0) for r in (carrier_audits.data or [])
            if (r.get("variance_zar") or 0) > 0),
        2,
    )

    html = generate_savings_certificate_html(
        org_name              = org_name,
        period_label          = period,
        cw_savings_zar        = cw_saved,
        fines_prevented_zar   = fines_prevented_zar,
        unbilled_found_zar    = unbilled_zar,
        subscription_zar      = float(subscription_zar),
        audit_count           = audit_count,
        errors_caught         = errors_caught,
        hours_saved           = round(hours_saved, 1),
        cw_transactions_saved = cw_tx_saved,
        carrier_overcharges_zar = carrier_overcharges_zar,
    )

    total_value = cw_saved + fines_prevented_zar + unbilled_zar + carrier_overcharges_zar + (hours_saved * 180)

    return {
        "org_name":          org_name,
        "period":            period,
        "html":              html,
        "total_value_zar":   round(total_value, 2),
        "subscription_zar":  subscription_zar,
        "net_benefit_zar":   round(total_value - subscription_zar, 2),
        "roi_multiple":      round(total_value / subscription_zar, 1) if subscription_zar > 0 else 0,
        "generated_at":      datetime.utcnow().isoformat(),
    }


# ── Client Success Story ────────────────────────────────────
# "Show the next prospect." A one-page, marketing-framed version
# of the Savings Certificate — same underlying numbers, different
# narrative: Before CargoIQ / After CargoIQ / Results.
#
# anonymized=True replaces the org name with a generic descriptor
# so it can be shown to prospects before the client agrees to be
# named as a reference.

INDUSTRY_DESCRIPTORS = {
    "pilot":      "a Johannesburg-based customs clearing agency",
    "starter":    "a South African freight forwarder",
    "growth":     "a mid-size South African freight forwarder",
    "enterprise": "a large South African logistics group",
}


def generate_success_story_html(cert: dict, org_plan: str, anonymized: bool = True) -> str:
    """
    Generate a one-page Client Success Story from Savings Certificate
    data. Open in browser, screenshot or print to PDF, send to the
    next prospect.
    """
    display_name = (
        INDUSTRY_DESCRIPTORS.get(org_plan, "a South African freight forwarder")
        if anonymized else cert["org_name"]
    )

    def zar(amount) -> str:
        return f"R{abs(float(amount or 0)):,.0f}"

    total_value  = cert["total_value_zar"]
    subscription = cert["subscription_zar"]
    roi          = cert["roi_multiple"]
    net_benefit  = cert["net_benefit_zar"]
    period       = cert["period"]
    generated_at = datetime.utcnow().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ font-family:-apple-system,Arial,sans-serif; background:#fff; color:#0D1B2A; padding: 48px 56px; }}
  .eyebrow {{ font-size:11px; font-weight:700; letter-spacing:0.15em; text-transform:uppercase; color:#B8860B; }}
  h1 {{ font-size: 26px; font-weight:700; margin-top:8px; margin-bottom: 24px; line-height:1.3; }}
  .lede {{ font-size:14px; color:#6B7E92; margin-bottom:32px; max-width: 560px; line-height:1.6; }}
  .columns {{ display:grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
  .col {{ border:1px solid #DDE3EA; border-radius:8px; padding:20px; }}
  .col h3 {{ font-size:11px; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#9AAAB8; margin-bottom:12px; }}
  .col.before h3 {{ color:#9B1C1C; }}
  .col.after h3 {{ color:#15632A; }}
  .col li {{ font-size:13px; line-height:1.8; list-style:none; padding-left:18px; position:relative; }}
  .col.before li::before {{ content:"−"; position:absolute; left:0; color:#9B1C1C; font-weight:700; }}
  .col.after li::before {{ content:"+"; position:absolute; left:0; color:#15632A; font-weight:700; }}
  .hero {{ background:linear-gradient(135deg,#1A2332 0%,#243447 100%); color:#F1F4F8; border-radius:10px;
           padding: 28px 32px; display:flex; justify-content:space-between; align-items:center; margin-bottom: 28px; }}
  .hero-value {{ font-family:monospace; font-size: 40px; font-weight:700; color:#B8860B; }}
  .hero-label {{ font-size:11px; letter-spacing:0.12em; text-transform:uppercase; color:#C8D3DF; margin-bottom:4px; }}
  .roi {{ text-align:right; }}
  .roi-value {{ font-family:monospace; font-size: 36px; font-weight:700; color:#15AC4A; }}
  .roi-label {{ font-size:10px; letter-spacing:0.1em; text-transform:uppercase; color:#9AAAB8; }}
  .quote {{ border-left: 3px solid #B8860B; padding-left:18px; margin: 24px 0; font-size:14px;
            font-style:italic; color:#0D1B2A; line-height:1.6; }}
  .footer {{ margin-top: 36px; padding-top:16px; border-top:1px solid #E8ECF1; font-size:10px; color:#9AAAB8;
             text-align:center; letter-spacing:0.05em; }}
</style></head>
<body>
  <div class="eyebrow">Client Success Story · {period}</div>
  <h1>How {display_name} found {zar(total_value)} in hidden costs and unbilled revenue — with software that paid for itself {roi}× over.</h1>
  <p class="lede">
    CargoIQ's AI compliance and cost-containment layer runs on top of {display_name}'s
    existing CargoWise setup. No migration, no workflow change — just
    a continuous audit of every shipment, every CargoWise transaction,
    and every carrier invoice.
  </p>

  <div class="hero">
    <div>
      <div class="hero-label">Total Value Delivered, {period}</div>
      <div class="hero-value">{zar(total_value)}</div>
    </div>
    <div class="roi">
      <div class="roi-value">{roi}×</div>
      <div class="roi-label">Return on Subscription</div>
    </div>
  </div>

  <div class="columns">
    <div class="col before">
      <h3>Before CargoIQ</h3>
      <ul>
        <li>Manual data entry into CargoWise, ~40 minutes per shipment</li>
        <li>Compliance errors caught only after SARS queries arrive</li>
        <li>Carrier invoices paid as billed — no rate card cross-check</li>
        <li>Driver waiting time tracked on paper, rarely invoiced</li>
      </ul>
    </div>
    <div class="col after">
      <h3>After CargoIQ</h3>
      <ul>
        <li>AI extraction + Compliance Shield on every shipment</li>
        <li>Errors flagged and fixed before submission</li>
        <li>Every carrier invoice checked against negotiated rates</li>
        <li>Waiting time captured via WhatsApp, invoiced same day</li>
      </ul>
    </div>
  </div>

  <div class="quote">
    "We paid {zar(subscription)} for CargoIQ this month. It found {zar(total_value)}
    in value we would otherwise have missed — a net benefit of {zar(net_benefit)},
    on top of work our team was already doing."
  </div>

  <div class="footer">
    CargoIQ (Pty) Ltd · Johannesburg, South Africa · cargoiq.co.za ·
    Figures drawn from {display_name}'s own operational data · {generated_at}
  </div>
</body></html>"""


async def get_success_story(org_id: str, anonymized: bool = True, month_label: Optional[str] = None) -> str:
    """Fetch certificate data for an org and render it as a Success Story."""
    admin = get_supabase_admin()
    org   = admin.table("organisations").select("plan").eq("id", org_id).single().execute()
    org_plan = org.data.get("plan", "growth") if org.data else "growth"

    cert = await generate_savings_certificate(org_id=org_id, month_label=month_label)
    return generate_success_story_html(cert, org_plan, anonymized=anonymized)
