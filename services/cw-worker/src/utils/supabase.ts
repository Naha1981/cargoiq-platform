import { createClient } from "@supabase/supabase-js";
export const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!,
  { auth: { persistSession: false } }
);
export async function getShipment(id: string) {
  const { data, error } = await supabase.from("shipments").select("*").eq("id", id).single();
  if (error) throw new Error("Shipment not found: " + error.message);
  return data;
}
export async function getOrgCWCredentials(orgId: string) {
  const { data, error } = await supabase.from("organisations")
    .select("cw_server_url, cw_credentials_enc").eq("id", orgId).single();
  if (error) throw new Error("Org not found: " + error.message);
  return data;
}
export async function updateExecution(id: string, updates: Record<string, unknown>) {
  await supabase.from("cw_executions").update(updates).eq("id", id);
}
export async function updateShipmentStatus(id: string, status: string, extra: Record<string, unknown> = {}) {
  await supabase.from("shipments").update({ status, ...extra }).eq("id", id);
}
export async function writeAuditLog(entry: {
  org_id: string; entity_id: string; action: string;
  actor_type: string; metadata: Record<string, unknown>;
}) {
  await supabase.from("audit_log").insert({ ...entry, entity_type: "shipment" });
}
