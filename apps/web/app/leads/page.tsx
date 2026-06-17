"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Users, TrendingUp, Copy, Check, ChevronRight,
  RefreshCw, ExternalLink, Circle, CheckCircle2
} from "lucide-react";
import { TopNav }    from "@/components/layout/TopNav";
import { Skeleton }  from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import toast from "react-hot-toast";

const leadsApi = {
  list:    (status?: string) => apiClient.get(`/leads/${status ? `?status=${status}` : ""}`),
  summary: () => apiClient.get("/leads/pipeline-summary"),
  status:  (id: string, status: string, notes?: string) =>
    apiClient.patch(`/leads/${id}/status`, { status, notes }),
};

const STAGES = [
  { key: "new",           label: "New",           color: "bg-slate-500" },
  { key: "messaged",      label: "Messaged",       color: "bg-blue-500" },
  { key: "replied",       label: "Replied",        color: "bg-purple-500" },
  { key: "call_booked",   label: "Call Booked",    color: "bg-amber-500" },
  { key: "audit_running", label: "Audit Running",  color: "bg-orange-500" },
  { key: "proposal_sent", label: "Proposal Sent",  color: "bg-cyan-500" },
  { key: "won",           label: "Won ✓",          color: "bg-emerald-500" },
  { key: "lost",          label: "Lost",           color: "bg-red-500" },
];

const TYPE_LABELS: Record<string, string> = {
  "3pl_fleet":            "3PL / Fleet",
  "importer_wholesaler":  "Importer",
  "cross_border_trucker": "Cross-Border",
  "clearing_agent":       "Clearing Agent",
  "other":                "Other",
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      className="btn btn-ghost btn-sm p-1.5"
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      title="Copy DM to clipboard"
    >
      {copied ? <Check className="w-3.5 h-3.5 text-success-DEFAULT" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

function StatusPill({ status }: { status: string }) {
  const stage = STAGES.find(s => s.key === status);
  return (
    <span className={cn(
      "inline-flex items-center px-2 py-0.5 rounded text-2xs font-semibold text-white",
      stage?.color || "bg-slate-600"
    )}>
      {stage?.label || status}
    </span>
  );
}

function LeadCard({ lead, onStatusChange }: { lead: any; onStatusChange: () => void }) {
  const [expanded, setExpanded]   = useState(false);
  const [nextStatus, setNextStatus] = useState("");
  const qc = useQueryClient();

  const statusMut = useMutation({
    mutationFn: () => leadsApi.status(lead.id, nextStatus),
    onSuccess: () => {
      toast.success(`${lead.company_name} → ${nextStatus}`);
      qc.invalidateQueries({ queryKey: ["leads"] });
      qc.invalidateQueries({ queryKey: ["leads-summary"] });
      setNextStatus("");
      onStatusChange();
    },
    onError: (e: any) => toast.error(e.message || "Update failed"),
  });

  const pain = lead.pain_estimate_zar_high
    ? `R${(lead.pain_estimate_zar_low || 0).toLocaleString("en-ZA")}–R${lead.pain_estimate_zar_high.toLocaleString("en-ZA")}/mo`
    : null;

  return (
    <div className="card overflow-hidden">
      <div
        className="flex items-start gap-3 px-4 py-3 cursor-pointer hover:bg-subtle transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-semibold text-text-primary">{lead.company_name}</span>
            {lead.company_type && (
              <span className="text-2xs text-text-tertiary border border-border rounded px-1.5 py-0.5">
                {TYPE_LABELS[lead.company_type] || lead.company_type}
              </span>
            )}
            <StatusPill status={lead.status} />
          </div>
          <div className="flex items-center gap-3 mt-1 flex-wrap">
            {lead.contact_name && (
              <span className="text-xs text-text-secondary">{lead.contact_name}</span>
            )}
            {lead.location && (
              <span className="text-xs text-text-tertiary">{lead.location}</span>
            )}
            {pain && (
              <span className="text-xs text-error-DEFAULT font-mono font-medium">{pain}</span>
            )}
          </div>
        </div>
        <ChevronRight className={cn("w-4 h-4 text-text-tertiary flex-shrink-0 mt-0.5 transition-transform", expanded && "rotate-90")} />
      </div>

      {expanded && (
        <div className="border-t border-border px-4 py-4 space-y-4">
          {/* Pain & modules */}
          {lead.primary_pain && (
            <div>
              <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-1">Primary Pain</p>
              <p className="text-xs text-text-secondary">{lead.primary_pain}</p>
            </div>
          )}
          {lead.cargoiq_modules?.length > 0 && (
            <div>
              <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-wider mb-1">CargoIQ Modules</p>
              <div className="flex flex-wrap gap-1.5">
                {lead.cargoiq_modules.map((m: string) => (
                  <span key={m} className="text-2xs bg-accent/10 text-accent border border-accent/20 rounded px-2 py-0.5">
                    {m.replace(/_/g, " ")}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* DM draft */}
          {lead.dm_draft && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <p className="text-2xs font-semibold text-text-tertiary uppercase tracking-wider">LinkedIn DM</p>
                <CopyButton text={lead.dm_draft} />
              </div>
              <pre className="text-xs text-text-secondary bg-subtle rounded p-3 whitespace-pre-wrap font-sans leading-relaxed max-h-48 overflow-y-auto">
                {lead.dm_draft}
              </pre>
            </div>
          )}

          {/* Links */}
          <div className="flex gap-3 flex-wrap">
            {lead.linkedin_url && (
              <a href={lead.linkedin_url} target="_blank"
                className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
                <ExternalLink className="w-3 h-3" /> LinkedIn
              </a>
            )}
            {lead.company_website && (
              <a href={lead.company_website} target="_blank"
                className="inline-flex items-center gap-1 text-xs text-accent hover:underline">
                <ExternalLink className="w-3 h-3" /> Website
              </a>
            )}
          </div>

          {/* Status update */}
          <div className="flex items-center gap-2 pt-1">
            <select
              className="form-input text-xs py-1.5 flex-1"
              value={nextStatus}
              onChange={e => setNextStatus(e.target.value)}
            >
              <option value="">Move to stage…</option>
              {STAGES.filter(s => s.key !== lead.status).map(s => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
            <button
              className="btn btn-primary btn-sm"
              disabled={!nextStatus || statusMut.isPending}
              onClick={() => statusMut.mutate()}
            >
              {statusMut.isPending ? "Saving…" : "Update"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LeadsPage() {
  const [activeStatus, setActiveStatus] = useState<string>("");
  const qc = useQueryClient();

  const { data: summary } = useQuery({
    queryKey: ["leads-summary"],
    queryFn:  leadsApi.summary,
    refetchInterval: 30000,
  });

  const { data: leadsData, isLoading } = useQuery({
    queryKey: ["leads", activeStatus],
    queryFn:  () => leadsApi.list(activeStatus || undefined),
    refetchInterval: 30000,
  });

  const leads  = leadsData?.data || [];
  const total  = summary?.total_leads || 0;
  const wonPct = summary?.conversion_rate_pct || 0;

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[{ label: "Deal Hunter — Leads CRM" }]}
        actions={
          <button className="btn btn-secondary btn-sm" onClick={() => qc.invalidateQueries()}>
            <RefreshCw className="w-3.5 h-3.5" /> Refresh
          </button>
        }
      />

      <div className="p-6 space-y-5">

        {/* Funnel summary */}
        {summary && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="section-label mb-1">Total Leads</div>
              <div className="text-3xl font-mono font-medium">{total}</div>
            </div>
            <div className="card p-4">
              <div className="section-label mb-1">Won</div>
              <div className="text-3xl font-mono font-medium text-success-DEFAULT">
                {summary.won_count}
              </div>
            </div>
            <div className="card p-4">
              <div className="section-label mb-1">Conversion Rate</div>
              <div className="text-3xl font-mono font-medium">{wonPct}%</div>
            </div>
            <div className="card p-4">
              <div className="section-label mb-1">Total Pain (High)</div>
              <div className="text-2xl font-mono font-medium text-error-DEFAULT">
                R{(summary.total_pain_zar_high || 0).toLocaleString("en-ZA")}
              </div>
              <p className="text-2xs text-text-tertiary mt-0.5">addressable/mo across all leads</p>
            </div>
          </div>
        )}

        {/* Stage filter tabs */}
        <div className="flex gap-1.5 flex-wrap">
          <button
            onClick={() => setActiveStatus("")}
            className={cn("px-3 py-1.5 text-xs rounded transition-colors",
              activeStatus === "" ? "bg-accent text-text-inverse" : "bg-surface border border-border text-text-secondary hover:bg-subtle"
            )}>
            All ({total})
          </button>
          {STAGES.slice(0, 6).map(s => (
            <button
              key={s.key}
              onClick={() => setActiveStatus(s.key)}
              className={cn("px-3 py-1.5 text-xs rounded transition-colors",
                activeStatus === s.key ? "bg-accent text-text-inverse" : "bg-surface border border-border text-text-secondary hover:bg-subtle"
              )}>
              {s.label} ({summary?.by_status?.[s.key] || 0})
            </button>
          ))}
        </div>

        {/* Pipeline note */}
        <div className="card p-3 bg-info-bg border-info-border">
          <p className="text-xs text-info-DEFAULT leading-relaxed">
            <strong>Deal Hunter runs nightly at 23:00 SAST</strong> via Base44 and generates 10 qualified leads with personalised LinkedIn DMs. 
            Before sending any DM that references "GPS proof," change it to <strong>"WhatsApp-verified timestamps"</strong> — 
            that's what CargoIQ actually uses for the Driver Check-In module (ARRIVED/DEPARTED texts). 
            The Beitbridge Fuel Theft Detector in the DMs also requires GPS hardware not yet in the stack — 
            lead with CarrierInvoice Auditor and SARS TMS Checker instead.
          </p>
        </div>

        {/* Leads list */}
        {isLoading ? (
          <div className="space-y-2">{[1,2,3,4,5].map(i => <Skeleton key={i} className="h-16" />)}</div>
        ) : leads.length === 0 ? (
          <div className="card p-10 text-center">
            <Users className="w-10 h-10 text-text-tertiary mx-auto mb-3 stroke-[1.5]" />
            <p className="text-sm font-medium text-text-secondary">
              {activeStatus ? `No leads with status "${activeStatus}"` : "No leads yet"}
            </p>
            <p className="text-xs text-text-tertiary mt-1">
              The Base44 Deal Hunter imports leads automatically each night.
              You can also POST to /api/v1/leads/batch to import manually.
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {leads.map((lead: any) => (
              <LeadCard
                key={lead.id}
                lead={lead}
                onStatusChange={() => qc.invalidateQueries({ queryKey: ["leads"] })}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
