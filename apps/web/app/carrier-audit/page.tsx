"use client";
import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Receipt, Upload, AlertTriangle, CheckCircle, FileX,
  Plus, Trash2, FileText, TrendingDown, RefreshCw, X
} from "lucide-react";
import { TopNav }   from "@/components/layout/TopNav";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import toast from "react-hot-toast";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const CHARGE_TYPES = [
  "ocean_freight","air_freight","baf","caf","thc",
  "documentation","demurrage","detention","other"
];

const carrierApi = {
  summary:    () => apiClient.get("/carrier-audit/summary"),
  audits:     (status?: string) => apiClient.get(`/carrier-audit/${status ? `?status=${status}` : ""}`),
  rateCards:  () => apiClient.get("/carrier-audit/rate-cards"),
  addRateCard: (body: any) => apiClient.post("/carrier-audit/rate-cards", body),
  deleteRateCard: (id: string) => apiClient.delete(`/carrier-audit/rate-cards/${id}`),
};

async function uploadInvoice(file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/carrier-audit/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${localStorage.getItem("cargoiq_token")}` },
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    clean:               "badge-pass",
    overcharge_detected: "badge-fail",
    no_rate_card:        "badge-neutral",
    review_required:     "badge-hold",
  };
  const label: Record<string, string> = {
    clean:               "CLEAN",
    overcharge_detected: "OVERCHARGE",
    no_rate_card:        "NO RATE CARD",
    review_required:     "REVIEW",
  };
  return <span className={cn("badge", map[status] || "badge-neutral")}>{label[status] || status.toUpperCase()}</span>;
}

function RateCardModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const [form, setForm] = useState({
    carrier_name: "", charge_type: "ocean_freight", lane: "",
    unit: "per_container", agreed_rate: "", currency: "USD", notes: "",
  });
  const mut = useMutation({
    mutationFn: () => carrierApi.addRateCard({
      ...form,
      lane: form.lane || undefined,
      agreed_rate: parseFloat(form.agreed_rate),
    }),
    onSuccess: () => { toast.success("Rate card saved"); onSaved(); onClose(); },
    onError: (e: any) => toast.error(e.message || "Save failed"),
  });

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="card w-full max-w-md">
        <div className="card-header">
          <h3 className="text-sm font-semibold">Add Rate Card</h3>
          <button className="btn btn-ghost btn-sm p-1" onClick={onClose}><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 space-y-3">
          <div>
            <label className="form-label">Carrier Name</label>
            <input className="form-input" placeholder="Maersk" value={form.carrier_name}
              onChange={e => setForm(f => ({ ...f, carrier_name: e.target.value }))} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="form-label">Charge Type</label>
              <select className="form-input" value={form.charge_type}
                onChange={e => setForm(f => ({ ...f, charge_type: e.target.value }))}>
                {CHARGE_TYPES.map(c => <option key={c} value={c}>{c.replace(/_/g," ")}</option>)}
              </select>
            </div>
            <div>
              <label className="form-label">Unit</label>
              <select className="form-input" value={form.unit}
                onChange={e => setForm(f => ({ ...f, unit: e.target.value }))}>
                {["per_container","per_kg","per_cbm","per_shipment","flat"].map(u =>
                  <option key={u} value={u}>{u.replace(/_/g," ")}</option>)}
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="form-label">Agreed Rate</label>
              <input className="form-input font-mono" type="number" step="0.01" placeholder="1850.00"
                value={form.agreed_rate} onChange={e => setForm(f => ({ ...f, agreed_rate: e.target.value }))} />
            </div>
            <div>
              <label className="form-label">Currency</label>
              <select className="form-input" value={form.currency}
                onChange={e => setForm(f => ({ ...f, currency: e.target.value }))}>
                {["USD","ZAR","EUR"].map(c => <option key={c}>{c}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="form-label">Lane (optional)</label>
            <input className="form-input font-mono" placeholder="CNSHA-ZADUR — leave blank for all lanes"
              value={form.lane} onChange={e => setForm(f => ({ ...f, lane: e.target.value }))} />
          </div>
          <div className="flex gap-2 pt-2">
            <button className="btn btn-secondary flex-1" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary flex-1" onClick={() => mut.mutate()}
              disabled={!form.carrier_name || !form.agreed_rate || mut.isPending}>
              {mut.isPending ? "Saving…" : "Save Rate Card"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CarrierAuditPage() {
  const qc = useQueryClient();
  const [showRateCardModal, setShowRateCardModal] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);

  const { data: summary }   = useQuery({ queryKey: ["carrier-summary"], queryFn: carrierApi.summary, refetchInterval: 30000 });
  const { data: auditsData, isLoading: auditsLoading } = useQuery({ queryKey: ["carrier-audits"], queryFn: () => carrierApi.audits() });
  const { data: rateCards } = useQuery({ queryKey: ["rate-cards"], queryFn: carrierApi.rateCards });

  const deleteRateCardMut = useMutation({
    mutationFn: (id: string) => carrierApi.deleteRateCard(id),
    onSuccess: () => { toast.success("Rate card removed"); qc.invalidateQueries({ queryKey: ["rate-cards"] }); },
  });

  const onDrop = useCallback(async (files: File[]) => {
    for (const file of files) {
      const toastId = toast.loading(`Auditing ${file.name}…`);
      try {
        const result = await uploadInvoice(file);
        setLastResult(result);
        qc.invalidateQueries({ queryKey: ["carrier-audits", "carrier-summary"] });

        if (result.status === "overcharge_detected") {
          toast.error(
            `${result.overcharge_count} overcharge${result.overcharge_count !== 1 ? "s" : ""} found — R${Math.abs(result.variance_zar || 0).toLocaleString("en-ZA")} disputed`,
            { id: toastId, duration: 6000 }
          );
        } else if (result.status === "no_rate_card") {
          toast(`No rate card for ${result.carrier_name} — add one to enable auditing`, { id: toastId, icon: "ℹ️" });
        } else {
          toast.success(`${result.carrier_name} invoice is clean — no overcharges`, { id: toastId });
        }
      } catch (err: any) {
        toast.error(err.message || "Audit failed", { id: toastId });
      }
    }
  }, [qc]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"], "image/png": [".png"], "image/jpeg": [".jpg",".jpeg"] },
    maxSize: 25 * 1024 * 1024,
  });

  const audits = auditsData?.data || [];

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[{ label: "Carrier Invoice Auditor" }]}
        actions={
          <button className="btn btn-secondary btn-sm" onClick={() => qc.invalidateQueries()}>
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        }
      />

      <div className="p-6 space-y-6">

        {/* Intro */}
        <div className="card p-4 bg-info-bg border-info-border">
          <p className="text-xs text-info-DEFAULT leading-relaxed">
            <strong>The other side of the P&L.</strong> WiseLayer stops you overpaying CargoWise.
            CarrierInvoice Auditor stops carriers overcharging you. Upload an invoice from
            Maersk, MSC, or any carrier — CargoIQ extracts every line item and checks it
            against your negotiated rates. Mismatches generate a printable dispute notice.
          </p>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="section-label">Invoices Audited</span>
              <Receipt className="w-4 h-4 text-text-tertiary" />
            </div>
            <div className="text-3xl font-mono font-medium">{summary?.invoices_audited ?? "—"}</div>
          </div>
          <div className="card p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="section-label">Overcharges Found</span>
              <AlertTriangle className="w-4 h-4 text-error-DEFAULT" />
            </div>
            <div className="text-3xl font-mono font-medium text-error-DEFAULT">{summary?.overcharges_found ?? "—"}</div>
          </div>
          <div className="card p-5">
            <div className="flex items-center justify-between mb-2">
              <span className="section-label">Clean Invoices</span>
              <CheckCircle className="w-4 h-4 text-success-DEFAULT" />
            </div>
            <div className="text-3xl font-mono font-medium text-success-DEFAULT">{summary?.clean_invoices ?? "—"}</div>
          </div>
          <div className={cn("card p-5", (summary?.total_overcharge_zar || 0) > 0 && "border-error-border bg-error-bg/20")}>
            <div className="flex items-center justify-between mb-2">
              <span className="section-label">Total Disputed</span>
              <TrendingDown className="w-4 h-4 text-error-DEFAULT" />
            </div>
            <div className="text-3xl font-mono font-medium text-error-DEFAULT">
              R{(summary?.total_overcharge_zar || 0).toLocaleString("en-ZA")}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Left: upload + rate cards */}
          <div className="space-y-5">

            {/* Upload zone */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Upload className="w-4 h-4 text-text-tertiary" />
                  <h3 className="text-xs font-semibold">Upload Carrier Invoice</h3>
                </div>
              </div>
              <div className="p-4">
                <div
                  {...getRootProps()}
                  className={cn(
                    "border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors",
                    isDragActive ? "border-accent bg-accent/5" : "border-border hover:border-accent/50"
                  )}
                >
                  <input {...getInputProps()} />
                  <FileText className="w-8 h-8 text-text-tertiary mx-auto mb-2 stroke-[1.5]" />
                  <p className="text-xs font-medium text-text-secondary">
                    Drag & drop a carrier invoice PDF
                  </p>
                  <p className="text-2xs text-text-tertiary mt-1">or click to browse · max 25MB</p>
                </div>
              </div>
            </div>

            {/* Rate cards */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-text-tertiary" />
                  <h3 className="text-xs font-semibold">
                    Rate Cards
                    <span className="ml-2 text-2xs font-mono text-text-tertiary">{rateCards?.length || 0}</span>
                  </h3>
                </div>
                <button className="btn btn-ghost btn-sm" onClick={() => setShowRateCardModal(true)}>
                  <Plus className="w-3.5 h-3.5" /> Add
                </button>
              </div>
              {!rateCards?.length ? (
                <div className="p-6 text-center">
                  <FileX className="w-8 h-8 text-text-tertiary mx-auto mb-2 stroke-[1.5]" />
                  <p className="text-xs text-text-secondary">No rate cards yet</p>
                  <p className="text-2xs text-text-tertiary mt-1">
                    Add your negotiated rates per carrier to enable auditing
                  </p>
                </div>
              ) : (
                <div className="divide-y divide-border max-h-80 overflow-y-auto">
                  {rateCards.map((rc: any) => (
                    <div key={rc.id} className="flex items-center justify-between px-4 py-2.5">
                      <div>
                        <p className="text-xs font-medium text-text-primary">
                          {rc.carrier_name} · {rc.charge_type.replace(/_/g," ")}
                        </p>
                        <p className="text-2xs text-text-tertiary font-mono">
                          {rc.currency} {Number(rc.agreed_rate).toLocaleString()} / {rc.unit.replace(/_/g," ")}
                          {rc.lane ? ` · ${rc.lane}` : ""}
                        </p>
                      </div>
                      <button className="btn btn-ghost btn-sm p-1 text-error-DEFAULT"
                        onClick={() => deleteRateCardMut.mutate(rc.id)}>
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right: audits table */}
          <div className="xl:col-span-2">
            <div className="card overflow-hidden">
              <div className="card-header">
                <h3 className="text-xs font-semibold">Audit History</h3>
              </div>
              {auditsLoading ? (
                <div className="p-4 space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-10" />)}</div>
              ) : audits.length === 0 ? (
                <div className="p-10 text-center">
                  <Receipt className="w-10 h-10 text-text-tertiary mx-auto mb-3 stroke-[1.5]" />
                  <p className="text-sm font-medium text-text-secondary">No carrier invoices audited yet</p>
                  <p className="text-xs text-text-tertiary mt-1">Upload one to find your first overcharge</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table>
                    <thead><tr>
                      <th>Carrier</th><th>Invoice #</th><th>Total</th>
                      <th>Variance</th><th>Status</th><th></th>
                    </tr></thead>
                    <tbody>
                      {audits.map((a: any) => (
                        <tr key={a.id}>
                          <td className="text-xs font-medium">{a.carrier_name}</td>
                          <td className="font-mono text-2xs text-text-tertiary">{a.invoice_number || "—"}</td>
                          <td className="font-mono text-xs">
                            {a.invoice_currency} {Number(a.invoice_total || 0).toLocaleString()}
                          </td>
                          <td className="font-mono text-xs">
                            {a.status === "overcharge_detected" && a.variance_zar
                              ? <span className="text-error-DEFAULT font-medium">R{Number(a.variance_zar).toLocaleString("en-ZA")}</span>
                              : "—"}
                          </td>
                          <td><StatusBadge status={a.status} /></td>
                          <td>
                            {a.status === "overcharge_detected" && (
                              <a
                                href={`${API_BASE}/api/v1/carrier-audit/${a.id}/dispute`}
                                target="_blank"
                                className="text-2xs text-accent hover:underline font-medium"
                              >
                                Dispute →
                              </a>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {showRateCardModal && (
        <RateCardModal
          onClose={() => setShowRateCardModal(false)}
          onSaved={() => qc.invalidateQueries({ queryKey: ["rate-cards"] })}
        />
      )}
    </div>
  );
}
