"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Search, Play, AlertTriangle, CheckCircle, Clock,
  Link2, Copy, Check, FileWarning, TrendingUp, History
} from "lucide-react";
import { TopNav }   from "@/components/layout/TopNav";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import toast from "react-hot-toast";

const shadowApi = {
  list:    () => apiClient.get("/audit/shadow"),
  trigger: (days_back: number, max_shipments: number) =>
    apiClient.post(`/audit/shadow?days_back=${days_back}&max_shipments=${max_shipments}`, {}),
  share:   (id: string) => apiClient.post(`/audit/shadow/${id}/share`, {}),
};

function Stat({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="card p-4">
      <div className="section-label mb-1">{label}</div>
      <div className={cn("text-2xl font-mono font-medium", color)}>{value}</div>
    </div>
  );
}

function ShareLinkButton({ auditId }: { auditId: string }) {
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const mut = useMutation({
    mutationFn: () => shadowApi.share(auditId),
    onSuccess: (d) => {
      const url = `${window.location.origin}${d.share_path}`;
      setLink(url);
    },
    onError: () => toast.error("Could not generate share link"),
  });

  if (link) {
    return (
      <div className="flex items-center gap-2">
        <input
          readOnly
          value={link}
          className="form-input font-mono text-2xs flex-1"
          onClick={(e) => (e.target as HTMLInputElement).select()}
        />
        <button
          className="btn btn-secondary btn-sm"
          onClick={() => {
            navigator.clipboard.writeText(link);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
    );
  }

  return (
    <button className="btn btn-secondary btn-sm" onClick={() => mut.mutate()} disabled={mut.isPending}>
      <Link2 className="w-3.5 h-3.5" />
      {mut.isPending ? "Generating…" : "Generate Proof Page Link"}
    </button>
  );
}

export default function ShadowAuditPage() {
  const qc = useQueryClient();
  const [daysBack, setDaysBack] = useState(30);
  const [maxShipments, setMaxShipments] = useState(100);
  const [latestResult, setLatestResult] = useState<any>(null);

  const { data: history, isLoading: historyLoading } = useQuery({
    queryKey: ["shadow-audits"],
    queryFn: shadowApi.list,
  });

  const triggerMut = useMutation({
    mutationFn: () => shadowApi.trigger(daysBack, maxShipments),
    onSuccess: (result) => {
      setLatestResult(result);
      qc.invalidateQueries({ queryKey: ["shadow-audits"] });
      qc.invalidateQueries({ queryKey: ["onboarding-status"] });
      if (result.status === "empty") {
        toast("No completed shipments found in this period yet", { icon: "ℹ️" });
      } else {
        toast.success(`Audit complete — R${(result.summary?.total_value_identified_zar || 0).toLocaleString("en-ZA")} identified`);
      }
    },
    onError: (e: any) => toast.error(e.message || "Audit failed"),
  });

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[{ label: "Shadow Audit" }]} />

      <div className="p-6 space-y-6 max-w-4xl">

        {/* Intro */}
        <div className="card p-4 bg-info-bg border-info-border">
          <p className="text-xs text-info-DEFAULT leading-relaxed">
            <strong>The Shadow Audit is your zero-risk proof.</strong> It runs the
            Compliance Shield over historical shipments your team has already
            processed — no changes to live operations, no commitment. Whatever it
            finds, you can show the prospect with one link, generated below.
          </p>
        </div>

        {/* Trigger */}
        <div className="card overflow-hidden">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Search className="w-4 h-4 text-text-tertiary" />
              <h3 className="text-xs font-semibold">Run a New Shadow Audit</h3>
            </div>
          </div>
          <div className="p-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="form-label">Look back (days)</label>
                <input
                  type="number" min={7} max={90} className="form-input font-mono"
                  value={daysBack} onChange={e => setDaysBack(parseInt(e.target.value) || 30)}
                />
              </div>
              <div>
                <label className="form-label">Max shipments</label>
                <input
                  type="number" min={10} max={500} className="form-input font-mono"
                  value={maxShipments} onChange={e => setMaxShipments(parseInt(e.target.value) || 100)}
                />
              </div>
            </div>
            <button
              className="btn btn-primary"
              onClick={() => triggerMut.mutate()}
              disabled={triggerMut.isPending}
            >
              <Play className="w-3.5 h-3.5" />
              {triggerMut.isPending ? "Auditing…" : "Run Shadow Audit"}
            </button>
          </div>
        </div>

        {/* Latest result */}
        {latestResult && latestResult.status === "completed" && (
          <div className="card overflow-hidden border-accent-border">
            <div className="card-header">
              <div className="flex items-center gap-2">
                <FileWarning className="w-4 h-4 text-accent" />
                <h3 className="text-xs font-semibold">Latest Audit Result</h3>
              </div>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Shipments Audited" value={latestResult.summary.shipments_audited} />
                <Stat label="Errors Found" value={latestResult.summary.errors_found} color="text-error-DEFAULT" />
                <Stat label="Pass Rate" value={`${latestResult.summary.pass_rate_pct}%`} color="text-success-DEFAULT" />
                <Stat
                  label="Total Value Identified"
                  value={`R${latestResult.summary.total_value_identified_zar.toLocaleString("en-ZA")}`}
                  color="text-accent"
                />
              </div>

              {latestResult.findings?.length > 0 && (
                <div className="border border-border rounded overflow-hidden">
                  <table>
                    <thead><tr>
                      <th>Reference</th><th>Issue</th><th>Risk</th>
                    </tr></thead>
                    <tbody>
                      {latestResult.findings.slice(0, 10).map((f: any) => (
                        <tr key={f.shipment_id}>
                          <td className="font-mono text-xs">{f.reference}</td>
                          <td className="text-xs">
                            {f.modules_failed.map((m: any) => m.module.replace(/_/g," ")).join(", ")}
                          </td>
                          <td className="font-mono text-xs text-error-DEFAULT">
                            R{f.total_penalty_zar.toLocaleString("en-ZA")}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              <div className="pt-2 border-t border-border">
                <p className="text-2xs text-text-tertiary mb-2">
                  Share this audit with the prospect — no login required:
                </p>
                <ShareLinkButton auditId={latestResult.audit_id} />
              </div>
            </div>
          </div>
        )}

        {/* History */}
        <div className="card overflow-hidden">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-text-tertiary" />
              <h3 className="text-xs font-semibold">Audit History</h3>
            </div>
          </div>
          {historyLoading ? (
            <div className="p-4 space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-10" />)}</div>
          ) : !history?.length ? (
            <div className="p-10 text-center">
              <Search className="w-10 h-10 text-text-tertiary mx-auto mb-3 stroke-[1.5]" />
              <p className="text-sm font-medium text-text-secondary">No audits run yet</p>
              <p className="text-xs text-text-tertiary mt-1">Run your first Shadow Audit above</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table>
                <thead><tr>
                  <th>Date</th><th>Shipments</th><th>Errors</th>
                  <th>Pass Rate</th><th>Value Identified</th><th></th>
                </tr></thead>
                <tbody>
                  {history.map((a: any) => (
                    <tr key={a.id}>
                      <td className="font-mono text-2xs text-text-tertiary">
                        {new Date(a.created_at).toLocaleDateString("en-ZA")}
                      </td>
                      <td className="text-xs">{a.summary?.shipments_audited ?? "—"}</td>
                      <td className="text-xs text-error-DEFAULT">{a.summary?.errors_found ?? "—"}</td>
                      <td className="text-xs text-success-DEFAULT">{a.summary?.pass_rate_pct ?? "—"}%</td>
                      <td className="font-mono text-xs text-accent">
                        R{(a.summary?.total_value_identified_zar ?? 0).toLocaleString("en-ZA")}
                      </td>
                      <td>
                        <ShareLinkButton auditId={a.id} />
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
  );
}
