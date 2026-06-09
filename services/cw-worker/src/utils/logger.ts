import winston from "winston";
export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || "info",
  format: winston.format.combine(
    winston.format.timestamp({ format: "YYYY-MM-DD HH:mm:ss" }),
    winston.format.printf(({ timestamp, level, message, ...meta }) => {
      const m = Object.keys(meta).length ? " " + JSON.stringify(meta) : "";
      return timestamp + " [" + level + "] [CW-WORKER] " + message + m;
    })
  ),
  transports: [new winston.transports.Console()],
});
