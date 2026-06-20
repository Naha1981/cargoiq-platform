"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Shield, Globe, Ship, Container, Activity, Play,
  RefreshCw, CheckCircle, Clock, AlertTriangle, XCircle,
  Database, Key, TrendingDown
} from "lucide-react";
import { TopNav }    from "@/components/layout/TopNav";
import { Skeleton }  from "@/components/ui/LoadingSkeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { cn, formatDateTime } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import toast from "react-hot-toast";

const portalsApi = {
  stats:     () => apiClient.get("/portals/stats"),
  jobs:      (portal?: string) => apiClient.get(`/portals/jobs${portal ? `?portal=${portal}` : ""}`),
  containers: () => apiClient.get("/portals/containers"),
  trigger:   (body: any) => apiClient.post("/portals/trigger", body),
  bulkTrack: (cns: string[]) => apiClient.post("/portals/containers/bulk-track", cns),
  bulkRLA:   (codes: string[]) => apiClient.post("/portals/rla/bulk-check", codes),
};

const PORTAL_META: Record<string, { label: string; color: string; icon: any }> = {
  sars:      { label: "SARS eFiling",     color: "text-error-DEFAULT",   icon: Shield   },
  transnet:  { label: "Transnet / TPT",   color: "text-info-DEFAULT",    icon: Ship     },
  shipping:  { label: "Shipping Lines",   color: "text-accent",          icon: Container},
};

const JOB_ACTIONS = [
  { key: "portal:sars:rla_check",       label: "Check RLA Status",         portal: "sars",     params: ["importerCode"] },
  { key: "portal:sars:release_check",   label: "Check Customs Release",    portal: "sars",     params: ["mrn"] },
  { key: "portal:sars:submit_sad500",   label: "Submit SAD500",            portal: "sars",     params: [] },
  { key: "portal:transnet:container",   label: "Track Container (Navis)",  portal: "transnet", params: ["containerNumber"] },
  { key: "portal:transnet:demurrage",   label: "Calculate Demurrage",      portal: "transnet", params: ["containerNumber"] },
  { key: "portal:transnet:vessel_eta",  label: "Check Vessel ETA",         portal: "transnet", params: ["vesselName"] },
  { key: "portal:shipping:track",       label: "Track Shipping Container", portal: "shipping", params: ["containerNumber"] },
  { key: "portal:shipping:release",     label: "Check Container Release",  portal: "shipping", params: ["containerNumber"] },
];

function StatCard({ label, value, sub, icon: Icon, color = "text-text-primary", alert = false }: any) {
  return (
    <div className={cn("card p-5", alert && "border-error-border bg-error-bg/20")}>
      <div className="flex items-center justify-between mb-3">
        <span className="section-label">{label}</span>
        <Icon className={cn("w-4 h-4", color)} />
      </div>
      <div className={cn("text-3xl font-mono font-medium", color)}>{value}</div>
      {sub && <p className="text-2xs text-text-tertiary mt-1">{sub}</p>}
    </div>
  );
}

function JobRow({ job }: { job: any }) {
  const meta = PORTAL_META[job.portal] || { label: job.portal, color: "text-text-secondary", icon: Globe };
  const Icon = meta.icon;
  return (
    <tr>
      <td>
        <div className="flex items-center gap-2">
          <Icon className={cn("w-3.5 h-3.5", meta.color)} />
          <span className="text-xs font-medium">{meta.label}</span>
        </div>
      </td>
      <td><span className="font-mono text-2xs text-text-secondary">{job.job_type.split(":").slice(2).join(":")}</span></td>
      <td><StatusBadge value={job.status} variant="status" /></td>
      <td className="font-mono text-2xs">{job.duration_ms ? `${(job.duration_ms/1000).toFixed(1)}s` : "—"}</td>
      <td className="font-mono text-2xs text-text-tertiary">{formatDateTime(job.created_at)}</td>
      <td>
        {job.error && <span className="text-2xs text-error-DEFAULT truncate max-w-[160px] block">{job.error}</span>}
        {job.result_data?.rlaStatus && (
          <span className={cn("badge", job.result_data.rlaStatus === "active" ? "badge-pass" : "badge-fail")}>
            {job.result_data.rlaStatus.toUpperCase()}
          </span>
        )}
        {job.result_data?.demurrageExposureZAR > 0 && (
          <span className="text-2xs text-error-DEFAULT font-medium">
            R{job.result_data.demurrageExposureZAR.toLocaleString("en-ZA")}
          </span>
        )}
      </td>
    </tr>
  );
}

export default function PortalsPage() {
  const qc = useQueryClient();
  const [activePortal, setActivePortal] = useState<string>("");
  const [triggerModal, setTriggerModal] = useState<any>(null);
  const [paramValues,  setParamValues]  = useState<Record<string,string>>({});
  const [bulkInput,    setBulkInput]    = useState("");

  const { data: stats,      isLoading: statsLoading }  = useQuery({ queryKey: ["portal-stats"],      queryFn: portalsApi.stats,      refetchInterval: 30000 });
  const { data: jobsData,   isLoading: jobsLoading }   = useQuery({ queryKey: ["portal-jobs", activePortal], queryFn: () => portalsApi.jobs(activePortal || undefined), refetchInterval: 10000 });
  const { data: containers, isLoading: containersLoading } = useQuery({ queryKey: ["containers"], queryFn: portalsApi.containers, refetchInterval: 30000 });

  const triggerMut = useMutation({
    mutationFn: portalsApi.trigger,
    onSuccess: (d) => {
      toast.success(`Job queued: ${d.job_type}`);
      setTriggerModal(null);
      setParamValues({});
      qc.invalidateQueries({ queryKey: ["portal-jobs"] });
      qc.invalidateQueries({ queryKey: ["portal-stats"] });
    },
    onError: (e: any) => toast.error(e.message || "Trigger failed"),
  });

  const bulkTrackMut = useMutation({
    mutationFn: (cns: string[]) => portalsApi.bulkTrack(cns),
    onSuccess: (d) => { toast.success(`${d.queued} tracking jobs queued`); setBulkInput(""); qc.invalidateQueries({ queryKey: ["portal-jobs"] }); },
  });

  const bulkRLAMut = useMutation({
    mutationFn: (codes: string[]) => portalsApi.bulkRLA(codes),
    onSuccess: (d) => { toast.success(`${d.queued} RLA checks queued`); setBulkInput(""); qc.invalidateQueries({ queryKey: ["portal-jobs"] }); },
  });

  const handleTrigger = () => {
    if (!triggerModal) return;
    triggerMut.mutate({ job_type: triggerModal.key, params: paramValues });
  };

  const jobs = jobsData?.data || [];
  const conts = (containers || []) as any[];

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[{ label: "Portal Automation" }]}
        actions={
          <button className="btn btn-secondary btn-sm" onClick={() => qc.invalidateQueries()}>
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        }
      />

      <div className="p-6 space-y-6">

        {/* Stats row */}
        {statsLoading ? (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-28" />)}
          </div>
        ) : stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard label="Total Portal Jobs"    value={stats.total_jobs}                    icon={Activity}   color="text-text-primary" sub="All time" />
            <StatCard label="Containers Tracked"   value={stats.containers_tracked}            icon={Container}  color="text-info-DEFAULT" sub={`${stats.containers_released} released`} />
            <StatCard label="Unreleased"           value={stats.containers_unreleased}         icon={Clock}      color={stats.containers_unreleased > 0 ? "text-warning-DEFAULT" : "text-text-primary"} />
            <StatCard
              label="Demurrage Exposure"
              value={stats.total_demurrage_exposure_zar > 0 ? `R${Math.round(stats.total_demurrage_exposure_zar).toLocaleString("en-ZA")}` : "R0"}
              icon={TrendingDown}
              color={stats.total_demurrage_exposure_zar > 0 ? "text-error-DEFAULT" : "text-success-DEFAULT"}
              alert={stats.total_demurrage_exposure_zar > 50000}
              sub="Active demurrage risk"
            />
          </div>
        )}

        {/* Two-column layout */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Left: trigger panel + quick actions */}
          <div className="space-y-5">

            {/* Quick trigger */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Play className="w-4 h-4 text-text-tertiary" />
                  <h3 className="text-xs font-semibold">Trigger Portal Job</h3>
                </div>
              </div>
              <div className="divide-y divide-border">
                {Object.entries(PORTAL_META).map(([key, meta]) => {
                  const Icon = meta.icon;
                  const actions = JOB_ACTIONS.filter(a => a.portal === key);
                  return (
                    <div key={key} className="p-4">
                      <div className="flex items-center gap-2 mb-3">
                        <Icon className={cn("w-3.5 h-3.5", meta.color)} />
                        <span className="text-xs font-semibold text-text-primary">{meta.label}</span>
                      </div>
                      <div className="space-y-1.5">
                        {actions.map(action => (
                          <button
                            key={action.key}
                            onClick={() => { setTriggerModal(action); setParamValues({}); }}
                            className="w-full flex items-center justify-between px-3 py-2 text-xs rounded border border-border hover:bg-subtle hover:border-accent/50 transition-colors text-left"
                          >
                            <span>{action.label}</span>
                            <Play className="w-3 h-3 text-text-tertiary flex-shrink-0" />
                          </button>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Bulk operations */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <h3 className="text-xs font-semibold">Bulk Operations</h3>
              </div>
              <div className="p-4 space-y-3">
                <div>
                  <label className="form-label">Container numbers or importer codes</label>
                  <textarea
                    className="form-input h-24 text-xs font-mono resize-none"
                    placeholder={"MSCU1234567\nMAEU9876543\nHLCU1111111"}
                    value={bulkInput}
                    onChange={e => setBulkInput(e.target.value)}
                  />
                  <p className="text-2xs text-text-tertiary mt-1">One per line. Max 20.</p>
                </div>
                <div className="flex gap-2">
                  <button
                    className="btn btn-secondary btn-sm flex-1"
                    disabled={!bulkInput.trim() || bulkTrackMut.isPending}
                    onClick={() => {
                      const cns = bulkInput.split("\n").map(s => s.trim()).filter(Boolean);
                      bulkTrackMut.mutate(cns);
                    }}
                  >
                    <Ship className="w-3.5 h-3.5" />
                    Track Containers
                  </button>
                  <button
                    className="btn btn-secondary btn-sm flex-1"
                    disabled={!bulkInput.trim() || bulkRLAMut.isPending}
                    onClick={() => {
                      const codes = bulkInput.split("\n").map(s => s.trim()).filter(Boolean);
                      bulkRLAMut.mutate(codes);
                    }}
                  >
                    <Shield className="w-3.5 h-3.5" />
                    Check RLA
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Right: jobs table + containers */}
          <div className="xl:col-span-2 space-y-5">

            {/* Filter tabs */}
            <div className="flex gap-1">
              {[["","All Portals"], ["sars","SARS"], ["transnet","Transnet"], ["shipping","Shipping"]].map(([k,l]) => (
                <button key={k} onClick={() => setActivePortal(k)}
                  className={cn("px-3 py-1.5 text-xs rounded transition-colors",
                    activePortal === k ? "bg-accent text-text-inverse" : "bg-surface border border-border text-text-secondary hover:bg-subtle"
                  )}>
                  {l}
                </button>
              ))}
            </div>

            {/* Jobs table */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-text-tertiary" />
                  <h3 className="text-xs font-semibold">Recent Jobs</h3>
                </div>
              </div>
              {jobsLoading ? (
                <div className="p-4 space-y-2">{[1,2,3].map(i => <Skeleton key={i} className="h-8" />)}</div>
              ) : jobs.length === 0 ? (
                <div className="p-8 text-center text-xs text-text-tertiary">No portal jobs yet. Trigger one from the panel.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table>
                    <thead><tr>
                      <th>Portal</th><th>Action</th><th>Status</th>
                      <th>Duration</th><th>Triggered</th><th>Result</th>
                    </tr></thead>
                    <tbody>{jobs.slice(0, 30).map((j: any) => <JobRow key={j.id} job={j} />)}</tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Containers at risk */}
            {conts.some(c => !c.is_released) && (
              <div className="card overflow-hidden">
                <div className="card-header">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-warning-DEFAULT" />
                    <h3 className="text-xs font-semibold">Containers Requiring Attention</h3>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table>
                    <thead><tr>
                      <th>Container</th><th>Line</th><th>Status</th>
                      <th>Location</th><th>ETA</th><th>Demurrage Risk</th>
                    </tr></thead>
                    <tbody>
                      {conts.filter(c => !c.is_released).map((c: any) => (
                        <tr key={c.id}>
                          <td className="font-mono text-xs font-medium text-accent">{c.container_number}</td>
                          <td className="text-xs">{c.shipping_line || "—"}</td>
                          <td><span className="badge badge-hold">{(c.status || "UNKNOWN").toUpperCase()}</span></td>
                          <td className="text-xs">{c.location || "—"}</td>
                          <td className="font-mono text-2xs">{c.eta ? new Date(c.eta).toLocaleDateString("en-ZA") : "—"}</td>
                          <td>
                            {(c.demurrage_zar || 0) > 0
                              ? <span className="text-xs font-mono text-error-DEFAULT font-medium">R{c.demurrage_zar?.toLocaleString("en-ZA")}</span>
                              : <span className="text-xs text-success-DEFAULT">Clear</span>
                            }
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Trigger modal */}
      {triggerModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="card w-full max-w-md">
            <div className="card-header">
              <h3 className="text-sm font-semibold">{triggerModal.label}</h3>
              <button className="btn btn-ghost btn-sm p-1" onClick={() => setTriggerModal(null)}>
                <XCircle className="w-4 h-4" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {triggerModal.params.map((p: string) => (
                <div key={p}>
                  <label className="form-label capitalize">{p.replace(/([A-Z])/g, " $1")}</label>
                  <input
                    className="form-input font-mono"
                    placeholder={p === "containerNumber" ? "MSCU1234567" : p === "importerCode" ? "ZA12345678" : p === "mrn" ? "SA-2026-001234" : ""}
                    value={paramValues[p] || ""}
                    onChange={e => setParamValues(v => ({ ...v, [p]: e.target.value }))}
                  />
                </div>
              ))}
              {triggerModal.params.length === 0 && (
                <p className="text-xs text-text-secondary">No parameters required. Click Execute to trigger.</p>
              )}
              <div className="flex gap-2 pt-2">
                <button className="btn btn-secondary flex-1" onClick={() => setTriggerModal(null)}>Cancel</button>
                <button
                  className="btn btn-primary flex-1"
                  onClick={handleTrigger}
                  disabled={triggerMut.isPending}
                >
                  {triggerMut.isPending ? "Queuing…" : "Execute"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
