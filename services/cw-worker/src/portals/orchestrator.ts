/**
 * CargoIQ — Portal Orchestrator
 *
 * Single entry point for all portal automation jobs.
 * Receives BullMQ jobs from FastAPI and routes to the correct adapter.
 *
 * Job types handled:
 *   portal:sars:rla_check        → SARS eFiling RLA status
 *   portal:sars:submit_sad500    → SARS eFiling SAD500 submission
 *   portal:sars:release_check    → SARS customs release check
 *   portal:transnet:container    → Transnet container status
 *   portal:transnet:demurrage    → Transnet demurrage calculation
 *   portal:transnet:vessel_eta   → Transnet vessel schedule
 *   portal:shipping:track        → Shipping line container tracking
 *   portal:shipping:release      → Shipping line release check
 */
import { Worker, Job } from "bullmq";
import IORedis from "ioredis";
import { logger }              from "../utils/logger";
import { supabase }            from "../utils/supabase";
import { decrypt }             from "../utils/crypto";
import { SARSEFilingAdapter }  from "./sars-efiling";
import { TransnetNavisAdapter } from "./transnet-navis";
import {
  ShippingLineAdapter, detectShippingLine,
  ShippingLine, createShippingAdapter
} from "./shipping-line";

export interface PortalJobPayload {
  job_type:       string;          // e.g. "portal:sars:rla_check"
  org_id:         string;
  portal_job_id:  string;          // DB record ID in portal_jobs table
  params:         Record<string, any>;
  credentials?:   {                // Encrypted portal credentials
    username_enc: string;
    password_enc: string;
    extra_enc?:   string;
  };
}

// ── Main job processor ────────────────────────────────────────

export async function processPortalJob(payload: PortalJobPayload) {
  const { job_type, org_id, portal_job_id, params, credentials } = payload;
  const startedAt = Date.now();

  logger.info(`[PORTAL] Processing job: ${job_type}`, { org_id, portal_job_id });

  // Mark as running
  await updatePortalJob(portal_job_id, { status: "running", started_at: new Date().toISOString() });

  try {
    // Decrypt credentials if provided
    const creds = credentials ? {
      username:      decrypt(credentials.username_enc),
      password:      decrypt(credentials.password_enc),
      secondFactor:  credentials.extra_enc ? decrypt(credentials.extra_enc) : undefined,
    } : { username: "", password: "" };

    let result;

    // ── Route to correct adapter ──────────────────────────
    if (job_type.startsWith("portal:sars:")) {
      result = await handleSARS(job_type, creds, params);

    } else if (job_type.startsWith("portal:transnet:")) {
      result = await handleTransnet(job_type, creds, params);

    } else if (job_type.startsWith("portal:shipping:")) {
      result = await handleShipping(job_type, params);

    } else {
      throw new Error(`Unknown job type: ${job_type}`);
    }

    const durationMs = Date.now() - startedAt;

    // ── Store result ──────────────────────────────────────
    await updatePortalJob(portal_job_id, {
      status:       result.success ? "completed" : "failed",
      result_data:  result.data,
      screenshot:   result.screenshotPath,
      error:        result.error,
      duration_ms:  durationMs,
      completed_at: new Date().toISOString(),
    });

    // ── Trigger downstream logic ──────────────────────────
    if (result.success) {
      await handlePortalResult(job_type, org_id, result.data || {});
    }

    logger.info(`[PORTAL] Job ${job_type} ${result.success ? "✅ completed" : "❌ failed"}`, {
      duration_ms: durationMs,
    });

    return result;

  } catch (err: any) {
    logger.error(`[PORTAL] Job ${job_type} threw error`, { error: err.message });
    await updatePortalJob(portal_job_id, {
      status:       "failed",
      error:        err.message,
      completed_at: new Date().toISOString(),
    });
    throw err;
  }
}

// ── SARS handler ──────────────────────────────────────────────

async function handleSARS(
  jobType: string,
  creds: { username: string; password: string; secondFactor?: string },
  params: Record<string, any>
) {
  const adapter = new SARSEFilingAdapter();

  if (!creds.username || !creds.password) {
    throw new Error("SARS eFiling credentials not configured for this org");
  }

  const loggedIn = await adapter.login(creds);
  if (!loggedIn) {
    throw new Error("SARS eFiling login failed — check credentials in Settings");
  }

  const actionMap: Record<string, string> = {
    "portal:sars:rla_check":     "check_rla",
    "portal:sars:submit_sad500": "submit_sad500",
    "portal:sars:release_check": "check_release",
  };

  return adapter.execute({
    action: actionMap[jobType] as any || "check_rla",
    ...params,
  });
}

// ── Transnet handler ──────────────────────────────────────────

async function handleTransnet(
  jobType: string,
  creds: { username: string; password: string },
  params: Record<string, any>
) {
  const adapter = new TransnetNavisAdapter();

  if (creds.username) {
    const loggedIn = await adapter.login(creds);
    if (!loggedIn) {
      throw new Error("Transnet login failed — check credentials in Settings");
    }
  } else {
    await (adapter as any).launch();
  }

  const actionMap: Record<string, string> = {
    "portal:transnet:container":  "check_container",
    "portal:transnet:demurrage":  "get_demurrage",
    "portal:transnet:vessel_eta": "check_vessel_eta",
  };

  return adapter.execute({
    action: actionMap[jobType] as any || "check_container",
    ...params,
  });
}

// ── Shipping line handler ─────────────────────────────────────

async function handleShipping(jobType: string, params: Record<string, any>) {
  const containerNumber: string = params.containerNumber || "";

  // Auto-detect line from container prefix, or use specified line
  const line: ShippingLine = params.line ||
    detectShippingLine(containerNumber) || "maersk";

  const adapter = createShippingAdapter(line);
  await (adapter as any).launch();

  return adapter.execute({
    action:          jobType === "portal:shipping:release" ? "check_release" : "track_container",
    containerNumber,
    line,
    billOfLading:    params.billOfLading,
  });
}

// ── Downstream result handlers ────────────────────────────────
// These trigger notifications, update Supabase, and alert operators

async function handlePortalResult(
  jobType: string,
  orgId: string,
  data: Record<string, any>
) {
  try {
    switch (jobType) {

      case "portal:sars:rla_check":
        if (data.rlaStatus === "suspended") {
          // Update RLA status in database
          await supabase.from("rla_statuses").upsert({
            org_id:         orgId,
            importer_code:  data.importerCode,
            rla_status:     "suspended",
            suspended_since: new Date().toISOString(),
            last_checked_at: new Date().toISOString(),
          }, { onConflict: "org_id,importer_code" });

          // Queue WhatsApp alert via notification service
          await supabase.from("notification_queue").insert({
            org_id:   orgId,
            type:     "rla_suspension",
            payload:  data,
            status:   "pending",
          });

          logger.warn(`[PORTAL] ⚠️ RLA SUSPENDED: ${data.importerCode} — alert queued`);

        } else if (data.rlaStatus === "active") {
          await supabase.from("rla_statuses").upsert({
            org_id:         orgId,
            importer_code:  data.importerCode,
            rla_status:     "active",
            last_checked_at: new Date().toISOString(),
          }, { onConflict: "org_id,importer_code" });
        }
        break;

      case "portal:transnet:container":
      case "portal:transnet:demurrage":
        // Update container tracking record
        if (data.containerNumber) {
          await supabase.from("container_tracking").upsert({
            org_id:             orgId,
            container_number:   data.containerNumber,
            status:             data.status,
            location:           data.location,
            vessel_name:        data.vesselName,
            eta:                data.eta,
            is_released:        data.isReleased,
            demurrage_zar:      data.demurrageExposureZAR || 0,
            days_over_free:     data.daysOverFreeTime || 0,
            last_checked_at:    new Date().toISOString(),
          }, { onConflict: "org_id,container_number" });

          // Demurrage alert: > R25,000 exposure
          if ((data.demurrageExposureZAR || 0) > 25000) {
            logger.warn(`[PORTAL] 💰 DEMURRAGE ALERT: ${data.containerNumber} = R${data.demurrageExposureZAR}`);
            await supabase.from("notification_queue").insert({
              org_id:  orgId,
              type:    "demurrage_alert",
              payload: data,
              status:  "pending",
            });
          }

          // Release detected: notify immediately
          if (data.isReleased) {
            logger.info(`[PORTAL] ✅ CONTAINER RELEASED: ${data.containerNumber}`);
            await supabase.from("notification_queue").insert({
              org_id:  orgId,
              type:    "container_released",
              payload: data,
              status:  "pending",
            });
          }
        }
        break;

      case "portal:shipping:track":
      case "portal:shipping:release":
        if (data.containerNumber) {
          await supabase.from("container_tracking").upsert({
            org_id:           orgId,
            container_number: data.containerNumber,
            shipping_line:    data.shippingLine,
            status:           data.status,
            location:         data.location,
            vessel_name:      data.vesselName,
            eta:              data.eta,
            is_released:      data.isReleased,
            last_checked_at:  new Date().toISOString(),
          }, { onConflict: "org_id,container_number" });
        }
        break;
    }
  } catch (err: any) {
    logger.error(`[PORTAL] Result handler error: ${err.message}`);
    // Non-fatal — result is already stored
  }
}

// ── Supabase helpers ──────────────────────────────────────────

async function updatePortalJob(id: string, updates: Record<string, any>) {
  await supabase.from("portal_jobs").update(updates).eq("id", id);
}

// ── BullMQ Worker ─────────────────────────────────────────────

export function startPortalWorker(redis: IORedis) {
  const worker = new Worker(
    "portal-jobs",
    async (job: Job) => {
      logger.info(`[PORTAL WORKER] Job received: ${job.data.job_type}`);
      return processPortalJob(job.data as PortalJobPayload);
    },
    {
      connection: redis,
      concurrency: 3,      // 3 simultaneous portal sessions
      limiter: { max: 10, duration: 60000 }, // 10 jobs/min max
    }
  );

  worker.on("completed", (job) =>
    logger.info(`[PORTAL WORKER] ✅ ${job.data.job_type} completed`));
  worker.on("failed", (job, err) =>
    logger.error(`[PORTAL WORKER] ❌ ${job?.data?.job_type} failed`, { error: err.message }));

  logger.info("[PORTAL WORKER] Ready — listening on queue: portal-jobs");
  return worker;
}
