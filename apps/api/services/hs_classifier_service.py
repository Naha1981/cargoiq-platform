"""
CargoIQ — HS Code Auto-Classifier
====================================
Uses Claude to suggest the correct SARS 8-digit HS code from a
cargo description. Goes beyond format validation (which the
Compliance Shield already does) to actually suggest the right
classification.

Why this matters:
  - JLog (Gerrit Dyman) handles fine art and designer furniture.
    Original artworks (HS 9701): 0% import duty.
    Textile wall hangings (HS 6304): 45% import duty.
    A wrong classification on a R500,000 artwork = R225,000 overpaid duty.

  - SARS conducted 6,980 seizures in 2023/24 worth R6.7B. The majority
    stem from HS code misdeclaration — often not fraud, just wrong codes.

  - Claude knows the SARS tariff structure and can reason about
    commodity descriptions well enough to flag ambiguous classifications
    and suggest alternatives with their duty rates.

This is NOT a definitive tariff ruling — it's a pre-submission check
that flags risky classifications so the operator can verify before
the declaration reaches SARS. The operator makes the final call.
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field
import anthropic
import instructor
from ..core.config import settings

logger = logging.getLogger(__name__)

# ── Common high-risk SA classification pairs ─────────────────
# Pairs where the difference between two plausible codes is
# a significant duty rate jump — the cases worth flagging.
HIGH_RISK_PAIRS = [
    {"description": "Original artworks, paintings, drawings",
     "low_duty_hs": "9701", "low_duty_rate": 0,
     "high_duty_hs": "6304", "high_duty_rate": 45,
     "note": "Original artworks 0% duty; textile wall hangings 45%. Confirm authenticity documentation."},
    {"description": "Solar panels, photovoltaic modules",
     "low_duty_hs": "8541.40", "low_duty_rate": 0,
     "high_duty_hs": "8507", "high_duty_rate": 10,
     "note": "PV modules 0% duty under REIPPPP concession; battery storage 10%."},
    {"description": "Lithium batteries, energy storage",
     "low_duty_hs": "8507.60", "low_duty_rate": 10,
     "high_duty_hs": "8548", "high_duty_rate": 0,
     "note": "UN3480/3481 DG classification also required. Confirm cell vs pack."},
    {"description": "Designer furniture, homeware",
     "low_duty_hs": "9403", "low_duty_rate": 20,
     "high_duty_hs": "4421", "high_duty_rate": 10,
     "note": "Wooden furniture 20%; wooden articles 10%. Material determines classification."},
    {"description": "Clothing, garments, textiles",
     "low_duty_hs": "6109", "low_duty_rate": 45,
     "high_duty_hs": "6217", "high_duty_rate": 45,
     "note": "Textile classification is a major SARS seizure trigger. Country of origin critical for AGOA/SADC preference."},
]


# ── Structured output schema ─────────────────────────────────

class HSCodeSuggestion(BaseModel):
    """Claude's structured HS code suggestion."""
    suggested_hs_code:    str   = Field(description="Primary suggested 8-digit SARS HS code, e.g. '9701.10.10'")
    suggested_hs_chapter: str   = Field(description="2-digit chapter, e.g. '97'")
    confidence:           str   = Field(description="high | medium | low — confidence in this classification")
    duty_rate_estimate:   str   = Field(description="Estimated import duty rate, e.g. '0%' or '45%' or 'varies'")
    alternative_hs_code:  Optional[str]  = Field(default=None, description="Alternative HS code if classification is ambiguous")
    alternative_duty_rate: Optional[str] = Field(default=None, description="Duty rate for the alternative code")
    classification_risk:  str   = Field(description="low | medium | high — risk of SARS challenging this classification")
    reasoning:            str   = Field(description="Brief explanation of why this HS code applies, max 2 sentences")
    action_required:      Optional[str] = Field(default=None,
        description="Specific action needed before submission, e.g. 'Obtain binding tariff ruling' or 'Attach CO for SADC preference'")


# ── Main classifier function ─────────────────────────────────

async def classify_hs_code(
    cargo_description:   str,
    country_of_origin:   str = "CN",
    current_hs_code:     Optional[str] = None,
    additional_context:  Optional[str] = None,
) -> dict:
    """
    Suggest the correct SARS 8-digit HS code for a cargo description.

    Args:
        cargo_description:  Free-text description from the commercial invoice
        country_of_origin:  ISO country code (affects preferential duty rates)
        current_hs_code:    The HS code currently on the shipment (if any)
        additional_context: Any additional details (unit value, material, end-use)

    Returns:
        Structured suggestion with duty rate, risk flag, and reasoning.
    """
    anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    client = instructor.from_anthropic(anthropic_client)

    # Build the system prompt with SA-specific context
    system_prompt = """You are an expert SARS Customs Classification Specialist with deep knowledge 
of the South African Harmonised Tariff Book (Schedule No. 1, Part 1).

Your task is to suggest the correct 8-digit HS code for a cargo description, specifically 
for South African import purposes. Follow these rules:

1. Use the SARS tariff schedule headings, NOT the generic WCO codes — SA has specific 
   national subheadings in the 7th and 8th digits.
2. Consider SADC and AGOA preferential duty rates where origin permits.
3. Flag classifications where SARS frequently challenges declarations — especially textiles, 
   electronics, artworks, and food products.
4. If the description is ambiguous between two codes with materially different duty rates, 
   flag this explicitly as high risk and suggest getting a binding tariff ruling (BTR).
5. Note DG (dangerous goods) classifications where relevant (lithium batteries, chemicals).
6. Maximum 2 sentences of reasoning — be direct and specific."""

    user_message = f"""Classify this cargo for SARS import purposes:

Cargo Description: {cargo_description}
Country of Origin: {country_of_origin}
{f"Current HS Code on Document: {current_hs_code}" if current_hs_code else ""}
{f"Additional Context: {additional_context}" if additional_context else ""}

Provide your best 8-digit SARS HS code suggestion with duty rate and risk assessment."""

    try:
        suggestion = client.chat.completions.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            response_model=HSCodeSuggestion,
            messages=[
                {"role": "user", "content": user_message}
            ],
            system=system_prompt,
        )

        result = suggestion.model_dump()

        # Check against known high-risk pairs
        risk_pair = None
        for pair in HIGH_RISK_PAIRS:
            if (pair["low_duty_hs"] in (suggestion.suggested_hs_code or "")[:len(pair["low_duty_hs"])] or
                    pair["high_duty_hs"] in (suggestion.suggested_hs_code or "")[:len(pair["high_duty_hs"])]):
                risk_pair = pair
                break

        if risk_pair:
            result["known_risk_pair"] = risk_pair
            result["classification_risk"] = "high"

        # Compare with existing HS code if provided
        if current_hs_code:
            current_chapter = current_hs_code[:4] if len(current_hs_code) >= 4 else current_hs_code
            suggested_chapter = suggestion.suggested_hs_code[:4] if len(suggestion.suggested_hs_code) >= 4 else ""
            result["matches_current"] = current_chapter == suggested_chapter
            if not result["matches_current"]:
                result["mismatch_warning"] = (
                    f"Suggested code {suggestion.suggested_hs_code} differs from "
                    f"current {current_hs_code}. Verify before SARS submission."
                )

        logger.info(
            f"HS classification: '{cargo_description[:50]}' → "
            f"{suggestion.suggested_hs_code} ({suggestion.confidence} confidence, "
            f"{suggestion.classification_risk} risk)"
        )

        return result

    except Exception as e:
        logger.error(f"HS classification failed: {e}")
        return {
            "error":   str(e),
            "status":  "classification_failed",
            "message": "Manual classification required. Check SARS tariff book or request BTR.",
        }


async def bulk_classify(shipment_id: str, org_id: str) -> dict:
    """
    Run HS classification on all line items of a specific shipment.
    Updates the shipment record with classification suggestions.
    """
    from ..core.supabase_client import get_supabase_admin
    admin = get_supabase_admin()

    shipment = admin.table("shipments").select("*") \
        .eq("id", shipment_id).eq("org_id", org_id).single().execute()

    if not shipment.data:
        return {"error": "Shipment not found"}

    s = shipment.data
    description = s.get("cargo_description") or s.get("goods_description") or ""
    origin      = s.get("origin_country_code", "CN")
    current_hs  = s.get("hs_code_primary")

    if not description:
        return {"status": "no_description", "message": "No cargo description on shipment record"}

    suggestion = await classify_hs_code(
        cargo_description=description,
        country_of_origin=origin,
        current_hs_code=current_hs,
    )

    # If there's a mismatch, store as a compliance event for the operator to review
    if suggestion.get("mismatch_warning") or suggestion.get("classification_risk") == "high":
        admin.table("compliance_events").insert({
            "org_id":       org_id,
            "shipment_id":  shipment_id,
            "module":       "hs_classifier",
            "result":       "hold",
            "detail":       suggestion,
            "penalty_risk": True,
            "resolution":   suggestion.get("action_required") or suggestion.get("mismatch_warning"),
        }).execute()

    return suggestion
