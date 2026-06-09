import "dotenv/config";
import { Worker, Job }  from "bullmq";
import IORedis          from "ioredis";
import { logger }       from "./utils/logger";
import { processJob }   from "./worker";
import fs               from "fs";

async function main() {
  logger.info("CargoIQ CW Worker starting...");
  if (!process.env.SUPABASE_URL)         throw new Error("Missing: SUPABASE_URL");
  if (!process.env.SUPABASE_SERVICE_ROLE_KEY) throw new Error("Missing: SUPABASE_SERVICE_ROLE_KEY");
  if (!process.env.REDIS_URL)            throw new Error("Missing: REDIS_URL");

  const screenshotPath = process.env.SCREENSHOT_PATH || "/tmp/cargoiq-screenshots";
  if (!fs.existsSync(screenshotPath)) fs.mkdirSync(screenshotPath, { recursive: true });

  const redis = new IORedis(process.env.REDIS_URL!, {
    maxRetriesPerRequest: null, enableReadyCheck: false,
  });
  redis.on("connect", () => logger.info("Redis connected"));
  redis.on("error",  (e) => logger.error("Redis error", { error: String(e) }));

  const worker = new Worker(
    "cw-executions",
    async (job: Job) => {
      logger.info("Processing job " + job.id, { attempt: job.attemptsMade });
      return processJob(job.data);
    },
    { connection: redis, concurrency: 2, limiter: { max: 5, duration: 1000 } }
  );

  worker.on("completed", (job, result) =>
    logger.info("Job " + job.id + " done", { success: result?.success, cw_job: result?.jobNumber }));
  worker.on("failed", (job, err) =>
    logger.error("Job " + job?.id + " failed", { error: err.message }));

  logger.info("CW Worker ready — listening on queue: cw-executions");

  const shutdown = async () => {
    logger.info("Shutting down...");
    await worker.close();
    redis.disconnect();
    process.exit(0);
  };
  process.on("SIGTERM", shutdown);
  process.on("SIGINT",  shutdown);
}

main().catch(err => { console.error("Fatal:", err.message); process.exit(1); });
