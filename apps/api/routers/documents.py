"""
CargoIQ — Documents Router
Upload, store, extract text, classify freight documents.
"""
import uuid
import logging
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from ..core.security import get_current_user_with_org
from ..core.supabase_client import get_supabase_admin
from ..models.schemas import DocumentUploadResponse
from ..services.document_service import (
    validate_upload, upload_to_storage,
    extract_text_from_pdf, classify_document_type
)

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger(__name__)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user_with_org)
):
    """
    Upload a freight document (PDF, image).
    Steps:
    1. Validate file type and size
    2. Upload to Supabase Storage
    3. Create document record in DB
    4. Queue OCR extraction (background task)
    """
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    doc_id = str(uuid.uuid4())

    # 1. Validate
    file_content = await validate_upload(file)
    filename = file.filename or f"document_{doc_id}.pdf"
    mime_type = file.content_type or "application/pdf"

    # 2. Upload to storage
    storage_path = await upload_to_storage(
        admin, org_id, file_content, filename, mime_type, doc_id
    )

    # 3. Create DB record
    doc_record = {
        "id": doc_id,
        "org_id": org_id,
        "storage_path": storage_path,
        "filename": filename,
        "file_size": len(file_content),
        "mime_type": mime_type,
        "status": "pending",
    }
    result = admin.table("documents").insert(doc_record).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create document record")

    # 4. Queue background extraction
    background_tasks.add_task(
        process_document_background,
        doc_id=doc_id,
        file_content=file_content,
        filename=filename,
        org_id=org_id
    )

    logger.info(f"Document uploaded: {doc_id} ({filename}, {len(file_content)} bytes)")

    return DocumentUploadResponse(
        id=doc_id,
        filename=filename,
        storage_path=storage_path,
        status="pending",
        created_at=result.data[0]["created_at"]
    )


@router.get("/{doc_id}")
async def get_document(
    doc_id: str,
    include_text: bool = False,
    current_user: dict = Depends(get_current_user_with_org)
):
    """Get document details. Set include_text=true to get raw extracted text."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    select_cols = "id,org_id,filename,doc_type,status,page_count,ocr_method,file_size,created_at"
    if include_text:
        select_cols += ",raw_text"

    result = admin.table("documents") \
        .select(select_cols) \
        .eq("id", doc_id) \
        .eq("org_id", org_id) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Document not found")

    return result.data


@router.get("/")
async def list_documents(
    page: int = 1,
    limit: int = 20,
    current_user: dict = Depends(get_current_user_with_org)
):
    """List all documents for the organisation."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]
    offset = (page - 1) * limit

    result = admin.table("documents") \
        .select("id,filename,doc_type,status,page_count,file_size,created_at") \
        .eq("org_id", org_id) \
        .order("created_at", desc=True) \
        .range(offset, offset + limit - 1) \
        .execute()

    count_result = admin.table("documents") \
        .select("id", count="exact") \
        .eq("org_id", org_id) \
        .execute()

    total = count_result.count or 0

    return {
        "data": result.data,
        "total": total,
        "page": page,
        "limit": limit,
        "has_more": (offset + limit) < total
    }


@router.post("/{doc_id}/reprocess")
async def reprocess_document(
    doc_id: str,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user_with_org)
):
    """Re-run OCR and classification on an existing document."""
    admin = get_supabase_admin()
    org_id = current_user["org_id"]

    # Get document record
    doc = admin.table("documents") \
        .select("*") \
        .eq("id", doc_id) \
        .eq("org_id", org_id) \
        .single() \
        .execute()

    if not doc.data:
        raise HTTPException(status_code=404, detail="Document not found")

    # Download from storage
    try:
        file_bytes = admin.storage.from_("documents").download(doc.data["storage_path"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not retrieve document: {e}")

    # Reset status
    admin.table("documents").update({"status": "pending"}).eq("id", doc_id).execute()

    background_tasks.add_task(
        process_document_background,
        doc_id=doc_id,
        file_content=file_bytes,
        filename=doc.data.get("filename", "document.pdf"),
        org_id=org_id
    )

    return {"message": "Reprocessing queued", "doc_id": doc_id}


# ============================================================
# BACKGROUND TASK
# ============================================================

async def process_document_background(
    doc_id: str,
    file_content: bytes,
    filename: str,
    org_id: str
):
    """
    Background task: OCR extraction + document classification.
    Called after successful upload.
    """
    admin = get_supabase_admin()

    try:
        # Update status to processing
        admin.table("documents").update({"status": "processing"}).eq("id", doc_id).execute()

        # Run OCR extraction
        raw_text, ocr_method, page_count = extract_text_from_pdf(file_content, filename)

        # Classify document type
        doc_type = classify_document_type(raw_text, filename) if raw_text else "unknown"

        # Update document record with results
        admin.table("documents").update({
            "raw_text": raw_text[:100000] if raw_text else None,  # Cap at 100K chars
            "doc_type": doc_type,
            "page_count": page_count,
            "ocr_method": ocr_method,
            "status": "processed" if raw_text else "failed",
        }).eq("id", doc_id).execute()

        logger.info(f"Document processed: {doc_id} → {doc_type} ({ocr_method}, {page_count}p, {len(raw_text or '')}c)")

    except Exception as e:
        logger.error(f"Document processing failed for {doc_id}: {e}")
        admin.table("documents").update({
            "status": "failed",
        }).eq("id", doc_id).execute()
