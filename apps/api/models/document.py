"""CargoIQ — Document models."""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class DocumentResponse(BaseModel):
    id: UUID
    org_id: UUID
    filename: Optional[str]
    doc_type: Optional[str]
    file_size: Optional[int]
    mime_type: Optional[str]
    page_count: Optional[int]
    status: str
    ocr_method: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentUploadResponse(BaseModel):
    document_id: UUID
    filename: str
    status: str = "queued"
    message: str = "Document uploaded successfully and queued for processing"
