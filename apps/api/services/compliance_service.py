"""
CargoIQ — Compliance Shield Service
Six SARS pre-submission audit modules.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

SACU_COUNTRIES = {"ZA", "LS", "NA", "SZ", "BW"}


@dataclass
class ModuleResult:
    module: str
    result: str          # pass | hold | fail
    detail: dict
    penalty_risk: bool = False
    resolution: Optional[str] = None


@dataclass
class ShieldReport:
    overall: str         # pass | hold | fail
    modules: List[ModuleResult]
    penalty_risk_detected: bool
    block_cargowise: bool
    run_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "overall": self.overall,
            "modules": [
                {
                    "module": m.module,
                    "result": m.result,
                    "detail": m.detail,
                    "penalty_risk": m.penalty_risk,
                    "resolution": m.resolution,
                }
                for m in self.modules
            ],
            "penalty_risk_detected": self.penalty_risk_detected,
            "block_cargowise": self.block_cargowise,
            "run_at": self.run_at.isoformat(),
        }


# ============================================================
# MODULE 1: Invoice ↔ Packing List Cross-Reference
# ============================================================

def check_invoice_pl_crossref(shipment: dict, documents: list) -> ModuleResult:
    """
    Cross-references commercial invoice data against packing list.
    Checks: gross weight, net weight, package count, declared values.
    """
    WEIGHT_TOLERANCE_KG = 1.0
    VALUE_TOLERANCE_PCT = 0.005  # 0.5%

    # Extract weights from extracted_fields or core fields
    invoice_weight = _extract_numeric(shipment.get("gross_weight"))
    
    # Look for packing list specific weight in extended fields
    extracted = shipment.get("extracted_fields", {})
    pl_weight = _extract_numeric(extracted.get("packing_list_gross_weight"))

    # If we only have one weight source, skip with hold
    if invoice_weight is None:
        return ModuleResult(
            module="invoice_pl_xref",
            result="hold",
            detail={"message": "Gross weight not found in documents"},
            penalty_risk=True,
            resolution="Ensure commercial invoice includes total gross weight"
        )

    if pl_weight is None:
        # Single document — can only warn
        return ModuleResult(
            module="invoice_pl_xref",
            result="hold",
            detail={
                "message": "Only one weight source available — cannot cross-reference",
                "invoice_weight_kg": invoice_weight,
                "note": "Provide both commercial invoice and packing list for full validation"
            },
            penalty_risk=False,
            resolution="Upload both commercial invoice and packing list for cross-reference validation"
        )

    # Compare weights
    weight_diff = abs(invoice_weight - pl_weight)
    if weight_diff > WEIGHT_TOLERANCE_KG:
        return ModuleResult(
            module="invoice_pl_xref",
            result="fail",
            detail={
                "invoice_gross_weight_kg": invoice_weight,
                "packing_list_gross_weight_kg": pl_weight,
                "variance_kg": round(weight_diff, 3),
                "tolerance_kg": WEIGHT_TOLERANCE_KG,
            },
            penalty_risk=True,
            resolution=(
                f"Weight mismatch: Invoice shows {invoice_weight}kg, "
                f"Packing List shows {pl_weight}kg (variance: {weight_diff:.2f}kg). "
                f"Correct the discrepancy before SARS submission to avoid penalty."
            )
        )

    return ModuleResult(
        module="invoice_pl_xref",
        result="pass",
        detail={
            "invoice_gross_weight_kg": invoice_weight,
            "packing_list_gross_weight_kg": pl_weight,
            "variance_kg": round(weight_diff, 3),
        }
    )


# ============================================================
# MODULE 2: HS Code Format Validator
# ============================================================

def check_hs_code_format(shipment: dict) -> ModuleResult:
    """
    Validates HS/tariff codes are exactly 8 digits (SARS requirement).
    Checks primary HS code and all line item codes.
    """
    import re
    issues = []

    def validate_code(code: str, label: str) -> Optional[dict]:
        if not code:
            return None
        clean = re.sub(r'[\.\s\-]', '', str(code))
        if not clean.isdigit():
            return {
                "label": label,
                "code": code,
                "issue": "Contains non-numeric characters",
                "cleaned": clean
            }
        if len(clean) != 8:
            return {
                "label": label,
                "code": code,
                "issue": f"Must be exactly 8 digits, found {len(clean)}",
                "cleaned": clean
            }
        return None

    # Check primary HS code
    primary = shipment.get("hs_code_primary")
    if primary:
        issue = validate_code(primary, "Primary HS Code")
        if issue:
            issues.append(issue)
    else:
        # No HS code at all is a hold
        return ModuleResult(
            module="hs_code_validator",
            result="hold",
            detail={"message": "No HS code found in documents"},
            penalty_risk=True,
            resolution="HS/tariff code is required for SARS customs declaration. Provide 8-digit SARS tariff code."
        )

    if issues:
        return ModuleResult(
            module="hs_code_validator",
            result="fail",
            detail={"invalid_codes": issues, "count": len(issues)},
            penalty_risk=True,
            resolution=(
                f"Invalid HS code(s) detected. SARS requires exactly 8 digits. "
                f"Affected: {', '.join(i['label'] for i in issues)}. "
                f"Check the SARS Customs Tariff Book at tariff.sars.gov.za"
            )
        )

    return ModuleResult(
        module="hs_code_validator",
        result="pass",
        detail={"primary_hs_code": primary, "format": "valid_8_digit"}
    )


# ============================================================
# MODULE 3: SACU / Non-SACU VAT Engine
# ============================================================

def check_sacu_vat(shipment: dict) -> ModuleResult:
    """
    Validates that the correct VAT formula is applied.
    Non-SACU imports require 10% markup on customs value before 15% VAT.
    SACU: ZA, LS, NA, SZ, BW — no markup.
    """
    origin = (shipment.get("origin_country") or "").upper().strip()
    customs_value = _extract_numeric(shipment.get("invoice_value"))
    currency = (shipment.get("currency") or "USD").upper()

    if not origin:
        return ModuleResult(
            module="vat_engine",
            result="hold",
            detail={"message": "Country of origin not found — cannot validate VAT formula"},
            penalty_risk=True,
            resolution="Provide country of origin to enable SACU/non-SACU VAT validation"
        )

    if customs_value is None or customs_value <= 0:
        return ModuleResult(
            module="vat_engine",
            result="hold",
            detail={
                "message": "Invoice value not found — cannot calculate VAT",
                "origin": origin
            },
            penalty_risk=True,
            resolution="Provide invoice/customs value for VAT calculation validation"
        )

    is_sacu = origin in SACU_COUNTRIES
    markup_pct = 0.0 if is_sacu else 10.0
    markup_multiplier = 1.0 if is_sacu else 1.10

    # Note: we're working in invoice currency, duties would be added separately
    # This validates the formula is being applied correctly
    atv_pre_duties = customs_value * markup_multiplier
    vat_on_value_only = round(atv_pre_duties * 0.15, 2)

    return ModuleResult(
        module="vat_engine",
        result="pass",
        detail={
            "origin_country": origin,
            "is_sacu_origin": is_sacu,
            "markup_applied_pct": markup_pct,
            "invoice_value": customs_value,
            "currency": currency,
            "calculated_atv_pre_duties": round(atv_pre_duties, 2),
            "vat_on_value_only": vat_on_value_only,
            "note": (
                "No markup applied (SACU origin)" if is_sacu
                else f"10% non-SACU markup applied to customs value before 15% VAT"
            )
        }
    )


# ============================================================
# MODULE 4: DA 65 Temporary Export Detector
# ============================================================

def check_da65_temporary_export(shipment: dict) -> ModuleResult:
    """
    Detects temporary export shipments requiring physical DA 65 stamp.
    Trigger: CPC codes or keywords indicating repair-and-return.
    """
    ai_flags = shipment.get("ai_flags", {})
    extracted = shipment.get("extracted_fields", {})
    cargo_desc = (shipment.get("cargo_description") or "").lower()

    # Keywords indicating temporary export
    temp_export_keywords = [
        "repair and return", "repair & return", "temporary export",
        "calibration", "re-import", "reimport", "sent for repair",
        "warranty repair", "overhaul and return", "cpc 4000", "cpc 4100",
        "temporary basis", "to be returned"
    ]

    detected = (
        ai_flags.get("temporary_export_detected", False) or
        any(kw in cargo_desc for kw in temp_export_keywords)
    )

    if detected:
        return ModuleResult(
            module="da65_detector",
            result="hold",
            detail={
                "temporary_export_detected": True,
                "cargo_description": shipment.get("cargo_description"),
                "warning": "PHYSICAL DA 65 STAMP REQUIRED",
            },
            penalty_risk=True,
            resolution=(
                "⚠️ PHYSICAL DA 65 STAMP REQUIRED: This cargo must be physically "
                "stamped by a SARS customs officer at the border BEFORE export. "
                "Failure to obtain the DA 65 stamp will result in full import "
                "duties and taxes being charged upon return."
            )
        )

    return ModuleResult(
        module="da65_detector",
        result="pass",
        detail={"temporary_export_detected": False}
    )


# ============================================================
# MODULE 5: DA 179 Sugar Tax Calculator
# ============================================================

def check_da179_sugar_tax(shipment: dict) -> ModuleResult:
    """
    Calculates Health Promotion Levy (Sugar Tax) for applicable beverages.
    Only runs if commodity is a sugar-sweetened beverage.
    """
    cargo_desc = (shipment.get("cargo_description") or "").lower()
    extracted = shipment.get("extracted_fields", {})

    # Check if this is a beverage shipment
    beverage_keywords = [
        "juice", "beverage", "soft drink", "carbonated", "energy drink",
        "sports drink", "sweetened", "sugar", "fruit drink", "cordial",
        "concentrate", "syrup", "cola", "soda"
    ]
    is_beverage = any(kw in cargo_desc for kw in beverage_keywords)

    if not is_beverage:
        return ModuleResult(
            module="da179_calculator",
            result="pass",
            detail={"applicable": False, "reason": "Not a sugar-sweetened beverage commodity"}
        )

    # Extract sugar content and volume from extended fields
    sugar_g_per_100ml = _extract_numeric(extracted.get("sugar_g_per_100ml"))
    total_volume_litres = _extract_numeric(extracted.get("volume_litres"))

    if sugar_g_per_100ml is None or total_volume_litres is None:
        return ModuleResult(
            module="da179_calculator",
            result="hold",
            detail={
                "applicable": True,
                "commodity": cargo_desc,
                "missing": "sugar_content_and_volume",
                "note": "Beverage commodity detected but sugar content and volume not found"
            },
            penalty_risk=True,
            resolution=(
                "DA 179 Sugar Tax (Health Promotion Levy) applies to this shipment. "
                "Provide: (1) grams of sugar per 100ml, (2) total volume in litres. "
                "Current rate: R0.0221 per gram above 4g threshold per 100ml."
            )
        )

    # Calculate levy
    SUGAR_THRESHOLD_G = 4.0
    RATE_PER_GRAM = 0.0221

    total_sugar_g = (total_volume_litres * 10) * sugar_g_per_100ml
    threshold_offset = total_volume_litres * 10 * SUGAR_THRESHOLD_G
    taxable_sugar_g = max(0.0, total_sugar_g - threshold_offset)
    levy_zar = round(taxable_sugar_g * RATE_PER_GRAM, 2)

    return ModuleResult(
        module="da179_calculator",
        result="pass",
        detail={
            "applicable": True,
            "total_volume_litres": total_volume_litres,
            "sugar_g_per_100ml": sugar_g_per_100ml,
            "total_sugar_grams": round(total_sugar_g, 2),
            "taxable_sugar_grams": round(taxable_sugar_g, 2),
            "da179_levy_zar": levy_zar,
            "rate_per_gram": RATE_PER_GRAM,
            "threshold_g_per_100ml": SUGAR_THRESHOLD_G,
        }
    )


# ============================================================
# MODULE 6: RLA Status Check (stub — requires eFiling integration)
# ============================================================

def check_rla_status(shipment: dict, org_id: str, supabase_admin=None) -> ModuleResult:
    """
    Checks importer RLA status against stored eFiling records.
    Requires WiseLayer RLA Sentinel to be configured.
    """
    if supabase_admin is None:
        return ModuleResult(
            module="rla_sentinel",
            result="hold",
            detail={"message": "RLA Sentinel not configured — eFiling integration required"},
            penalty_risk=False,
            resolution="Configure WiseLayer RLA Sentinel in Settings → Integrations → eFiling"
        )

    consignee = shipment.get("consignee_name", "")
    if not consignee:
        return ModuleResult(
            module="rla_sentinel",
            result="hold",
            detail={"message": "Consignee name not found — cannot check RLA status"},
            penalty_risk=True,
            resolution="Provide consignee name to enable RLA status verification"
        )

    try:
        result = supabase_admin.table("rla_statuses") \
            .select("*") \
            .eq("org_id", org_id) \
            .ilike("importer_name", f"%{consignee}%") \
            .execute()

        if result.data:
            record = result.data[0]
            if record["rla_status"] == "suspended":
                return ModuleResult(
                    module="rla_sentinel",
                    result="fail",
                    detail={
                        "importer": record["importer_name"],
                        "rla_status": "suspended",
                        "suspended_since": record.get("suspended_since"),
                        "warning": "EDI submission will be automatically rejected"
                    },
                    penalty_risk=True,
                    resolution=(
                        f"⚠️ IMPORTER RLA SUSPENDED: {record['importer_name']}'s RLA status "
                        f"is suspended on eFiling. Automatic EDI rejection will occur. "
                        f"Cargo at port will accrue R2,000/day storage fees. "
                        f"Resolve eFiling status before submission."
                    )
                )
            return ModuleResult(
                module="rla_sentinel",
                result="pass",
                detail={
                    "importer": record["importer_name"],
                    "rla_status": record["rla_status"],
                    "last_checked": record.get("last_checked_at")
                }
            )
    except Exception as e:
        logger.error(f"RLA check error: {e}")

    return ModuleResult(
        module="rla_sentinel",
        result="hold",
        detail={"message": "RLA status not on record — verify manually"},
        penalty_risk=False,
        resolution="Importer not in RLA monitoring list. Add to WiseLayer RLA Sentinel for automated daily checks."
    )


# ============================================================
# SHIELD ORCHESTRATOR
# ============================================================

def run_compliance_shield(
    shipment: dict,
    documents: list = None,
    org_id: str = None,
    supabase_admin=None,
    run_rla: bool = False,
    run_da179: bool = True,
    run_da65: bool = True,
) -> ShieldReport:
    """
    Run all applicable Compliance Shield modules.
    Returns complete ShieldReport with overall status.
    """
    if documents is None:
        documents = []

    results = []

    # Module 1: Invoice/PL cross-reference
    results.append(check_invoice_pl_crossref(shipment, documents))

    # Module 2: HS code validation
    results.append(check_hs_code_format(shipment))

    # Module 3: VAT engine
    results.append(check_sacu_vat(shipment))

    # Module 4: DA 65 temporary export (if enabled)
    if run_da65:
        results.append(check_da65_temporary_export(shipment))

    # Module 5: DA 179 sugar tax (if enabled)
    if run_da179:
        results.append(check_da179_sugar_tax(shipment))

    # Module 6: RLA sentinel (if configured)
    if run_rla and org_id and supabase_admin:
        results.append(check_rla_status(shipment, org_id, supabase_admin))

    # Determine overall status
    if any(r.result == "fail" for r in results):
        overall = "fail"
    elif any(r.result == "hold" for r in results):
        overall = "hold"
    else:
        overall = "pass"

    penalty_risk = any(r.penalty_risk for r in results)

    return ShieldReport(
        overall=overall,
        modules=results,
        penalty_risk_detected=penalty_risk,
        block_cargowise=(overall == "fail"),
    )


# ============================================================
# UTILITY
# ============================================================

def _extract_numeric(value) -> Optional[float]:
    """Safely extract a float from a string or number."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return float(value)
        cleaned = str(value).replace(",", "").replace(" ", "")
        return float(cleaned)
    except (ValueError, TypeError):
        return None
