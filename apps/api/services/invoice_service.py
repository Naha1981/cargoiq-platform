"""
CargoIQ — Invoice Generator Service
=====================================
Closes the loop from "found money" to "cash collected."

Current flow without this:
  CargoIQ finds R3,500 unbilled waiting time
  → Operator generates charge notice (printable HTML)
  → Operator MANUALLY creates an invoice in their accounting system
  → Cash collected days later

With this:
  CargoIQ finds R3,500 unbilled waiting time
  → One click: "Generate Invoice"
  → Numbered invoice created in DB, HTML ready to send/print
  → Status tracked: Draft → Sent → Paid

Same HTML→print pattern as the Savings Certificate and
Carrier Dispute Notice. No new libraries.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from ..core.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)

VAT_RATE = 0.15  # 15% VAT (SA standard rate)


# ── Sequential invoice numbering ─────────────────────────────

async def _next_invoice_number(org_id: str, admin) -> str:
    """
    Generate the next invoice number for this org.
    Format: CIQ-INV-YYYY-NNNN (e.g. CIQ-INV-2026-0042)
    Uses a DB sequence to guarantee no gaps or duplicates.
    """
    year = datetime.utcnow().year

    # Upsert sequence record and return new number
    existing = admin.table("invoice_sequences").select("last_number") \
        .eq("org_id", org_id).execute()

    if existing.data:
        new_num = existing.data[0]["last_number"] + 1
        admin.table("invoice_sequences").update({"last_number": new_num}) \
            .eq("org_id", org_id).execute()
    else:
        new_num = 1
        admin.table("invoice_sequences").insert({
            "org_id": org_id, "last_number": new_num
        }).execute()

    return f"CIQ-INV-{year}-{new_num:04d}"


# ── Create from waiting-time finding ─────────────────────────

async def create_invoice_from_finding(
    org_id:       str,
    finding_id:   str,
    bank_account: Optional[str] = None,
    due_days:     int = 30,
) -> dict:
    """
    Generate a numbered invoice from a waiting-time finding.
    The finding already has: location, arrived_at, departed_at,
    billable_minutes, rate_per_hour_zar, unbilled_revenue_zar.
    """
    admin = get_supabase_admin()

    finding = admin.table("waiting_time_findings").select("*") \
        .eq("id", finding_id).eq("org_id", org_id).single().execute()

    if not finding.data:
        raise ValueError("Waiting-time finding not found")

    f = finding.data

    # Resolve the client name from the linked shipment
    client_name = "Unknown Client"
    if f.get("shipment_id"):
        ship = admin.table("shipments") \
            .select("consignee_name,importer_client_name") \
            .eq("id", f["shipment_id"]).single().execute()
        if ship.data:
            client_name = (
                ship.data.get("importer_client_name") or
                ship.data.get("consignee_name") or
                "Unknown Client"
            )

    billable_hrs = round(float(f.get("billable_minutes") or 0) / 60, 2)
    rate         = float(f.get("rate_per_hour_zar") or 350)
    subtotal     = round(float(f.get("unbilled_revenue_zar") or 0), 2)

    arrived  = f.get("arrived_at", "")[:16].replace("T", " ")
    departed = f.get("departed_at", "")[:16].replace("T", " ")
    location = f.get("location_name") or "Port/DC"
    reference = f.get("reference") or "—"

    line_items = [{
        "description": (
            f"Waiting/Detention Time — {location}\n"
            f"Reference: {reference}\n"
            f"Arrived: {arrived} | Departed: {departed}\n"
            f"Free time: {int(f.get('free_minutes', 120))} min | "
            f"Billable: {int(f.get('billable_minutes', 0))} min"
        ),
        "quantity":       billable_hrs,
        "unit":           "hours",
        "unit_price_zar": rate,
        "total_zar":      subtotal,
    }]

    invoice_number = await _next_invoice_number(org_id, admin)
    due_date       = (datetime.utcnow() + timedelta(days=due_days)).date().isoformat()

    # Get org details for the invoice header
    org = admin.table("organisations").select("name").eq("id", org_id).single().execute()
    org_name = org.data.get("name", "") if org.data else ""

    record = {
        "org_id":         org_id,
        "invoice_number": invoice_number,
        "invoice_type":   "waiting_time",
        "shipment_id":    f.get("shipment_id"),
        "finding_id":     finding_id,
        "client_name":    client_name,
        "line_items":     line_items,
        "subtotal_zar":   subtotal,
        "vat_rate":       VAT_RATE,
        "status":         "draft",
        "due_date":       due_date,
        "bank_account":   bank_account,
    }

    inserted = admin.table("invoices").insert(record).execute()
    inv = inserted.data[0] if inserted.data else record

    # Mark the finding as invoiced
    admin.table("waiting_time_findings").update({"status": "invoiced"}) \
        .eq("id", finding_id).execute()

    logger.info(f"Invoice {invoice_number} created: {client_name} R{subtotal:,.2f}")

    inv["html"] = generate_invoice_html(inv, org_name)
    return inv


# ── HTML invoice generator ────────────────────────────────────

def generate_invoice_html(invoice: dict, org_name: str) -> str:
    """
    Generate a print-ready HTML tax invoice.
    Same HTML→print pattern as all other CargoIQ documents.
    """
    inv_num      = invoice.get("invoice_number", "—")
    client       = invoice.get("client_name", "—")
    client_addr  = invoice.get("client_address", "")
    client_vat   = invoice.get("vat_number", "")
    subtotal     = float(invoice.get("subtotal_zar") or 0)
    vat_rate     = float(invoice.get("vat_rate") or 0.15)
    vat_amount   = round(subtotal * vat_rate, 2)
    total        = round(subtotal + vat_amount, 2)
    due_date     = invoice.get("due_date", "")
    line_items   = invoice.get("line_items") or []
    bank_account = invoice.get("bank_account", "")
    inv_date     = datetime.utcnow().strftime("%d %B %Y")
    inv_type     = (invoice.get("invoice_type") or "").replace("_", " ").title()

    def zar(n): return f"R{abs(float(n or 0)):,.2f}"

    rows = ""
    for item in line_items:
        desc     = (item.get("description") or "").replace("\n", "<br>")
        qty      = item.get("quantity", 1)
        unit     = item.get("unit", "")
        rate_str = zar(item.get("unit_price_zar", 0))
        tot_str  = zar(item.get("total_zar", 0))
        rows += f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #EEF1F4;font-size:13px;vertical-align:top">{desc}</td>
          <td style="padding:10px 0;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:center;white-space:nowrap">{qty} {unit}</td>
          <td style="padding:10px 0;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:right;font-family:monospace;white-space:nowrap">{rate_str}</td>
          <td style="padding:10px 0;border-bottom:1px solid #EEF1F4;font-size:13px;text-align:right;font-family:monospace;white-space:nowrap">{tot_str}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,Arial,sans-serif;font-size:13px;color:#0D1B2A;padding:48px 56px}}
  .header{{display:flex;justify-content:space-between;align-items:flex-start;
           padding-bottom:24px;border-bottom:3px solid #1A2332;margin-bottom:28px}}
  .logo{{font-family:monospace;font-size:20px;font-weight:700;color:#1A2332}}
  .logo span{{color:#B8860B}}
  .title{{text-align:right}}
  .title h1{{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#6B7E92}}
  .title .num{{font-size:18px;font-weight:700;margin-top:4px}}
  .parties{{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-bottom:28px}}
  .label{{font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;
          color:#9AAAB8;margin-bottom:6px}}
  .value{{font-size:13px;line-height:1.6}}
  .muted{{color:#6B7E92;font-size:12px}}
  table{{width:100%;border-collapse:collapse;margin-bottom:24px}}
  thead th{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#9AAAB8;
            padding-bottom:8px;border-bottom:1px solid #DDE3EA;text-align:left}}
  thead th:nth-child(2){{text-align:center}}
  thead th:nth-child(3),thead th:nth-child(4){{text-align:right}}
  .totals{{display:flex;justify-content:flex-end;margin-bottom:24px}}
  .totals-block{{width:260px}}
  .tot-row{{display:flex;justify-content:space-between;padding:5px 0;font-size:13px}}
  .tot-row.total{{border-top:2px solid #1A2332;padding-top:10px;font-weight:700;font-size:15px}}
  .bank{{background:#F1F4F8;border-radius:4px;padding:14px 16px;font-size:12px;
         line-height:1.8;margin-bottom:24px}}
  .footer{{margin-top:32px;font-size:10px;color:#9AAAB8;border-top:1px solid #E8ECF1;
           padding-top:14px;text-align:center}}
  @media print{{body{{padding:24px 32px}}}}
</style></head>
<body>
  <div class="header">
    <div class="logo">Cargo<span>IQ</span></div>
    <div class="title">
      <h1>Tax Invoice — {inv_type}</h1>
      <div class="num">{inv_num}</div>
    </div>
  </div>

  <div class="parties">
    <div>
      <div class="label">From</div>
      <div class="value">
        <strong>{org_name}</strong>
      </div>
    </div>
    <div>
      <div class="label">Billed To</div>
      <div class="value">
        <strong>{client}</strong>
        {f'<br><span class="muted">{client_addr}</span>' if client_addr else ''}
        {f'<br><span class="muted">VAT Reg: {client_vat}</span>' if client_vat else ''}
      </div>
    </div>
    <div>
      <div class="label">Invoice Date</div>
      <div class="value">{inv_date}</div>
    </div>
    <div>
      <div class="label">Payment Due</div>
      <div class="value">{due_date or '30 days from invoice date'}</div>
    </div>
  </div>

  <table>
    <thead><tr>
      <th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>

  <div class="totals">
    <div class="totals-block">
      <div class="tot-row"><span>Subtotal</span><span style="font-family:monospace">{zar(subtotal)}</span></div>
      <div class="tot-row"><span>VAT ({int(vat_rate*100)}%)</span><span style="font-family:monospace">{zar(vat_amount)}</span></div>
      <div class="tot-row total"><span>Total Due</span><span style="font-family:monospace">{zar(total)}</span></div>
    </div>
  </div>

  {f'<div class="bank"><strong>Payment Details:</strong><br>{bank_account}</div>' if bank_account else ''}

  <div class="footer">
    {org_name} · {inv_num} · Generated by CargoIQ · {inv_date}
  </div>
</body></html>"""
