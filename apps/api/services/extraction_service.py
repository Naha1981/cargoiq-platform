"""
CargoIQ — AI Extraction Service
LangChain + Instructor pipeline to extract 100+ structured fields
from freight documents using Claude API.
"""
import logging
from typing import Optional, List
from datetime import datetime
import anthropic
import instructor
from pydantic import BaseModel, Field

from ..core.config import settings

logger = logging.getLogger(__name__)

# ============================================================
# EXTRACTION SCHEMA (Pydantic + Instructor)
# ============================================================

class Confidence(str):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FieldValue(BaseModel):
    """A single extracted field with its confidence level."""
    value: Optional[str] = None
    confidence: str = "low"  # high | medium | low


class CargoLineItemExtracted(BaseModel):
    """One line item from a commercial invoice or packing list."""
    line_number: Optional[int] = None
    hs_code: Optional[FieldValue] = None
    description: Optional[FieldValue] = None
    quantity: Optional[FieldValue] = None
    unit: Optional[FieldValue] = None
    unit_weight: Optional[FieldValue] = None
    total_weight: Optional[FieldValue] = None
    unit_value: Optional[FieldValue] = None
    total_value: Optional[FieldValue] = None
    currency: Optional[FieldValue] = None
    country_of_origin: Optional[FieldValue] = None


class ShipmentExtraction(BaseModel):
    """
    Complete structured extraction of a freight shipment.
    Extracted from emails, commercial invoices, packing lists,
    bills of lading, and air waybills.
    
    Confidence rules:
    - HIGH: value explicitly and clearly stated in source document
    - MEDIUM: reasonably inferred from context  
    - LOW: uncertain, guessed, or partially matching
    
    If a field is not present, set value to null — NEVER fabricate data.
    """
    
    # ---- Parties ----
    shipper_name: Optional[FieldValue] = Field(None, description="Full legal name of the shipper/exporter")
    shipper_address: Optional[FieldValue] = Field(None, description="Full address of shipper")
    consignee_name: Optional[FieldValue] = Field(None, description="Full legal name of the consignee/importer")
    consignee_address: Optional[FieldValue] = Field(None, description="Full address of consignee")
    notify_party: Optional[FieldValue] = Field(None, description="Notify party name and address")
    
    # ---- Routing ----
    origin_port: Optional[FieldValue] = Field(None, description="Port of loading/origin (use IATA/UNLOC code if identifiable)")
    origin_country: Optional[FieldValue] = Field(None, description="Country of origin (ISO 3166-1 alpha-2 code preferred)")
    destination_port: Optional[FieldValue] = Field(None, description="Port of discharge/destination")
    destination_country: Optional[FieldValue] = Field(None, description="Country of destination")
    shipment_type: Optional[FieldValue] = Field(None, description="air_import|air_export|fcl_import|fcl_export|lcl_import|lcl_export|road_import|road_export|customs_only|unknown")
    
    # ---- Cargo ----
    cargo_description: Optional[FieldValue] = Field(None, description="General description of goods")
    hs_code_primary: Optional[FieldValue] = Field(None, description="Primary HS/tariff code - must be 8 digits for SARS compliance")
    gross_weight: Optional[FieldValue] = Field(None, description="Total gross weight as number only")
    gross_weight_unit: Optional[FieldValue] = Field(None, description="Weight unit: KGS, LBS, MT")
    net_weight: Optional[FieldValue] = Field(None, description="Net weight as number only")
    volume_cbm: Optional[FieldValue] = Field(None, description="Volume in cubic meters")
    number_of_packages: Optional[FieldValue] = Field(None, description="Total number of packages/cartons/units")
    incoterms: Optional[FieldValue] = Field(None, description="Incoterms code: FOB, CIF, DAP, DDP, EXW, etc.")
    
    # ---- Commercial ----
    invoice_number: Optional[FieldValue] = Field(None, description="Commercial invoice number")
    invoice_value: Optional[FieldValue] = Field(None, description="Total invoice value as number only")
    currency: Optional[FieldValue] = Field(None, description="Invoice currency: USD, EUR, ZAR, GBP, CNY")
    payment_terms: Optional[FieldValue] = Field(None, description="Payment terms: TT, LC, etc.")
    
    # ---- Transport docs ----
    awb_or_bl_number: Optional[FieldValue] = Field(None, description="Air Waybill number OR Bill of Lading number")
    vessel_or_flight: Optional[FieldValue] = Field(None, description="Vessel name or flight number")
    eta: Optional[FieldValue] = Field(None, description="Estimated arrival date (YYYY-MM-DD format)")
    etd: Optional[FieldValue] = Field(None, description="Estimated departure date (YYYY-MM-DD format)")
    
    # ---- Line items ----
    line_items: List[CargoLineItemExtracted] = Field(default_factory=list, description="Individual cargo line items")
    
    # ---- SARS-specific flags (AI-detected) ----
    sars_query_flag: bool = Field(False, description="True if document mentions previous SARS query on this cargo")
    description_change_flag: bool = Field(False, description="True if description appears to differ from a prior shipment")
    missing_invoice: bool = Field(False, description="True if no commercial invoice document was provided")
    missing_packing_list: bool = Field(False, description="True if no packing list document was provided")
    temporary_export_detected: bool = Field(False, description="True if CPC or description indicates temporary export/repair-and-return")
    
    # ---- Extraction metadata ----
    extraction_notes: Optional[str] = Field(None, description="Notes on ambiguity, conflicts between documents, or reasoning for uncertainty")
    documents_used: List[str] = Field(default_factory=list, description="List of document types used for extraction")
    overall_confidence: str = Field("low", description="high|medium|low — overall confidence in the complete extraction")


# ============================================================
# EXTRACTION SYSTEM PROMPT
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """You are CargoIQ's specialist freight document extraction AI.
You extract structured shipment data from South African logistics documents with precision.

CRITICAL RULES — FOLLOW EXACTLY:

1. CONFIDENCE LEVELS:
   - Set confidence to "high" ONLY when the value is explicitly and clearly stated
   - Use "medium" when reasonably inferred from context  
   - Use "low" when uncertain or partially matching
   - If a field is not present: set value to null — NEVER fabricate or guess data

2. WEIGHTS & MEASUREMENTS:
   - Always extract weight as a number only (no units in value field)
   - Put unit in the separate unit field: KGS, LBS, MT
   - If weight appears on both invoice and packing list and they differ, use packing list and note in extraction_notes

3. HS CODES (CRITICAL FOR SARS COMPLIANCE):
   - Extract exactly as written in the document
   - Do NOT correct or expand — if it's 6 digits, extract 6 digits
   - Note if the code appears invalid in extraction_notes
   - South African SARS requires 8 digits — flag anything else

4. DATES:
   - Convert all dates to YYYY-MM-DD format
   - If year is ambiguous, assume current year

5. PORTS:
   - Use standard UNLOC/IATA codes where identifiable
   - South African ports: ZADUR (Durban), ZACPT (Cape Town), ZAPLZ (Port Elizabeth/Gqeberha)
   - If port code not known, use the full name

6. SARS FLAGS — set to true when:
   - sars_query_flag: document mentions "SARS query", "customs hold", "classification dispute"
   - description_change_flag: phrases like "same as before but different description", "previously filed as", "reclassified"
   - temporary_export_detected: "repair and return", "calibration", "temporary export", CPC codes 4000/4100

7. EXTRACTION NOTES:
   - Use this field to flag anything unusual
   - Note conflicts between documents
   - Flag if cargo description is vague or could be misclassified
   - Note if high-value goods have unusually low declared values

8. SOUTH AFRICA CONTEXT:
   - SACU countries: ZA (South Africa), LS (Lesotho), NA (Namibia), SZ (Eswatini), BW (Botswana)
   - Non-SACU imports require 10% markup on customs value before 15% VAT
   - Common SA incoterms: FOB, CIF, DAP, DDP, CFR, EXW
   - Common trade lanes: China→ZA, India→ZA, EU→ZA, US→ZA, SADC regional

Always return valid JSON matching the schema exactly. Do not include markdown formatting."""


# ============================================================
# EXTRACTION ENGINE
# ============================================================

def get_instructor_client():
    """Get Anthropic client patched with Instructor for structured output."""
    anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return instructor.from_anthropic(anthropic_client)


async def extract_shipment_fields(
    raw_text: str,
    doc_types: List[str],
    filename: str = "",
    previous_extraction: Optional[dict] = None
) -> ShipmentExtraction:
    """
    Core AI extraction function.
    Takes raw document text and returns structured ShipmentExtraction.
    
    Args:
        raw_text: Combined text from all documents
        doc_types: List of document types (e.g., ['commercial_invoice', 'packing_list'])
        filename: Original filename for context
        previous_extraction: Optional previous result for iterative refinement
    
    Returns:
        ShipmentExtraction with all fields and confidence scores
    """
    if not raw_text or len(raw_text.strip()) < 50:
        logger.warning("Raw text too short for extraction")
        return ShipmentExtraction(
            extraction_notes="Document text too short or empty for extraction",
            overall_confidence="low"
        )

    # Build context message
    doc_type_context = f"Document types provided: {', '.join(doc_types)}" if doc_types else ""
    filename_context = f"Filename: {filename}" if filename else ""
    
    user_message = f"""Extract all shipment fields from the following freight document(s).

{doc_type_context}
{filename_context}

DOCUMENT TEXT:
{raw_text[:12000]}  

{"[DOCUMENT TRUNCATED - first 12000 chars only]" if len(raw_text) > 12000 else ""}

Extract every available field. For fields not present, use null. Never fabricate data."""

    try:
        client = get_instructor_client()
        
        extraction = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            system=EXTRACTION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            response_model=ShipmentExtraction,
        )
        
        logger.info(
            f"Extraction complete: confidence={extraction.overall_confidence}, "
            f"flags: sars={extraction.sars_query_flag}, "
            f"desc_change={extraction.description_change_flag}, "
            f"line_items={len(extraction.line_items)}"
        )
        return extraction

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return ShipmentExtraction(
            extraction_notes=f"Extraction failed: {str(e)[:200]}",
            overall_confidence="low"
        )


def extraction_to_shipment_dict(extraction: ShipmentExtraction) -> dict:
    """
    Convert ShipmentExtraction to flat dict for database storage.
    Separates core fields (top-level columns) from extended fields (JSONB).
    """
    def get_val(field: Optional[FieldValue]) -> Optional[str]:
        return field.value if field else None

    def get_conf(field: Optional[FieldValue]) -> str:
        return field.confidence if field else "low"

    # Core columns
    core = {
        "shipper_name": get_val(extraction.shipper_name),
        "shipper_address": get_val(extraction.shipper_address),
        "consignee_name": get_val(extraction.consignee_name),
        "consignee_address": get_val(extraction.consignee_address),
        "notify_party": get_val(extraction.notify_party),
        "origin_port": get_val(extraction.origin_port),
        "origin_country": get_val(extraction.origin_country),
        "destination_port": get_val(extraction.destination_port),
        "destination_country": get_val(extraction.destination_country),
        "shipment_type": get_val(extraction.shipment_type),
        "cargo_description": get_val(extraction.cargo_description),
        "hs_code_primary": get_val(extraction.hs_code_primary),
        "incoterms": get_val(extraction.incoterms),
        "invoice_number": get_val(extraction.invoice_number),
        "currency": get_val(extraction.currency),
        "awb_or_bl_number": get_val(extraction.awb_or_bl_number),
        "vessel_or_flight": get_val(extraction.vessel_or_flight),
        "overall_confidence": extraction.overall_confidence,
    }

    # Numeric fields with safe conversion
    try:
        gw = get_val(extraction.gross_weight)
        core["gross_weight"] = float(gw.replace(",", "")) if gw else None
    except (ValueError, AttributeError):
        core["gross_weight"] = None

    try:
        nw = get_val(extraction.net_weight)
        core["net_weight"] = float(nw.replace(",", "")) if nw else None
    except (ValueError, AttributeError):
        core["net_weight"] = None

    try:
        iv = get_val(extraction.invoice_value)
        core["invoice_value"] = float(iv.replace(",", "")) if iv else None
    except (ValueError, AttributeError):
        core["invoice_value"] = None

    try:
        pkgs = get_val(extraction.number_of_packages)
        core["number_of_packages"] = int(pkgs.replace(",", "")) if pkgs else None
    except (ValueError, AttributeError):
        core["number_of_packages"] = None

    # Date fields
    for date_field, db_field in [("eta", "eta"), ("etd", "etd")]:
        val = get_val(getattr(extraction, date_field))
        core[db_field] = val if val and len(val) == 10 else None

    # Confidence scores (JSONB)
    confidence_scores = {}
    field_names = [
        "shipper_name", "consignee_name", "origin_port", "destination_port",
        "cargo_description", "hs_code_primary", "gross_weight", "invoice_value",
        "incoterms", "awb_or_bl_number", "currency", "shipment_type"
    ]
    for fn in field_names:
        field_obj = getattr(extraction, fn, None)
        if field_obj:
            confidence_scores[fn] = get_conf(field_obj)

    # Calculate overall confidence percentage
    if confidence_scores:
        score_map = {"high": 1.0, "medium": 0.6, "low": 0.2}
        avg = sum(score_map.get(v, 0.2) for v in confidence_scores.values()) / len(confidence_scores)
        core["confidence_percentage"] = round(avg * 100, 1)
    else:
        core["confidence_percentage"] = 0.0

    # AI flags (JSONB)
    ai_flags = {
        "sars_query_flag": extraction.sars_query_flag,
        "description_change_flag": extraction.description_change_flag,
        "missing_invoice": extraction.missing_invoice,
        "missing_packing_list": extraction.missing_packing_list,
        "temporary_export_detected": extraction.temporary_export_detected,
    }

    # Extended fields (everything else in JSONB)
    extracted_fields = {
        "weight_unit": get_val(extraction.gross_weight_unit),
        "volume_cbm": get_val(extraction.volume_cbm),
        "payment_terms": get_val(extraction.payment_terms),
        "origin_country": get_val(extraction.origin_country),
        "documents_used": extraction.documents_used,
        "extraction_notes": extraction.extraction_notes,
    }

    return {
        **core,
        "confidence_scores": confidence_scores,
        "ai_flags": ai_flags,
        "extracted_fields": extracted_fields,
        "weight_unit": get_val(extraction.gross_weight_unit) or "KGS",
    }


def extraction_to_line_items(extraction: ShipmentExtraction, shipment_id: str) -> list:
    """Convert extracted line items to database records."""
    items = []
    for i, item in enumerate(extraction.line_items):
        def gv(f): return f.value if f else None
        def gc(f): return f.confidence if f else "low"

        def safe_float(f):
            v = gv(f)
            if v is None:
                return None
            try:
                return float(str(v).replace(",", ""))
            except (ValueError, TypeError):
                return None

        items.append({
            "shipment_id": shipment_id,
            "line_number": item.line_number or (i + 1),
            "hs_code": gv(item.hs_code),
            "description": gv(item.description),
            "quantity": safe_float(item.quantity),
            "unit": gv(item.unit),
            "unit_weight": safe_float(item.unit_weight),
            "total_weight": safe_float(item.total_weight),
            "unit_value": safe_float(item.unit_value),
            "total_value": safe_float(item.total_value),
            "currency": gv(item.currency),
            "country_of_origin": gv(item.country_of_origin),
            "confidence": gc(item.hs_code) if item.hs_code else "low",
        })
    return items
