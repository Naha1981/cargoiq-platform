"""
CargoIQ — Pydantic models for shipments and extraction.
These are the schemas used across the API — request bodies,
responses, and the AI extraction output contract.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from uuid import UUID
from enum import Enum


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ShipmentStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    SHIELD_RUNNING = "shield_running"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUSHING_TO_CW = "pushing_to_cw"
    IN_CARGOWISE = "in_cargowise"
    ERROR = "error"


class ShieldStatus(str, Enum):
    PASS = "pass"
    HOLD = "hold"
    FAIL = "fail"
    PENDING = "pending"
    SKIPPED = "skipped"


class ShipmentType(str, Enum):
    AIR_IMPORT = "air_import"
    AIR_EXPORT = "air_export"
    FCL_IMPORT = "fcl_import"
    FCL_EXPORT = "fcl_export"
    LCL_IMPORT = "lcl_import"
    LCL_EXPORT = "lcl_export"
    ROAD_IMPORT = "road_import"
    ROAD_EXPORT = "road_export"
    CUSTOMS_ONLY = "customs_only"
    UNKNOWN = "unknown"


# ── AI Extraction Schema ─────────────────────────────────────
class FieldWithConfidence(BaseModel):
    """A single extracted field with its confidence level."""
    value: Optional[str] = None
    confidence: ConfidenceLevel = ConfidenceLevel.LOW

    class Config:
        use_enum_values = True


class CargoLineItemExtraction(BaseModel):
    """A single line item from a commercial invoice or packing list."""
    line_number: Optional[int] = None
    hs_code: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    description: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    quantity: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    unit: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    unit_weight: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    total_weight: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    unit_value: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    total_value: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    currency: FieldWithConfidence = Field(default_factory=FieldWithConfidence)
    country_of_origin: FieldWithConfidence = Field(default_factory=FieldWithConfidence)


class ShipmentExtraction(BaseModel):
    """
    Full extraction schema — 15 core fields for Phase 1 MVP.
    Instructor forces the LLM to return this exact structure.

    Confidence guide:
    - HIGH: explicitly stated in the source document, unambiguous
    - MEDIUM: inferred from context or partially stated
    - LOW: uncertain, could not find in document
    """

    # Parties
    shipper_name: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Full legal name of the shipper/exporter"
    )
    shipper_address: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Full address of the shipper including country"
    )
    consignee_name: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Full legal name of the consignee/importer"
    )
    consignee_address: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Full address of the consignee including country"
    )
    notify_party: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Notify party name if different from consignee"
    )

    # Routing
    origin_port: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Port or airport of loading/departure. Use IATA/UNLOC codes where possible (e.g. CNSHA, ZADUR)"
    )
    origin_country: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Country of origin as ISO 3166-1 alpha-2 code (e.g. CN, ZA, DE)"
    )
    destination_port: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Port or airport of discharge/destination. Use IATA/UNLOC codes where possible"
    )
    shipment_type: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Type: air_import, air_export, fcl_import, fcl_export, lcl_import, lcl_export, road_import, road_export, customs_only"
    )

    # Cargo
    cargo_description: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="General description of goods as stated on the invoice"
    )
    hs_code_primary: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Primary HS/tariff code. Must be extracted exactly as written — do NOT correct or expand."
    )
    gross_weight: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Total gross weight as a number only (no unit)"
    )
    gross_weight_unit: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Weight unit: KGS, LBS, MT, or CBM"
    )
    net_weight: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Total net weight as a number only"
    )
    number_of_packages: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Total number of packages, cartons, or pieces"
    )
    incoterms: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Incoterms code: FOB, CIF, CFR, DAP, DDP, EXW, FCA, CPT, CIP, DAT, DPU, FAS"
    )

    # Commercial
    invoice_number: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Commercial invoice number exactly as printed"
    )
    invoice_value: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Total invoice value as a number only (no currency symbol)"
    )
    currency: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Currency code: USD, EUR, ZAR, GBP, CNY, etc."
    )

    # Transport reference
    awb_or_bl_number: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Air waybill number (AWB) or Bill of Lading number (BL) as printed"
    )
    vessel_or_flight: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Vessel name or flight number"
    )
    eta: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Estimated time of arrival as YYYY-MM-DD"
    )
    etd: FieldWithConfidence = Field(
        default_factory=FieldWithConfidence,
        description="Estimated time of departure as YYYY-MM-DD"
    )

    # Line items
    line_items: List[CargoLineItemExtraction] = Field(
        default_factory=list,
        description="Individual cargo line items from invoice"
    )

    # AI-detected flags (set independently of Compliance Shield)
    sars_query_flag: bool = Field(
        default=False,
        description="Set to true if document or email mentions a previous SARS query on this cargo"
    )
    description_change_flag: bool = Field(
        default=False,
        description="Set to true if cargo description appears to differ from a stated previous shipment"
    )
    missing_invoice: bool = Field(
        default=False,
        description="Set to true if no commercial invoice was found in the provided documents"
    )
    missing_packing_list: bool = Field(
        default=False,
        description="Set to true if no packing list was found in the provided documents"
    )

    # Extraction metadata
    extraction_notes: Optional[str] = Field(
        default=None,
        description="Any ambiguity, multi-document conflicts, or reasoning the operator should know about"
    )
    extracted_from_docs: List[str] = Field(
        default_factory=list,
        description="List of document IDs used in this extraction"
    )


# ── API Request/Response Models ──────────────────────────────
class ShipmentSummary(BaseModel):
    """Lightweight shipment for list views."""
    id: UUID
    reference: Optional[str]
    org_id: UUID
    shipper_name: Optional[str]
    consignee_name: Optional[str]
    origin_port: Optional[str]
    destination_port: Optional[str]
    shipment_type: Optional[str]
    overall_confidence: Optional[str]
    shield_status: Optional[str]
    status: str
    source: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ShipmentDetail(ShipmentSummary):
    """Full shipment with all extracted fields."""
    cargo_description: Optional[str]
    hs_code_primary: Optional[str]
    gross_weight: Optional[float]
    net_weight: Optional[float]
    weight_unit: Optional[str]
    number_of_packages: Optional[int]
    incoterms: Optional[str]
    invoice_number: Optional[str]
    invoice_value: Optional[float]
    currency: Optional[str]
    awb_or_bl_number: Optional[str]
    vessel_or_flight: Optional[str]
    eta: Optional[date]
    etd: Optional[date]
    extracted_fields: Dict[str, Any] = {}
    confidence_scores: Dict[str, Any] = {}
    ai_flags: Dict[str, Any] = {}
    shield_results: Dict[str, Any] = {}
    cargowise_job_id: Optional[str]
    review_notes: Optional[str]
    reviewed_at: Optional[datetime]


class ShipmentUpdateRequest(BaseModel):
    """Fields a human operator can update in the approval UI."""
    shipper_name: Optional[str] = None
    consignee_name: Optional[str] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    cargo_description: Optional[str] = None
    hs_code_primary: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    weight_unit: Optional[str] = None
    number_of_packages: Optional[int] = None
    incoterms: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_value: Optional[float] = None
    currency: Optional[str] = None
    awb_or_bl_number: Optional[str] = None
    eta: Optional[date] = None
    etd: Optional[date] = None
    review_notes: Optional[str] = None
    extracted_fields: Optional[Dict[str, Any]] = None


class ShipmentApproveRequest(BaseModel):
    notes: Optional[str] = None
    acknowledge_risks: bool = False  # Required if shield_status is 'hold'


class ShipmentRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class PaginatedShipments(BaseModel):
    items: List[ShipmentSummary]
    total: int
    page: int
    page_size: int
    pages: int
