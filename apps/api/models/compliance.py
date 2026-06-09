"""CargoIQ — Compliance Shield models."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class ModuleResult(str, Enum):
    PASS = "pass"
    HOLD = "hold"
    FAIL = "fail"


class ComplianceModuleResult(BaseModel):
    module: str
    result: ModuleResult
    detail: Dict[str, Any] = {}
    penalty_risk: bool = False
    resolution: Optional[str] = None

    class Config:
        use_enum_values = True


class ShieldReport(BaseModel):
    overall: ModuleResult
    modules: List[ComplianceModuleResult]
    penalty_risk_detected: bool
    block_cargowise: bool
    run_at: datetime

    class Config:
        use_enum_values = True


class ComplianceEventResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    module: str
    result: str
    detail: Dict[str, Any]
    penalty_risk: bool
    resolution: Optional[str]
    resolved_by: Optional[UUID]
    resolved_at: Optional[datetime]
    resolution_note: Optional[str]
    created_at: datetime


class ResolveComplianceEventRequest(BaseModel):
    resolution_note: str
