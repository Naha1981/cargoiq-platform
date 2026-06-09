import crypto from "crypto";
const ALG = "aes-256-gcm";
function getKey(): Buffer {
  const hex = process.env.ENCRYPTION_KEY || "";
  if (hex.length < 64) return crypto.scryptSync("cargoiq-dev-key", "salt", 32);
  return Buffer.from(hex, "hex");
}
export function decrypt(enc: string): string {
  try {
    const [ivHex, tagHex, data] = enc.split(":");
    const iv  = Buffer.from(ivHex, "hex");
    const tag = Buffer.from(tagHex, "hex");
    const d   = crypto.createDecipheriv(ALG, getKey(), iv);
    d.setAuthTag(tag);
    return d.update(data, "hex", "utf8") + d.final("utf8");
  } catch { return enc; }
}
