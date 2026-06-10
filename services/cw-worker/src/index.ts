/**
 * CargoIQ — CW Worker Entry Point
 * Runs two BullMQ workers simultaneously:
 *   1. cw-executions  → CargoWise form automation
 *   2. portal-jobs    → SARS / Transnet / Shipping line portal automation
 */
import "dotenv/config";
import { Worker, Job }      from "bullmq";
import IORedis               from "ioredis";
import { logger }            from "./utils/logger";
import { processJob }        from "./worker";
import { startPortalWorker } from "./portals/orchestrator";
import fs                    from "fs";

async function main() {
  logger.info("=================================================");
  logger.info("  CargoIQ Automation Worker v1.0");
  logger.info("  CW Execution + Portal Automation");
  logger.info("=================================================");

  // Validate environment
  const required = ["SUPABASE_URL","SUPABASE_SERVICE_ROLE_KEY","REDIS_URL"];
  for (const key of required) {
    if (!process.env[key]) throw new Error(`Missing required env: ${key}`);
  }

  // Ensure screenshot directory
  const shotDir = process.env.SCREENSHOT_PATH || "/tmp/cargoiq-screenshots";
  if (!fs.existsSync(shotDir)) fs.mkdirSync(shotDir, { recursive: true });

  // Redis connection
  const redis = new IORedis(process.env.REDIS_URL!, {
    maxRetriesPerRequest: null,
    enableReadyCheck:     false,
    retryStrategy: (times) => Math.min(times * 500, 5000),
  });

  redis.on("connect", () => logger.info("✅ Redis connected"));
  redis.on("error",  (e) => logger.error("Redis error", { err: String(e) }));

  // ── Worker 1: CargoWise form execution ──────────────────
  const cwWorker = new Worker(
    "cw-executions",
    async (job: Job) => {
      logger.info(`[CW] Processing job ${job.id}`, { attempt: job.attemptsMade });
      return processJob(job.data);
    },
    {
      connection:  redis,
      concurrency: 2,
      limiter:     { max: 5, duration: 1000 },
    }
  );

  cwWorker.on("completed", (job, r) =>
    logger.info(`[CW] ✅ Job ${job.id} done`, { cw_job: r?.jobNumber }));
  cwWorker.on("failed", (job, err) =>
    logger.error(`[CW] ❌ Job ${job?.id} failed`, { error: err.message }));

  // ── Worker 2: Portal automation ──────────────────────────
  const portalWorker = startPortalWorker(redis);

  logger.info("✅ All workers ready");
  logger.info("   Queue 1: cw-executions  (CargoWise form automation)");
  logger.info("   Queue 2: portal-jobs    (SARS / Transnet / Shipping lines)");

  // ── Graceful shutdown ─────────────────────────────────────
  const shutdown = async (signal: string) => {
    logger.info(`${signal} received — draining workers...`);
    await cwWorker.close();
    await portalWorker.close();
    redis.disconnect();
    logger.info("Shutdown complete");
    process.exit(0);
  };

  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("SIGINT",  () => shutdown("SIGINT"));
}

main().catch(err => {
  console.error("Fatal startup error:", err.message);
  process.exit(1);
});
