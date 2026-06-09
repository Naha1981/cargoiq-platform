"""
CargoIQ — Pydantic schemas for API request/response validation.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Any
from datetime import datetime, date
from enum import Enum
import uuid


# ============================================================
# ENUMS
# ============================================================

class UserRole(str, Enum):
    ADMIN = "admin"
    OPERATIONS_MANAGER = "operations_manager"
    OPERATOR = "operator"
    VIEWER = "viewer"


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


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DocumentType(str, Enum):
    COMMERCIAL_INVOICE = "commercial_invoice"
    PACKING_LIST = "packing_list"
    AIR_WAYBILL = "air_waybill"
    BILL_OF_LADING = "bill_of_lading"
    CERTIFICATE_OF_ORIGIN = "certificate_of_origin"
    CUSTOMS_DECLARATION = "customs_declaration"
    DELIVERY_NOTE = "delivery_note"
    INSURANCE_CERT = "insurance_cert"
    OTHER = "other"
    UNKNOWN = "unknown"


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


# ============================================================
# AUTH SCHEMAS
# ============================================================

class SignUpRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2)
    org_name: str = Field(min_length=2)
    org_slug: Optional[str] = None


class SignInRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    organisation: dict


# ============================================================
# DOCUMENT SCHEMAS
# ============================================================

class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    storage_path: str
    status: str
    doc_type: Optional[str] = None
    created_at: datetime


class DocumentResponse(BaseModel):
    id: str
    org_id: str
    filename: Optional[str]
    doc_type: Optional[str]
    status: str
    page_count: Optional[int]
    raw_text: Optional[str] = None  # excluded in list views
    ocr_method: Optional[str]
    created_at: datetime


# ============================================================
# SHIPMENT SCHEMAS
# ============================================================

class FieldWithConfidence(BaseModel):
    value: Optional[Any] = None
    confidence: Confidence = Confidence.LOW


class CargoLineItem(BaseModel):
    line_number: Optional[int] = None
    hs_code: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_weight: Optional[float] = None
    total_weight: Optional[float] = None
    unit_value: Optional[float] = None
    total_value: Optional[float] = None
    currency: Optional[str] = None
    country_of_origin: Optional[str] = None
    confidence: Confidence = Confidence.MEDIUM


class ShipmentSummary(BaseModel):
    """Lightweight schema for list views."""
    id: str
    reference: Optional[str]
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


class ShipmentDetail(BaseModel):
    """Full schema for detail view."""
    id: str
    reference: Optional[str]
    org_id: str

    # Parties
    shipper_name: Optional[str]
    shipper_address: Optional[str]
    consignee_name: Optional[str]
    consignee_address: Optional[str]
    notify_party: Optional[str]

    # Routing
    origin_port: Optional[str]
    origin_country: Optional[str]
    destination_port: Optional[str]
    destination_country: Optional[str]
    shipment_type: Optional[str]

    # Cargo
    cargo_description: Optional[str]
    hs_code_primary: Optional[str]
    gross_weight: Optional[float]
    net_weight: Optional[float]
    weight_unit: Optional[str]
    number_of_packages: Optional[int]
    incoterms: Optional[str]

    # Commercial
    invoice_number: Optional[str]
    invoice_value: Optional[float]
    currency: Optional[str]

    # Transport
    awb_or_bl_number: Optional[str]
    vessel_or_flight: Optional[str]
    eta: Optional[date]
    etd: Optional[date]

    # AI output
    extracted_fields: dict = {}
    confidence_scores: dict = {}
    overall_confidence: Optional[str]
    confidence_percentage: Optional[float]
    ai_flags: dict = {}

    # Compliance
    shield_status: Optional[str]
    shield_results: dict = {}
    shield_run_at: Optional[datetime]

    # Status
    status: str
    cargowise_job_id: Optional[str]
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_notes: Optional[str]
    source: Optional[str]

    created_at: datetime
    updated_at: datetime


class ShipmentApproveRequest(BaseModel):
    notes: Optional[str] = None
    acknowledged_risks: bool = False  # Required if shield has HOLD items


class ShipmentRejectRequest(BaseModel):
    reason: str = Field(min_length=5)


class ShipmentUpdateRequest(BaseModel):
    """Fields that a human reviewer can edit."""
    shipper_name: Optional[str] = None
    consignee_name: Optional[str] = None
    origin_port: Optional[str] = None
    destination_port: Optional[str] = None
    cargo_description: Optional[str] = None
    hs_code_primary: Optional[str] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    invoice_number: Optional[str] = None
    invoice_value: Optional[float] = None
    currency: Optional[str] = None
    awb_or_bl_number: Optional[str] = None
    incoterms: Optional[str] = None
    review_notes: Optional[str] = None


# ============================================================
# COMPLIANCE SCHEMAS
# ============================================================

class ComplianceModuleResult(BaseModel):
    module: str
    result: str  # pass | hold | fail
    detail: dict = {}
    penalty_risk: bool = False
    resolution: Optional[str] = None


class ComplianceShieldReport(BaseModel):
    overall: str  # pass | hold | fail
    modules: List[ComplianceModuleResult]
    penalty_risk_detected: bool
    block_cargowise: bool
    run_at: datetime


# ============================================================
# DASHBOARD / ANALYTICS SCHEMAS
# ============================================================

class DashboardKPIs(BaseModel):
    queue_size: int
    processed_today: int
    automation_rate: float
    exceptions_requiring_review: int
    compliance_flags_today: int
    avg_processing_time_seconds: Optional[float]


class ProcessingVolumeDataPoint(BaseModel):
    date: str
    total: int
    auto_approved: int
    manual_reviewed: int
    failed: int


# ============================================================
# PAGINATED RESPONSE
# ============================================================

class PaginatedResponse(BaseModel):
    data: List[Any]
    total: int
    page: int
    limit: int
    has_more: bool
