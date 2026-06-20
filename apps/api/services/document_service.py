"""
CargoIQ — Document Service
Handles PDF upload, storage, and text extraction.
Primary: pypdf (fast, for digitally-generated PDFs — most invoices,
SAD500s, and CargoWise exports). Fallback: Tesseract OCR for scanned
or photographed documents (free, CPU-only, no GPU required).
"""
import io
import uuid
import logging
from pathlib import Path
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status

logger = logging.getLogger(__name__)

# MIME type → document type mapping
MIME_TO_DOC_TYPE = {
    "application/pdf": None,  # classified by content
    "image/jpeg": None,
    "image/png": None,
    "image/tiff": None,
}

ALLOWED_MIME_TYPES = list(MIME_TO_DOC_TYPE.keys()) + [
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
]

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def validate_upload(file: UploadFile) -> bytes:
    """Validate file type and size. Returns file bytes."""
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type {file.content_type} not supported. Allowed: PDF, JPEG, PNG, TIFF, DOC, DOCX"
        )
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: 50MB"
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    return content


def build_storage_path(org_id: str, filename: str, doc_id: str) -> str:
    """Build Supabase Storage path: org_id/documents/doc_id/filename"""
    safe_filename = Path(filename).name  # strip any path traversal
    return f"{org_id}/documents/{doc_id}/{safe_filename}"


async def upload_to_storage(
    supabase_admin,
    org_id: str,
    file_content: bytes,
    filename: str,
    mime_type: str,
    doc_id: str
) -> str:
    """Upload file bytes to Supabase Storage. Returns storage path."""
    storage_path = build_storage_path(org_id, filename, doc_id)
    try:
        supabase_admin.storage.from_("documents").upload(
            path=storage_path,
            file=file_content,
            file_options={"content-type": mime_type, "upsert": False}
        )
        return storage_path
    except Exception as e:
        logger.error(f"Storage upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store document. Please try again."
        )


def extract_text_from_pdf(file_content: bytes, filename: str) -> Tuple[str, str, int]:
    """
    Extract text from PDF using Marker (primary) with pypdf fallback.
    Returns: (raw_text, ocr_method, page_count)
    """
    # First try digital PDF extraction (fast, no OCR needed)
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_content))
        page_count = len(reader.pages)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text() or ""
            pages_text.append(text)
        full_text = "\n\n".join(pages_text).strip()

        # If we got meaningful text, use it (digital PDF)
        if len(full_text) > 100 and not _is_mostly_whitespace(full_text):
            logger.info(f"Digital PDF extraction: {len(full_text)} chars, {page_count} pages")
            return full_text, "digital_pdf", page_count
    except Exception as e:
        logger.warning(f"pypdf extraction failed: {e}")
        page_count = 1

    # Fallback: Tesseract OCR for scanned documents (free, CPU-only,
    # no GPU required — tesseract-ocr + poppler-utils are tiny apt
    # packages, no PyTorch/CUDA dependency chain)
    try:
        import pytesseract
        import pdf2image

        logger.info(f"Running Tesseract OCR on {filename}")
        images = pdf2image.convert_from_bytes(file_content, last_page=50)
        page_count = len(images)
        pages_text = [pytesseract.image_to_string(img) for img in images]
        full_text = "\n\n".join(pages_text).strip()
        logger.info(f"Tesseract OCR complete: {len(full_text)} chars, {page_count} pages")
        return full_text, "tesseract_ocr", page_count

    except ImportError:
        logger.warning("pytesseract not available, using pdfplumber fallback")
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}, using pdfplumber fallback")

    # Last resort: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            page_count = len(pdf.pages)
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                # Also extract tables
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                pages_text.append(" | ".join(str(cell or "") for cell in row))
                pages_text.append(text)
            full_text = "\n".join(pages_text).strip()
        return full_text, "pdfplumber", page_count
    except Exception as e:
        logger.error(f"All extraction methods failed: {e}")
        return "", "failed", 0


def _is_mostly_whitespace(text: str) -> bool:
    """Check if extracted text is mostly whitespace/garbage (scanned PDF)."""
    non_space = sum(1 for c in text if not c.isspace())
    return non_space < len(text) * 0.1


def classify_document_type(raw_text: str, filename: str) -> str:
    """
    Classify document type from content keywords.
    Returns DocumentType string.
    """
    text_lower = raw_text.lower()
    filename_lower = filename.lower()

    # Check filename first (fast path)
    if any(kw in filename_lower for kw in ["invoice", "inv_", "_inv"]):
        return "commercial_invoice"
    if any(kw in filename_lower for kw in ["packing", "pack_list", "pl_"]):
        return "packing_list"
    if any(kw in filename_lower for kw in ["awb", "airwaybill", "air_waybill"]):
        return "air_waybill"
    if any(kw in filename_lower for kw in ["bl_", "bill_of_lading", "b_l"]):
        return "bill_of_lading"
    if any(kw in filename_lower for kw in ["co_", "cert_origin", "certificate"]):
        return "certificate_of_origin"

    # Content-based classification
    invoice_keywords = ["commercial invoice", "invoice no", "invoice number",
                        "seller", "buyer", "unit price", "total amount",
                        "payment terms", "bank details"]
    packing_keywords = ["packing list", "net weight", "gross weight",
                        "carton", "package", "marks & numbers", "dimensions"]
    awb_keywords = ["air waybill", "airway bill", "awb no", "iata",
                    "airport of departure", "airport of destination"]
    bl_keywords = ["bill of lading", "b/l no", "vessel", "port of loading",
                   "port of discharge", "shipper", "consignee", "notify party",
                   "ocean bill"]

    scores = {
        "commercial_invoice": sum(1 for kw in invoice_keywords if kw in text_lower),
        "packing_list": sum(1 for kw in packing_keywords if kw in text_lower),
        "air_waybill": sum(1 for kw in awb_keywords if kw in text_lower),
        "bill_of_lading": sum(1 for kw in bl_keywords if kw in text_lower),
    }

    best_type = max(scores, key=scores.get)
    if scores[best_type] >= 2:
        return best_type
    return "unknown"
