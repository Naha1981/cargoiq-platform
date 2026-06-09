import { NextRequest, NextResponse } from "next/server";

const FROM  = process.env.EMAIL_FROM      || "alerts@cargoiq.co.za";
const NAME  = process.env.EMAIL_FROM_NAME || "CargoIQ";
const KEY   = (process.env.SECRET_KEY     || "dev").slice(0, 16);
const DRV   = process.env.EMAIL_DRIVER    || "resend";

async function getClient() {
  const { createEmail } = await import("unemail");
  const cfg: any = { driver: DRV };
  if (DRV === "resend")  cfg.key = process.env.RESEND_API_KEY;
  if (DRV === "ses")     { cfg.region = process.env.AWS_REGION || "af-south-1"; cfg.accessKeyId = process.env.AWS_ACCESS_KEY_ID; cfg.secretAccessKey = process.env.AWS_SECRET_ACCESS_KEY; }
  if (DRV === "smtp")    { cfg.host = process.env.SMTP_HOST; cfg.port = parseInt(process.env.SMTP_PORT||"587"); cfg.user = process.env.SMTP_USER; cfg.password = process.env.SMTP_PASSWORD; }
  return createEmail(cfg);
}

export async function POST(req: NextRequest) {
  if (req.headers.get("x-internal-key") !== KEY)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const { to, toName, subject, template, data } = await req.json();
    if (!to || !subject) return NextResponse.json({ error: "Missing: to, subject" }, { status: 400 });
    const client = await getClient();
    await client.send({ from: `${NAME} <${FROM}>`, to: toName ? `${toName} <${to}>` : to, subject, html: buildTemplate(template, data||{}) });
    return NextResponse.json({ success: true });
  } catch (e: any) {
    console.error("[Email]", e.message);
    return NextResponse.json({ error: e.message }, { status: 500 });
  }
}

const wrap = (b: string) => `<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{font-family:-apple-system,sans-serif;background:#F1F4F8;margin:0;padding:24px}
.c{background:#fff;border-radius:6px;border:1px solid #C8D0DA;max-width:560px;margin:0 auto;overflow:hidden}
.h{background:#1A2332;padding:18px 24px}.logo{font-family:monospace;font-size:17px;font-weight:700;color:#F1F4F8}
.logo b{color:#D4922B}.bd{padding:24px}h2{margin:0 0 14px;font-size:16px;font-weight:600;color:#0D1B2A}
p{font-size:13px;line-height:1.7;color:#3D5166;margin:0 0 10px}
.row{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #DDE3EA;font-size:13px}
.row:last-child{border:none}.lbl{color:#6B7E92}.val{font-family:monospace;font-weight:500}
.box{padding:12px 14px;border-radius:4px;margin:12px 0;font-size:13px;line-height:1.6}
.danger{background:#FEF2F2;border:1px solid #F5A5A5;color:#9B1C1C}
.warn{background:#FEF6E7;border:1px solid #E8B84B;color:#7A4F00}
.ok{background:#EBF5EE;border:1px solid #8EC9A0;color:#15632A}
.btn{display:inline-block;padding:10px 20px;background:#B8860B;color:#fff;text-decoration:none;border-radius:4px;font-size:13px;font-weight:600;margin-top:14px}
.ft{padding:14px 24px;background:#F1F4F8;border-top:1px solid #DDE3EA;font-size:11px;color:#9AAAB8}
</style></head><body><div class="c"><div class="h"><div class="logo">Cargo<b>IQ</b></div></div>
<div class="bd">${b}</div><div class="ft">CargoIQ (Pty) Ltd · Johannesburg · POPIA Compliant</div>
</div></body></html>`;

function buildTemplate(t: string, d: Record<string,any>): string {
  const row = (l: string, v: string, color = "") =>
    `<div class="row"><span class="lbl">${l}</span><span class="val"${color ? ` style="color:${color}"` : ""}>${v}</span></div>`;
  switch(t) {
    case "compliance_alert": return wrap(`
      <h2>${d.penaltyRisk?"⚠️ SARS Penalty Risk Detected":"Compliance Review Required"}</h2>
      <div class="box ${d.penaltyRisk?"danger":"warn"}">${d.penaltyRisk?"<strong>SARS penalty exposure.</strong> Do not submit until resolved.":"Review required before CargoWise submission."}</div>
      ${row("Shipment",d.shipmentRef)} ${row("Module",(d.module||"").replace(/_/g," ").toUpperCase())} ${row("Action",d.resolution)}
      <a href="${d.dashboardUrl}" class="btn">Review in CargoIQ →</a>`);
    case "rla_suspension": return wrap(`
      <h2>🚨 RLA SUSPENDED — Immediate Action Required</h2>
      <div class="box danger"><strong>${d.importerName}</strong> RLA suspended. All EDI submissions will be rejected.</div>
      ${row("Importer",d.importerName)} ${row("Code",d.importerCode)} ${row("Port Storage Risk",`${d.storageCost}/day`,"#9B1C1C")}
      <a href="https://efiling.sars.gov.za" class="btn">Go to SARS eFiling →</a>`);
    case "shipment_approved": return wrap(`
      <h2>✅ CargoWise Draft Created</h2>
      <div class="box ok">Shipment approved and draft created in CargoWise.</div>
      ${row("Reference",d.shipmentRef)} ${row("CW Job",d.cwJobId)}
      <a href="${d.dashboardUrl}" class="btn">View in Dashboard →</a>`);
    case "extraction_complete": return wrap(`
      <h2>${d.shieldStatus==="fail"?"🔴 Compliance Failure":"🟡 Review Required"}</h2>
      ${row("Shipment",d.shipmentRef)} ${row("Confidence",(d.confidence||"").toUpperCase())}
      ${row("Shield",(d.shieldStatus||"").toUpperCase(), d.shieldStatus==="pass"?"#15632A":d.shieldStatus==="hold"?"#7A4F00":"#9B1C1C")}
      ${d.flagsCount>0?row("Flags",`${d.flagsCount} issue${d.flagsCount!==1?"s":""}`, "#9B1C1C"):""}
      <a href="${d.dashboardUrl}" class="btn">Review Shipment →</a>`);
    case "weekly_roi": return wrap(`
      <h2>Weekly Report — ${d.orgName}</h2>
      ${row("Shipments",String(d.shipmentsProcessed))} ${row("Hours Saved",`${d.hoursSaved}h`)}
      ${row("Labour Saved",d.labourSavedZar,"#15632A")} ${row("Penalties Prevented",d.penaltiesValueZar,"#15632A")}
      <div class="row" style="border-top:2px solid #C8D0DA;padding-top:12px">
        <span class="lbl" style="font-weight:600;color:#0D1B2A">Total Value</span>
        <span class="val" style="color:#B8860B;font-size:15px">${d.totalValueZar}</span></div>
      <a href="${d.dashboardUrl}" class="btn">View Analytics →</a>`);
    default: return wrap(`<pre>${JSON.stringify(d,null,2)}</pre>`);
  }
}
