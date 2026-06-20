"""
CargoIQ — Notification Service
Sends emails via unemail (Next.js API route) and WhatsApp via Evolution API.
"""
import logging, httpx
from typing import Optional
from ..core.config import settings

logger    = logging.getLogger(__name__)
EMAIL_API = settings.WEB_URL.rstrip("/") + "/api/email"
WA_API    = settings.EVOLUTION_API_URL

async def send_compliance_alert(to: str, name: str, ref: str, sid: str, module: str, resolution: str, penalty: bool = True):
    await _email({"to": to, "toName": name,
        "subject": f"{'⚠️ SARS Penalty Risk' if penalty else 'Compliance Review'} — {ref}",
        "template": "compliance_alert",
        "data": {"shipmentRef": ref, "shipmentId": sid, "module": module,
                 "resolution": resolution, "penaltyRisk": penalty,
                 "dashboardUrl": f"https://app.cargoiq.co.za/shipments/{sid}"}})

async def send_rla_suspension(to: str, name: str, importer: str, code: str):
    await _email({"to": to, "toName": name,
        "subject": f"🚨 RLA SUSPENDED — {importer}",
        "template": "rla_suspension",
        "data": {"importerName": importer, "importerCode": code, "storageCost": "R2,000"}})

async def send_shipment_approved(to: str, ref: str, sid: str, cw_job: Optional[str]):
    await _email({"to": to, "subject": f"✅ {ref} created in CargoWise",
        "template": "shipment_approved",
        "data": {"shipmentRef": ref, "cwJobId": cw_job or "Pending",
                 "dashboardUrl": f"https://app.cargoiq.co.za/shipments/{sid}"}})

async def send_extraction_complete(to: str, ref: str, sid: str, confidence: str, shield: str, flags: int):
    if confidence == "high" and shield == "pass":
        return
    await _email({"to": to,
        "subject": f"{'🔴 Compliance failure' if shield == 'fail' else '🟡 Review required'} — {ref}",
        "template": "extraction_complete",
        "data": {"shipmentRef": ref, "confidence": confidence, "shieldStatus": shield,
                 "flagsCount": flags, "dashboardUrl": f"https://app.cargoiq.co.za/shipments/{sid}"}})

async def send_weekly_roi(to: str, name: str, org: str, count: int, hours: float, labour: float, prevented: int, value: float):
    total = labour + value
    await _email({"to": to, "toName": name,
        "subject": f"CargoIQ Weekly Report — R{total:,.0f} value delivered",
        "template": "weekly_roi",
        "data": {"orgName": org, "shipmentsProcessed": count, "hoursSaved": round(hours, 1),
                 "labourSavedZar": f"R{labour:,.0f}", "penaltiesPrevented": prevented,
                 "penaltiesValueZar": f"R{value:,.0f}", "totalValueZar": f"R{total:,.0f}",
                 "dashboardUrl": "https://app.cargoiq.co.za/analytics"}})

async def whatsapp_compliance(phone: str, ref: str, module: str, resolution: str):
    msg = f"⚠️ *CargoIQ Alert*\n\n*Shipment:* {ref}\n*Issue:* {module.replace('_',' ').title()}\n\n*Action:*\n{resolution}\n\nhttps://app.cargoiq.co.za"
    await _whatsapp(phone, msg)

async def whatsapp_rla(phone: str, importer: str):
    msg = f"🚨 *URGENT — RLA SUSPENDED*\n\n*{importer}* RLA suspended on SARS eFiling.\nAll EDI submissions rejected.\nR2,000/day port storage.\n\nResolve at efiling.sars.gov.za"
    await _whatsapp(phone, msg)

async def _email(payload: dict):
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{EMAIL_API}/send", json=payload,
                             headers={"x-internal-key": settings.SECRET_KEY[:16]})
            if r.status_code != 200:
                logger.error(f"Email failed: {r.status_code} {r.text[:100]}")
            else:
                logger.info(f"Email sent: {payload.get('subject','')[:60]}")
    except httpx.ConnectError:
        logger.warning("Email service unreachable")
    except Exception as e:
        logger.error(f"Email error: {e}")

async def _whatsapp(phone: str, message: str):
    clean = phone.replace("+","").replace(" ","").replace("-","")
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{WA_API}/message/sendText/cargoiq",
                json={"number": clean, "options": {"delay": 1000}, "textMessage": {"text": message}},
                headers={"apikey": "cargoiq-evolution-key"})
            if r.status_code != 200:
                logger.error(f"WhatsApp failed: {r.status_code}")
    except httpx.ConnectError:
        logger.warning("Evolution API unreachable")
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
