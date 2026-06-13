"""
CargoIQ — Public Router
========================
Routes here require NO authentication. Currently: shadow audit
proof pages — a no-login link a founder can text to a prospect
before a sales call.

The proof page is looked up by an opaque share_token (24 bytes,
URL-safe random) and only served if share_enabled = true on the
underlying shadow_audits row. Disabling sharing (DELETE
/audit/shadow/{id}/share) immediately revokes the link.

Nothing else in CargoIQ is exposed without authentication — keep
it that way. Any new endpoint added to this router is public to
the entire internet by definition.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from ..core.supabase_client import get_supabase_admin
from ..services.shadow_audit_service import generate_proof_page_html

router = APIRouter(prefix="/public", tags=["Public"])
logger = logging.getLogger(__name__)


@router.get("/proof/{token}", response_class=HTMLResponse)
async def get_proof_page(token: str):
    """
    Public, no-login proof page for a shadow audit.
    Looked up by share_token; only served if share_enabled = true.
    """
    admin = get_supabase_admin()

    audit = admin.table("shadow_audits") \
        .select("*") \
        .eq("share_token", token) \
        .eq("share_enabled", True) \
        .limit(1) \
        .execute()

    if not audit.data:
        raise HTTPException(404, "This link is invalid or has been disabled")

    audit_record = audit.data[0]
    org = admin.table("organisations").select("name") \
        .eq("id", audit_record["org_id"]).single().execute()
    org_name = org.data.get("name", "Your Organisation") if org.data else "Your Organisation"

    html = generate_proof_page_html(audit_record, org_name)
    return HTMLResponse(content=html)
