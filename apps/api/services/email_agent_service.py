"""
CargoIQ — Email Inbox AI Agent
============================
Sits in the background monitoring connected email inboxes.
For every freight-related email it finds, it can:

MODE: auto   → immediately downloads attachments + triggers extraction
MODE: manual → creates an inbox item for human to review and decide

The mode is set per-organisation in Settings → Email Connection.
Operators can switch mid-session from the Inbox page.

Architecture:
  Gmail/IMAP poller  →  classify email  →  extract attachments
       ↓                                         ↓
  auto mode: enqueue extraction          manual mode: create inbox_item
       ↓                                         ↓
  shipment created                       human sees email in Inbox UI
                                              human clicks Process/Skip
                                                    ↓
                                              enqueue extraction
"""
import imaplib
import email
import logging
import asyncio
import io
from email.header import decode_header
from typing import Optional, List, Tuple
from datetime import datetime
import httpx

from ..core.config import settings
from ..core.supabase_client import get_supabase_admin
from .document_service import extract_text_from_pdf, classify_document_type

logger = logging.getLogger(__name__)

FREIGHT_KEYWORDS = [
    "shipment", "freight", "invoice", "packing list", "bill of lading",
    "air waybill", "awb", "b/l", "bol", "commercial invoice", "customs",
    "cargo", "consignment", "forwarder", "clearance", "container", "fcl",
    "lcl", "eta", "etd", "incoterms", "fob", "cif", "dap", "ddp",
    "import", "export", "hs code", "tariff", "sars", "saaff",
    "shipping instructions", "booking confirmation", "release order",
    # Afrikaans / SA-specific
    "vragbrief", "invoer", "uitvoer", "doeane",
]

FREIGHT_ATTACHMENT_TYPES = [
    "application/pdf", "image/tiff", "image/jpeg", "image/png",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]


class InboxAgent:
    """
    Polls an IMAP mailbox, classifies emails, and routes them
    through the extraction pipeline or to the manual review queue.
    """

    def __init__(self, org_id: str, connection_id: str, credentials: dict):
        self.org_id        = org_id
        self.connection_id = connection_id
        self.creds         = credentials   # {host, port, username, password}
        self.admin         = get_supabase_admin()
        self._running      = False

    # ── Public control ────────────────────────────────────────

    async def start(self):
        self._running = True
        logger.info(f"Email agent started for org {self.org_id}")
        while self._running:
            try:
                await self._poll_inbox()
            except Exception as e:
                logger.error(f"Inbox poll error: {e}")
            await asyncio.sleep(60)  # Poll every 60 seconds

    def stop(self):
        self._running = False
        logger.info(f"Email agent stopped for org {self.org_id}")

    # ── Poll ────────────────────────────────────────────────────

    async def _poll_inbox(self):
        conn = self._connect_imap()
        if not conn:
            return

        try:
            conn.select("INBOX")
            # Search for unseen emails
            _, uids = conn.search(None, "UNSEEN")
            uid_list = uids[0].split()

            if not uid_list:
                return

            logger.info(f"Found {len(uid_list)} unseen email(s) for org {self.org_id}")

            for uid in uid_list:
                try:
                    _, data = conn.fetch(uid, "(RFC822)")
                    raw = data[0][1]
                    await self._process_raw_email(raw, uid.decode())
                except Exception as e:
                    logger.error(f"Error processing email uid {uid}: {e}")
        finally:
            try:
                conn.logout()
            except Exception:
                pass

    # ── Email processing ────────────────────────────────────────

    async def _process_raw_email(self, raw: bytes, uid: str):
        msg = email.message_from_bytes(raw)

        subject    = self._decode_header(msg.get("Subject", ""))
        from_addr  = msg.get("From", "")
        message_id = msg.get("Message-ID", f"uid-{uid}")
        date_str   = msg.get("Date", "")

        # Check if this email was already processed
        existing = self.admin.table("inbound_emails")             .select("id")             .eq("message_id", message_id)             .execute()
        if existing.data:
            return  # Already seen

        # Classify the email
        body        = self._extract_body(msg)
        is_freight  = self._is_freight_email(subject, body, from_addr)
        attachments = self._extract_attachments(msg)

        classification = "freight" if is_freight else (
            "non_freight" if body else "unknown"
        )

        # Store inbound email record
        email_record = self.admin.table("inbound_emails").insert({
            "org_id":         self.org_id,
            "connection_id":  self.connection_id,
            "message_id":     message_id,
            "from_address":   from_addr,
            "subject":        subject[:500],
            "body_preview":   body[:300] if body else None,
            "received_at":    date_str,
            "classification": classification,
            "status":         "received",
        }).execute()

        if not email_record.data:
            return

        inbound_id = email_record.data[0]["id"]

        if not is_freight:
            logger.info(f"Non-freight email skipped: {subject[:60]}")
            return

        if not attachments:
            logger.info(f"Freight email but no PDF attachments: {subject[:60]}")
            # Update as processed with note
            self.admin.table("inbound_emails").update({
                "status": "processed",
            }).eq("id", inbound_id).execute()
            return

        # Get org mode setting
        mode = self._get_org_mode()

        logger.info(
            f"Freight email detected: {subject[:60]} | "
            f"attachments={len(attachments)} | mode={mode}"
        )

        if mode == "auto":
            await self._auto_process(inbound_id, attachments, subject)
        else:
            await self._queue_for_manual_review(inbound_id, attachments, subject, from_addr)

    # ── Auto mode ──────────────────────────────────────────────

    async def _auto_process(self, inbound_id: str, attachments: list, subject: str):
        """Auto mode: immediately upload + trigger extraction."""
        from .queue_service import enqueue_cw_execution
        import uuid

        document_ids = []
        for filename, content, mime_type in attachments:
            doc_id = str(uuid.uuid4())
            storage_path = f"{self.org_id}/email-attachments/{doc_id}/{filename}"

            # Store to Supabase Storage
            try:
                self.admin.storage.from_("documents").upload(
                    path=storage_path,
                    file=content,
                    file_options={"content-type": mime_type, "upsert": False}
                )
            except Exception as e:
                logger.error(f"Storage upload failed for {filename}: {e}")
                continue

            # Extract text
            raw_text, ocr_method, page_count = extract_text_from_pdf(content, filename)
            doc_type = classify_document_type(raw_text or "", filename)

            # Create document record
            doc = self.admin.table("documents").insert({
                "id":           doc_id,
                "org_id":       self.org_id,
                "email_id":     inbound_id,
                "storage_path": storage_path,
                "filename":     filename,
                "file_size":    len(content),
                "mime_type":    mime_type,
                "doc_type":     doc_type,
                "raw_text":     (raw_text or "")[:100000],
                "page_count":   page_count,
                "ocr_method":   ocr_method,
                "status":       "processed" if raw_text else "failed",
            }).execute()

            if doc.data:
                document_ids.append(doc_id)

        if document_ids:
            # Create shipment and trigger extraction pipeline
            shipment_id = str(uuid.uuid4())
            self.admin.table("shipments").insert({
                "id":        shipment_id,
                "org_id":    self.org_id,
                "status":    "extracting",
                "source":    "email",
                "source_email_id": inbound_id,
                "processing_started_at": datetime.utcnow().isoformat(),
            }).execute()

            # Link documents
            for doc_id in document_ids:
                self.admin.table("shipment_documents").insert({
                    "shipment_id": shipment_id,
                    "document_id": doc_id,
                }).execute()

            # Trigger extraction via background HTTP call to own API
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        f"http://localhost:8000/api/v1/internal/extract/{shipment_id}",
                        headers={"x-internal-key": settings.SECRET_KEY[:16]}
                    )
            except Exception as e:
                logger.warning(f"Could not trigger extraction via HTTP: {e}")
                # Fallback: mark for background processing
                self.admin.table("shipments").update({
                    "status": "extracted",
                    "extracted_fields": {"pending_extraction": True, "doc_ids": document_ids}
                }).eq("id", shipment_id).execute()

            # Update email status
            self.admin.table("inbound_emails").update({
                "status": "processed"
            }).eq("id", inbound_id).execute()

            logger.info(f"Auto-processed email → shipment {shipment_id}")

    # ── Manual mode ─────────────────────────────────────────────

    async def _queue_for_manual_review(
        self, inbound_id: str, attachments: list, subject: str, from_addr: str
    ):
        """
        Manual mode: store attachments and create inbox item.
        Human sees this in the Inbox page and decides: Process or Skip.
        """
        import uuid

        stored_attachments = []
        for filename, content, mime_type in attachments:
            doc_id = str(uuid.uuid4())
            storage_path = f"{self.org_id}/email-attachments/{doc_id}/{filename}"

            try:
                self.admin.storage.from_("documents").upload(
                    path=storage_path,
                    file=content,
                    file_options={"content-type": mime_type, "upsert": False}
                )
                doc = self.admin.table("documents").insert({
                    "id":           doc_id,
                    "org_id":       self.org_id,
                    "email_id":     inbound_id,
                    "storage_path": storage_path,
                    "filename":     filename,
                    "file_size":    len(content),
                    "mime_type":    mime_type,
                    "status":       "pending",
                }).execute()

                if doc.data:
                    stored_attachments.append({
                        "doc_id":   doc_id,
                        "filename": filename,
                        "size":     len(content),
                    })
            except Exception as e:
                logger.error(f"Manual mode storage error: {e}")

        # Update email with pending status and attachment info
        self.admin.table("inbound_emails").update({
            "status":      "processing",
            "raw_headers": {
                "attachments":  stored_attachments,
                "from":         from_addr,
                "subject":      subject,
                "awaiting_human": True,
            },
        }).eq("id", inbound_id).execute()

        logger.info(
            f"Queued for manual review: {subject[:60]} "
            f"({len(stored_attachments)} attachments)"
        )

    # ── Helpers ─────────────────────────────────────────────────

    def _connect_imap(self) -> Optional[imaplib.IMAP4_SSL]:
        try:
            host = self.creds.get("host", "imap.gmail.com")
            port = int(self.creds.get("port", 993))
            conn = imaplib.IMAP4_SSL(host, port)
            conn.login(self.creds["username"], self.creds["password"])
            return conn
        except Exception as e:
            logger.error(f"IMAP connection failed: {e}")
            return None

    def _decode_header(self, value: str) -> str:
        parts = decode_header(value)
        decoded = []
        for part, charset in parts:
            if isinstance(part, bytes):
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(str(part))
        return " ".join(decoded)

    def _extract_body(self, msg) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body += payload.decode("utf-8", errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body = payload.decode("utf-8", errors="replace")
        return body[:2000]

    def _extract_attachments(self, msg) -> List[Tuple[str, bytes, str]]:
        attachments = []
        for part in msg.walk():
            disposition = part.get("Content-Disposition", "")
            mime_type   = part.get_content_type()

            if "attachment" in disposition or mime_type in FREIGHT_ATTACHMENT_TYPES:
                filename = part.get_filename()
                if not filename:
                    ext = "pdf" if "pdf" in mime_type else "bin"
                    filename = f"attachment.{ext}"

                payload = part.get_payload(decode=True)
                if payload and len(payload) > 0:
                    attachments.append((filename, payload, mime_type))

        return attachments

    def _is_freight_email(self, subject: str, body: str, from_addr: str) -> bool:
        text = (subject + " " + body).lower()
        matches = sum(1 for kw in FREIGHT_KEYWORDS if kw in text)
        return matches >= 2

    def _get_org_mode(self) -> str:
        """Get this org's inbox processing mode: auto or manual."""
        try:
            org = self.admin.table("organisations")                 .select("settings")                 .eq("id", self.org_id)                 .single()                 .execute()
            if org.data:
                return org.data.get("settings", {}).get("inbox_mode", "manual")
        except Exception:
            pass
        return "manual"  # Default to manual — safer


# ── Agent Registry (one agent per connected inbox) ────────────

_running_agents: dict[str, InboxAgent] = {}


async def start_agents_for_org(org_id: str):
    """Start inbox polling agents for all connected email accounts in an org."""
    from ..core.security import decrypt_value
    admin = get_supabase_admin()

    connections = admin.table("email_connections")         .select("*")         .eq("org_id", org_id)         .eq("status", "active")         .execute()

    for conn in (connections.data or []):
        conn_id = conn["id"]
        if conn_id in _running_agents:
            continue

        try:
            creds_raw = decrypt_value(conn["credentials_enc"])
            import json
            creds = json.loads(creds_raw) if creds_raw.startswith("{") else {}
            agent = InboxAgent(org_id, conn_id, creds)
            _running_agents[conn_id] = agent
            asyncio.create_task(agent.start())
            logger.info(f"Started inbox agent for connection {conn_id}")
        except Exception as e:
            logger.error(f"Failed to start agent for connection {conn_id}: {e}")


def stop_agent(connection_id: str):
    if connection_id in _running_agents:
        _running_agents[connection_id].stop()
        del _running_agents[connection_id]


def get_agent_status() -> dict:
    return {
        conn_id: "running"
        for conn_id in _running_agents
    }
