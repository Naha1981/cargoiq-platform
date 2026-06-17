"""
CargoIQ — CarrierInvoice Auditor ("Overcharge Hunter")
========================================================
Ingests a carrier invoice (PDF), extracts line items via Claude
(reusing the same document_service + Instructor pattern as
shipment extraction), and compares each line item against the
org's negotiated rate cards. Flags overcharges and generates a
printable Dispute Notice — same HTML→print pattern as the
Savings Certificate, so no new PDF library is required.

This is the "other side of the P&L" companion to WiseLayer:
WiseLayer stops CargoWise fee leakage. CarrierInvoice Auditor
stops carrier overbilling.
"""
import logging
from datetime import datetime
from typing import Optional, List
import anthropic
import instructor
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.supabase_client import get_supabase_admin
from .document_service import extract_text_from_pdf

logger = logging.getLogger(__name__)


# ── Extraction schema ───────────────────────────────────────

class CarrierInvoiceLineItem(BaseModel):
    """One billed line item on a carrier invoice."""
    description: str = Field(description="Charge description as printed, e.g. 'Ocean Freight 1x40HC', 'BAF Surcharge', 'THC Durban'")
    charge_type: str = Field(description="Normalised category: ocean_freight | air_freight | baf | caf | thc | documentation | demurrage | detention | other")
    billed_amount: float = Field(description="Amount billed for this line item")
    quantity: Optional[float] = Field(default=1, description="Quantity / units billed, e.g. number of containers")
    unit: Optional[str] = Field(default="per_shipment", description="per_container | per_kg | per_cbm | per_shipment | flat")


class CarrierInvoiceExtraction(BaseModel):
    """Structured extraction of a carrier (freight) invoice."""
    carrier_name:   str = Field(description="The carrier or shipping line issuing this invoice, e.g. 'Maersk', 'MSC', 'Bidvest'")
    invoice_number: Optional[str] = Field(default=None, description="Invoice / reference number")
    invoice_date:   Optional[str] = Field(default=None, description="Invoice date in YYYY-MM-DD if present")
    currency:       str = Field(default="USD", description="ISO currency code of the invoice")
    total_amount:   float = Field(description="Grand total of the invoice")
    line_items:     List[CarrierInvoiceLineItem] = Field(default_factory=list)
    lane:           Optional[str] = Field(default=None, description="Origin-destination lane if identifiable, e.g. 'CNSHA-ZADUR'")
    container_or_awb: Optional[str] = Field(default=None, description="Container number or AWB referenced on the invoice")


def get_instructor_client():
    anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return instructor.from_anthropic(anthropic_client)


async def extract_carrier_invoice(raw_text: str) -> CarrierInvoiceExtraction:
    """Run Claude extraction on carrier invoice text."""
    client = get_instructor_client()

    extraction = client.chat.completions.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        response_model=CarrierInvoiceExtraction,
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract every billed line item from this carrier/freight invoice. "
                    "Identify the carrier name, invoice number, currency, and total. "
                    "For each line item, classify charge_type into one of: "
                    "ocean_freight, air_freight, baf, caf, thc, documentation, "
                    "demurrage, detention, other. "
                    "Only extract what is explicitly stated — never fabricate amounts.\n\n"
                    f"=== INVOICE TEXT ===\n{raw_text[:15000]}"
                ),
            }
        ],
    )
    return extraction


# ── Rate card matching ──────────────────────────────────────

def _find_matching_rate(
    rate_cards: List[dict], charge_type: str, lane: Optional[str]
) -> Optional[dict]:
    """
    Find the best matching rate card for a line item.
    Priority: exact charge_type + lane match > charge_type only (lane=NULL).
    """
    # 1. Exact charge_type + lane match
    if lane:
        for rc in rate_cards:
            if rc["charge_type"] == charge_type and rc.get("lane") == lane:
                return rc

    # 2. charge_type match with no lane restriction (applies to all lanes)
    for rc in rate_cards:
        if rc["charge_type"] == charge_type and not rc.get("lane"):
            return rc

    return None


async def audit_carrier_invoice(
    org_id: str,
    extraction: CarrierInvoiceExtraction,
    shipment_id: Optional[str] = None,
    document_id: Optional[str] = None,
    fx_rate_to_zar: float = 19.20,
) -> dict:
    """
    Compare extracted line items against the org's rate cards.
    Returns the audit result and persists it to carrier_invoice_audits.
    """
    admin = get_supabase_admin()

    # Fetch all active rate cards for this carrier
    today = datetime.utcnow().date().isoformat()
    rc_result = admin.table("carrier_rate_cards") \
        .select("*") \
        .eq("org_id", org_id) \
        .ilike("carrier_name", extraction.carrier_name) \
        .lte("valid_from", today) \
        .execute()

    rate_cards = [
        rc for rc in (rc_result.data or [])
        if not rc.get("valid_to") or rc["valid_to"] >= today
    ]

    line_results = []
    agreed_total  = 0.0
    has_rate_card = len(rate_cards) > 0

    for item in extraction.line_items:
        match = _find_matching_rate(rate_cards, item.charge_type, extraction.lane)

        if match:
            qty = item.quantity or 1
            agreed_amount = float(match["agreed_rate"]) * qty
            variance = round(item.billed_amount - agreed_amount, 2)
            agreed_total += agreed_amount

            line_results.append({
                "description":     item.description,
                "charge_type":     item.charge_type,
                "billed":          item.billed_amount,
                "agreed":          round(agreed_amount, 2),
                "variance":        variance,
                "matched_rate_card_id": match["id"],
                "is_overcharge":   variance > 0.01,
            })
        else:
            # No rate card for this charge type — can't audit, but still record
            agreed_total += item.billed_amount  # assume billed = agreed (no data to dispute)
            line_results.append({
                "description":   item.description,
                "charge_type":   item.charge_type,
                "billed":        item.billed_amount,
                "agreed":        None,
                "variance":      None,
                "matched_rate_card_id": None,
                "is_overcharge": False,
            })

    overcharges = [l for l in line_results if l["is_overcharge"]]
    total_variance = round(extraction.total_amount - agreed_total, 2)

    if not has_rate_card:
        status = "no_rate_card"
    elif overcharges:
        status = "overcharge_detected"
    else:
        status = "clean"

    # Convert variance to ZAR for the dashboard / Savings Certificate roll-up
    variance_zar = round(total_variance * fx_rate_to_zar, 2) if extraction.currency == "USD" else (
        round(total_variance, 2) if extraction.currency == "ZAR" else round(total_variance * fx_rate_to_zar, 2)
    )

    record = {
        "org_id":           org_id,
        "shipment_id":      shipment_id,
        "document_id":      document_id,
        "carrier_name":     extraction.carrier_name,
        "invoice_number":   extraction.invoice_number,
        "invoice_currency": extraction.currency,
        "invoice_total":    extraction.total_amount,
        "agreed_total":     round(agreed_total, 2) if has_rate_card else None,
        "variance_zar":     variance_zar if has_rate_card and overcharges else 0,
        "line_items":       line_results,
        "status":           status,
    }

    inserted = admin.table("carrier_invoice_audits").insert(record).execute()
    audit_id = inserted.data[0]["id"] if inserted.data else None

    logger.info(
        f"Carrier audit complete: carrier={extraction.carrier_name} "
        f"status={status} overcharges={len(overcharges)} "
        f"variance_zar={variance_zar if has_rate_card else 'n/a'}"
    )

    return {
        "audit_id":        audit_id,
        "carrier_name":    extraction.carrier_name,
        "invoice_number":  extraction.invoice_number,
        "currency":        extraction.currency,
        "invoice_total":   extraction.total_amount,
        "agreed_total":    round(agreed_total, 2) if has_rate_card else None,
        "total_variance":  total_variance if has_rate_card else None,
        "variance_zar":    variance_zar if has_rate_card else None,
        "status":          status,
        "has_rate_card":   has_rate_card,
        "overcharge_count": len(overcharges),
        "line_items":      line_results,
    }


async def process_carrier_invoice_upload(
    org_id: str,
    file_content: bytes,
    filename: str,
    shipment_id: Optional[str] = None,
) -> dict:
    """
    Full pipeline: PDF → text → Claude extraction → rate card audit.
    Called by the upload endpoint.
    """
    raw_text, ocr_method, page_count = extract_text_from_pdf(file_content, filename)

    if not raw_text or not raw_text.strip():
        return {
            "status": "error",
            "error":  "Could not extract text from this PDF. Try a different scan/export.",
        }

    extraction = await extract_carrier_invoice(raw_text)
    result = await audit_carrier_invoice(
        org_id=org_id,
        extraction=extraction,
        shipment_id=shipment_id,
    )
    return result


# ── Dispute Notice (HTML → print, same pattern as Savings Certificate) ──

def generate_dispute_notice_html(audit: dict, org_name: str) -> str:
    """
    Generate a printable Short-Payment / Dispute Notice for the
    overcharges found on a carrier invoice. Open in browser, print
    to PDF, attach to the carrier email.
    """
    overcharges = [l for l in audit["line_items"] if l.get("is_overcharge")]
    total_dispute = sum(l["variance"] for l in overcharges)

    def money(amount, currency):
        return f"{currency} {amount:,.2f}"

    rows = ""
    for l in overcharges:
        rows += f"""
        <tr>
          <td>{l['description']}</td>
          <td style="text-align:right">{money(l['agreed'], audit['currency'])}</td>
          <td style="text-align:right">{money(l['billed'], audit['currency'])}</td>
          <td style="text-align:right; color:#9B1C1C; font-weight:600">
            {money(l['variance'], audit['currency'])}
          </td>
        </tr>"""

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
  .meta strong {{ color:#6B7E92; font-weight:600; display:inline-block; width:160px; }}
  table {{ width:100%; border-collapse:collapse; margin-bottom: 24px; }}
  th {{ text-align:left; font-size:10px; text-transform:uppercase; letter-spacing:0.08em;
        color:#6B7E92; padding-bottom:8px; border-bottom:1px solid #DDE3EA; }}
  th:nth-child(2), th:nth-child(3), th:nth-child(4) {{ text-align:right; }}
  td {{ padding: 8px 0; border-bottom:1px solid #EEF1F4; font-size:13px; }}
  .total-row td {{ border-top:2px solid #1A2332; border-bottom:none; font-weight:700; padding-top:12px; }}
  .notice {{ background:#FEF2F2; border:1px solid #F5A5A5; color:#9B1C1C; border-radius:4px;
             padding:14px 16px; font-size:13px; line-height:1.7; margin-bottom:24px; }}
  .footer {{ margin-top: 40px; font-size:11px; color:#9AAAB8; border-top:1px solid #E8ECF1; padding-top:14px; }}
</style></head>
<body>
  <div class="header">
    <div class="logo">Cargo<span>IQ</span></div>
    <div class="title">
      <h1>Rate Dispute Notice</h1>
      <div class="ref">{audit.get('invoice_number') or 'No Reference'}</div>
    </div>
  </div>

  <div class="meta">
    <div><strong>Issued by</strong> {org_name}</div>
    <div><strong>Carrier</strong> {audit['carrier_name']}</div>
    <div><strong>Invoice Total</strong> {money(audit['invoice_total'], audit['currency'])}</div>
    <div><strong>Date</strong> {generated_at}</div>
  </div>

  <div class="notice">
    <strong>This invoice contains {len(overcharges)} line item{'s' if len(overcharges) != 1 else ''}
    billed above our negotiated rate card.</strong> Per our agreement, we are
    short-paying this invoice by {money(total_dispute, audit['currency'])}.
    Please issue a corrected invoice or credit note for the amount below.
  </div>

  <table>
    <thead><tr><th>Line Item</th><th>Agreed Rate</th><th>Billed</th><th>Variance</th></tr></thead>
    <tbody>
      {rows}
      <tr class="total-row">
        <td>Total Disputed Amount</td><td></td><td></td>
        <td style="text-align:right; color:#9B1C1C">{money(total_dispute, audit['currency'])}</td>
      </tr>
    </tbody>
  </table>

  <div class="footer">
    Generated by CargoIQ CarrierInvoice Auditor · {org_name} ·
    All variances calculated against rate cards on file · {generated_at}
  </div>
</body></html>"""


# ── FSC (Fuel Surcharge Clause) Auditor ─────────────────────
# Detects when a carrier hasn't reduced their FSC after diesel
# price drops. Uses diesel_price_history table + rate card FSC
# formula to calculate the correct FSC and flag overcharges.
#
# Story 2 from the Daily Risk Briefing: "Diesel fell R3.25/litre
# on 3 June. Your carriers raised FSC fast in April. Are they
# cutting it now? On R1.5M/month freight = R90k–R120k overcharged."

def calculate_correct_fsc_percent(
    diesel_base_rate_zar: float,
    fsc_percent_per_50c:  float,
    current_diesel_zar:   float,
) -> float:
    """
    Calculate the correct FSC percentage for a given diesel price.

    Standard SA FSC clause: 1% per R0.50/litre above the base rate.
    Example: base=R22.00, rate=1%/R0.50, diesel=R26.11
      → surplus = R4.11, steps = floor(4.11/0.50) = 8, FSC = 8%

    When diesel fell to R22.86/litre in June 2026:
      → surplus = R0.86, steps = floor(0.86/0.50) = 1, FSC = 1%
      → Correct FSC dropped from 8% to 1% — a 7% reduction
    """
    surplus = max(0.0, current_diesel_zar - diesel_base_rate_zar)
    steps   = int(surplus / 0.50)
    return round(steps * fsc_percent_per_50c, 3)


async def audit_fsc_overcharge(
    org_id:              str,
    carrier_name:        str,
    invoice_freight_zar: float,
    billed_fsc_percent:  float,
    invoice_date:        str,     # YYYY-MM-DD
    region:              str = "gauteng",
) -> dict:
    """
    Check whether the FSC billed on an invoice matches the correct
    rate for the diesel price on the invoice date.

    Returns:
        correct_fsc_percent, billed_fsc_percent, overcharge_zar,
        diesel_price_on_date, is_overcharged
    """
    admin = get_supabase_admin()

    # Fetch the rate card for this carrier with FSC fields
    rc = admin.table("carrier_rate_cards") \
        .select("diesel_base_rate_zar,fsc_percent_per_50c") \
        .eq("org_id", org_id) \
        .ilike("carrier_name", carrier_name) \
        .eq("charge_type", "baf") \
        .limit(1).execute()

    if not rc.data or not rc.data[0].get("diesel_base_rate_zar"):
        return {
            "status":  "no_fsc_rate_card",
            "message": f"No FSC formula configured for {carrier_name}. Add diesel_base_rate_zar and fsc_percent_per_50c to the rate card.",
        }

    base_rate  = float(rc.data[0]["diesel_base_rate_zar"])
    fsc_rate   = float(rc.data[0]["fsc_percent_per_50c"])

    # Find the diesel price on or before the invoice date
    diesel_rec = admin.table("diesel_price_history") \
        .select("price_zar,effective_date") \
        .eq("region", region) \
        .lte("effective_date", invoice_date) \
        .order("effective_date", desc=True) \
        .limit(1).execute()

    if not diesel_rec.data:
        return {
            "status":  "no_diesel_price",
            "message": f"No diesel price on record for {invoice_date}. Add to diesel_price_history table.",
        }

    diesel_price = float(diesel_rec.data[0]["price_zar"])
    diesel_date  = diesel_rec.data[0]["effective_date"]

    correct_fsc  = calculate_correct_fsc_percent(base_rate, fsc_rate, diesel_price)
    correct_amount = round(invoice_freight_zar * correct_fsc / 100, 2)
    billed_amount  = round(invoice_freight_zar * billed_fsc_percent / 100, 2)
    overcharge     = round(billed_amount - correct_amount, 2)

    return {
        "status":                "overcharge_detected" if overcharge > 0 else "clean",
        "carrier":               carrier_name,
        "invoice_date":          invoice_date,
        "diesel_price_on_date":  diesel_price,
        "diesel_price_date":     diesel_date,
        "diesel_base_rate":      base_rate,
        "correct_fsc_percent":   correct_fsc,
        "billed_fsc_percent":    billed_fsc_percent,
        "invoice_freight_zar":   invoice_freight_zar,
        "correct_fsc_amount_zar": correct_amount,
        "billed_fsc_amount_zar":  billed_amount,
        "overcharge_zar":         max(0.0, overcharge),
        "is_overcharged":         overcharge > 0,
        "note": (
            f"Diesel was R{diesel_price}/litre on {diesel_date}. "
            f"Correct FSC = {correct_fsc}%. Carrier billed {billed_fsc_percent}%. "
            f"Overcharge = R{max(0.0, overcharge):,.2f}."
        ) if overcharge > 0 else "FSC correctly applied.",
    }
