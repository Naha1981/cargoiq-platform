"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Mail, Bot, User, Play, SkipForward, RefreshCw,
  Paperclip, CheckCircle, Clock, AlertTriangle, Zap, Power
} from "lucide-react";
import { TopNav }   from "@/components/layout/TopNav";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn, formatDateTime } from "@/lib/utils";
import { apiClient } from "@/lib/api";
import toast from "react-hot-toast";

// ── API helpers ─────────────────────────────────────────────
const inboxApi = {
  status:       () => apiClient.get("/inbox/status"),
  setMode:      (mode: string) => apiClient.post("/inbox/mode", { mode }),
  emails:       (status?: string) => apiClient.get(`/inbox/emails${status ? `?status=${status}` : ""}`),
  processEmail: (id: string) => apiClient.post(`/inbox/emails/${id}/process`, {}),
  skipEmail:    (id: string) => apiClient.post(`/inbox/emails/${id}/skip`, {}),
  start:        () => apiClient.post("/inbox/start", {}),
};

// ── Mode Toggle ─────────────────────────────────────────────
function ModeToggle({ mode, onChange, loading }: {
  mode: string; onChange: (m: string) => void; loading?: boolean;
}) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-text-secondary">Processing Mode:</span>
      <div className="flex rounded overflow-hidden border border-border">
        <button
          onClick={() => onChange("auto")}
          disabled={loading}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors",
            mode === "auto"
              ? "bg-accent text-text-inverse"
              : "bg-surface text-text-secondary hover:bg-subtle"
          )}
        >
          <Bot className="w-3.5 h-3.5" />
          AI Auto
        </button>
        <button
          onClick={() => onChange("manual")}
          disabled={loading}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors border-l border-border",
            mode === "manual"
              ? "bg-nav text-text-inverse"
              : "bg-surface text-text-secondary hover:bg-subtle"
          )}
        >
          <User className="w-3.5 h-3.5" />
          Manual Review
        </button>
      </div>
      {mode === "auto" && (
        <span className="flex items-center gap-1 text-2xs text-success-DEFAULT">
          <Zap className="w-3 h-3" /> Agent processing automatically
        </span>
      )}
      {mode === "manual" && (
        <span className="flex items-center gap-1 text-2xs text-warning-DEFAULT">
          <User className="w-3 h-3" /> You approve each email before processing
        </span>
      )}
    </div>
  );
}

// ── Email Card ──────────────────────────────────────────────
function EmailCard({
  email, mode, onProcess, onSkip, processing
}: {
  email: any; mode: string; processing: boolean;
  onProcess: () => void; onSkip: () => void;
}) {
  const attachments = email.raw_headers?.attachments || [];
  const isAwaiting  = email.status === "processing";
  const isProcessed = email.status === "processed";
  const isSkipped   = email.status === "ignored";

  return (
    <div className={cn(
      "card overflow-hidden transition-all",
      isAwaiting && "border-warning-border",
      isProcessed && "opacity-60",
    )}>
      <div className="flex items-start gap-4 p-4">
        {/* Icon */}
        <div className={cn(
          "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
          isAwaiting  ? "bg-warning-bg"  :
          isProcessed ? "bg-success-bg"  :
          isSkipped   ? "bg-subtle"      : "bg-info-bg"
        )}>
          {isAwaiting  ? <Clock    className="w-4 h-4 text-warning-DEFAULT" /> :
           isProcessed ? <CheckCircle className="w-4 h-4 text-success-DEFAULT" /> :
           isSkipped   ? <SkipForward className="w-4 h-4 text-text-tertiary" /> :
                         <Mail     className="w-4 h-4 text-info-DEFAULT" />}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-text-primary truncate">
                {email.subject || "(no subject)"}
              </p>
              <p className="text-2xs text-text-tertiary mt-0.5 truncate">
                {email.from_address}
              </p>
            </div>
            <span className="text-2xs font-mono text-text-tertiary whitespace-nowrap">
              {formatDateTime(email.received_at)}
            </span>
          </div>

          {email.body_preview && (
            <p className="text-xs text-text-secondary mt-2 line-clamp-2">
              {email.body_preview}
            </p>
          )}

          {/* Attachments */}
          {attachments.length > 0 && (
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              {attachments.map((a: any, i: number) => (
                <div key={i} className="flex items-center gap-1 px-2 py-1 bg-subtle rounded text-2xs text-text-secondary">
                  <Paperclip className="w-3 h-3" />
                  {a.filename}
                  {a.size && <span className="text-text-tertiary">
                    ({(a.size / 1024).toFixed(0)}KB)
                  </span>}
                </div>
              ))}
            </div>
          )}

          {/* Status + Actions */}
          <div className="flex items-center justify-between mt-3">
            <div className="flex items-center gap-2">
              <span className={cn("badge",
                isAwaiting  ? "badge-hold"    :
                isProcessed ? "badge-pass"    :
                isSkipped   ? "badge-neutral" : "badge-info"
              )}>
                {isAwaiting  ? "AWAITING REVIEW" :
                 isProcessed ? "PROCESSED"       :
                 isSkipped   ? "SKIPPED"         : email.status?.toUpperCase()}
              </span>
              {email.classification === "freight" && (
                <span className="badge badge-info">FREIGHT</span>
              )}
            </div>

            {/* Action buttons — only shown in manual mode for awaiting emails */}
            {mode === "manual" && isAwaiting && (
              <div className="flex items-center gap-2">
                <button
                  className="btn btn-danger btn-sm"
                  onClick={onSkip}
                  disabled={processing}
                >
                  <SkipForward className="w-3.5 h-3.5" />
                  Skip
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={onProcess}
                  disabled={processing}
                >
                  <Play className="w-3.5 h-3.5" />
                  {processing ? "Processing…" : "Process →"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Main Inbox Page ─────────────────────────────────────────
export default function InboxPage() {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<string>("");
  const [processingId, setProcessingId] = useState<string | null>(null);

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ["inbox-status"],
    queryFn:  inboxApi.status,
    refetchInterval: 30_000,
  });

  const { data: emailData, isLoading: emailsLoading } = useQuery({
    queryKey: ["inbox-emails", filter],
    queryFn:  () => inboxApi.emails(filter || undefined),
    refetchInterval: 15_000,
  });

  const modeMut = useMutation({
    mutationFn: (mode: string) => inboxApi.setMode(mode),
    onSuccess: (data) => {
      toast.success(`Mode changed to ${data.inbox_mode}`);
      qc.invalidateQueries({ queryKey: ["inbox-status"] });
    },
    onError: () => toast.error("Failed to change mode"),
  });

  const startMut = useMutation({
    mutationFn: inboxApi.start,
    onSuccess:  () => { toast.success("Inbox agents started"); qc.invalidateQueries({ queryKey: ["inbox-status"] }); },
  });

  const processMut = useMutation({
    mutationFn: (id: string) => inboxApi.processEmail(id),
    onSuccess: (data) => {
      toast.success(`Processing started — Shipment ${data.shipment_id?.slice(0,8)}`);
      qc.invalidateQueries({ queryKey: ["inbox-emails"] });
    },
    onError: (e: any) => toast.error(e.message || "Process failed"),
    onSettled: () => setProcessingId(null),
  });

  const skipMut = useMutation({
    mutationFn: (id: string) => inboxApi.skipEmail(id),
    onSuccess: () => {
      toast.success("Email skipped");
      qc.invalidateQueries({ queryKey: ["inbox-emails"] });
    },
  });

  const mode        = statusData?.inbox_mode || "manual";
  const connections = statusData?.connections || [];
  const emails      = emailData?.data || [];
  const total       = emailData?.total || 0;
  const awaiting    = emails.filter((e: any) => e.status === "processing").length;

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[{ label: "Email Inbox Agent" }]}
        actions={
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["inbox-emails", "inbox-status"] })}
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Refresh
          </button>
        }
      />

      <div className="p-6 space-y-5">

        {/* Agent status + mode toggle */}
        <div className="card p-5">
          <div className="flex items-center justify-between flex-wrap gap-4 mb-4">
            <div>
              <h2 className="text-sm font-semibold text-text-primary mb-1">
                Inbox Agent
              </h2>
              <p className="text-xs text-text-tertiary">
                Monitors your connected inboxes for freight emails and routes them
                through the AI extraction pipeline.
              </p>
            </div>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => startMut.mutate()}
              disabled={startMut.isPending}
            >
              <Power className="w-3.5 h-3.5" />
              {startMut.isPending ? "Starting…" : "Start Agents"}
            </button>
          </div>

          <ModeToggle
            mode={mode}
            onChange={(m) => modeMut.mutate(m)}
            loading={modeMut.isPending}
          />

          {/* Connected accounts */}
          {connections.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <p className="section-label mb-2">Connected Inboxes</p>
              <div className="space-y-2">
                {connections.map((c: any) => (
                  <div key={c.id} className="flex items-center gap-3">
                    <div className={cn(
                      "w-2 h-2 rounded-full flex-shrink-0",
                      c.agent_running ? "bg-success-DEFAULT" : "bg-border-strong"
                    )} />
                    <span className="text-xs text-text-primary">{c.email_address}</span>
                    <span className="text-2xs text-text-tertiary uppercase">{c.type}</span>
                    <span className={cn("badge",
                      c.agent_running ? "badge-pass" : "badge-neutral"
                    )}>
                      {c.agent_running ? "MONITORING" : "IDLE"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {connections.length === 0 && !statusLoading && (
            <div className="mt-4 p-3 bg-info-bg border border-info-border rounded text-xs text-info-DEFAULT">
              No inboxes connected yet.{" "}
              <a href="/settings" className="underline font-medium">
                Connect your email in Settings →
              </a>
            </div>
          )}
        </div>

        {/* Awaiting review banner */}
        {mode === "manual" && awaiting > 0 && (
          <div className="flex items-center gap-3 p-4 bg-warning-bg border border-warning-border rounded-lg">
            <AlertTriangle className="w-4 h-4 text-warning-DEFAULT flex-shrink-0" />
            <div>
              <p className="text-xs font-semibold text-warning-DEFAULT">
                {awaiting} email{awaiting !== 1 ? "s" : ""} awaiting your review
              </p>
              <p className="text-2xs text-text-secondary mt-0.5">
                The AI has detected freight emails with attachments. Review each one below
                and click Process or Skip.
              </p>
            </div>
          </div>
        )}

        {/* Mode explanation */}
        <div className="grid grid-cols-2 gap-4">
          <div className={cn(
            "card p-4 border-l-2",
            mode === "auto" ? "border-l-accent" : "border-l-border"
          )}>
            <div className="flex items-center gap-2 mb-2">
              <Bot className={cn("w-4 h-4", mode === "auto" ? "text-accent" : "text-text-tertiary")} />
              <span className="text-xs font-semibold text-text-primary">AI Auto Mode</span>
              {mode === "auto" && <span className="badge badge-pass">ACTIVE</span>}
            </div>
            <p className="text-2xs text-text-tertiary leading-relaxed">
              Every freight email is automatically processed through the extraction
              pipeline. Shipments appear in the queue with their compliance results.
              Best for high-volume operations with trusted senders.
            </p>
          </div>
          <div className={cn(
            "card p-4 border-l-2",
            mode === "manual" ? "border-l-accent" : "border-l-border"
          )}>
            <div className="flex items-center gap-2 mb-2">
              <User className={cn("w-4 h-4", mode === "manual" ? "text-accent" : "text-text-tertiary")} />
              <span className="text-xs font-semibold text-text-primary">Manual Review Mode</span>
              {mode === "manual" && <span className="badge badge-pass">ACTIVE</span>}
            </div>
            <p className="text-2xs text-text-tertiary leading-relaxed">
              AI detects freight emails and queues them for your decision. You review
              each email and choose Process or Skip. Best for new senders or when
              you need control over what enters the pipeline.
            </p>
          </div>
        </div>

        {/* Email list */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-text-primary">
              Inbox Feed
              <span className="ml-2 text-2xs font-mono text-text-tertiary">
                {total} total
              </span>
            </h3>
            <div className="flex gap-1">
              {["", "processing", "processed", "ignored", "non_freight"].map(s => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  className={cn(
                    "px-2.5 py-1 text-2xs rounded transition-colors",
                    filter === s
                      ? "bg-accent text-text-inverse"
                      : "bg-surface border border-border text-text-secondary hover:bg-subtle"
                  )}
                >
                  {s === ""            ? "All"      :
                   s === "processing"  ? "Awaiting" :
                   s === "processed"   ? "Done"     :
                   s === "ignored"     ? "Skipped"  : "Non-freight"}
                </button>
              ))}
            </div>
          </div>

          {emailsLoading ? (
            <div className="space-y-3">
              {[1,2,3].map(i => <Skeleton key={i} className="h-28 w-full" />)}
            </div>
          ) : emails.length === 0 ? (
            <div className="card p-10 text-center">
              <Mail className="w-10 h-10 text-text-tertiary mx-auto mb-3 stroke-[1.5]" />
              <p className="text-sm font-medium text-text-secondary">No emails yet</p>
              <p className="text-xs text-text-tertiary mt-1">
                {connections.length === 0
                  ? "Connect an inbox in Settings to start monitoring"
                  : "The agent will detect freight emails as they arrive"
                }
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {emails.map((e: any) => (
                <EmailCard
                  key={e.id}
                  email={e}
                  mode={mode}
                  processing={processingId === e.id}
                  onProcess={() => {
                    setProcessingId(e.id);
                    processMut.mutate(e.id);
                  }}
                  onSkip={() => skipMut.mutate(e.id)}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
