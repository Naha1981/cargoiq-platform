import { logger }              from "./utils/logger";
import { decrypt }              from "./utils/crypto";
import { getShipment, getOrgCWCredentials, updateExecution, updateShipmentStatus, writeAuditLog } from "./utils/supabase";
import { parseCWCredentials, createCWSession, closeCWSession } from "./utils/session";
import { createAirImportDraft } from "./forms/air-import";

export interface JobPayload {
  execution_id: string; shipment_id: string;
  org_id: string; execution_type: "playwright" | "eadaptor_xml";
}

export async function processJob(payload: JobPayload): Promise<any> {
  const { execution_id, shipment_id, org_id } = payload;
  const startedAt = new Date();

  await updateExecution(execution_id, { status: "running", started_at: startedAt.toISOString() });

  try {
    const shipment = await getShipment(shipment_id);
    logger.info("Shipment loaded", { ref: shipment.reference, type: shipment.shipment_type });

    const org = await getOrgCWCredentials(org_id);
    if (!org.cw_server_url || !org.cw_credentials_enc)
      throw new Error("CargoWise credentials not configured. Go to Settings → CargoWise.");

    const creds   = parseCWCredentials(org.cw_server_url, org.cw_credentials_enc);
    const session = await createCWSession(creds);

    let result: any;
    try {
      const type = shipment.shipment_type || "unknown";
      if (type.includes("air")) {
        result = await createAirImportDraft(session, {
          shipperName: shipment.shipper_name, consigneeName: shipment.consignee_name,
          awbNumber: shipment.awb_or_bl_number, originPort: shipment.origin_port,
          destinationPort: shipment.destination_port, cargoDescription: shipment.cargo_description,
          grossWeight: shipment.gross_weight, weightUnit: shipment.weight_unit,
          pieces: shipment.number_of_packages, invoiceNumber: shipment.invoice_number,
          invoiceValue: shipment.invoice_value, currency: shipment.currency,
          incoterms: shipment.incoterms, eta: shipment.eta, hsCode: shipment.hs_code_primary,
        });
      } else {
        throw new Error("Sea/road freight automation coming Phase 2. Approve manually in CargoWise.");
      }
    } finally {
      await closeCWSession(session);
    }

    const durationMs = Date.now() - startedAt.getTime();
    if (result.success) {
      await updateExecution(execution_id, {
        status: "success", screenshot_path: result.screenshotPath,
        cw_response: { job_number: result.jobNumber, fields_set: result.fieldsSet, fields_failed: result.fieldsFailed },
        duration_ms: durationMs, completed_at: new Date().toISOString(),
      });
      await updateShipmentStatus(shipment_id, "in_cargowise", { cargowise_job_id: result.jobNumber });
      await writeAuditLog({ org_id, entity_id: shipment_id, action: "pushed_to_cargowise",
        actor_type: "ai_system", metadata: { execution_id, cw_job: result.jobNumber, duration_ms: durationMs } });
      logger.info("Draft created", { shipment_id, cw_job: result.jobNumber, duration_ms: durationMs });
    } else {
      await updateExecution(execution_id, { status: "failed", error_message: result.error,
        duration_ms: durationMs, completed_at: new Date().toISOString() });
      await updateShipmentStatus(shipment_id, "error");
    }
    return result;

  } catch (err: any) {
    const durationMs = Date.now() - startedAt.getTime();
    logger.error("Job error", { execution_id, error: err.message });
    await updateExecution(execution_id, { status: "failed", error_message: err.message,
      duration_ms: durationMs, completed_at: new Date().toISOString() });
    await updateShipmentStatus(shipment_id, "error").catch(() => {});
    return { success: false, error: err.message };
  }
}
