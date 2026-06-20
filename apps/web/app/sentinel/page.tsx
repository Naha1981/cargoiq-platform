"use client";
import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  TrendingDown, TrendingUp, Shield, AlertTriangle,
  CheckCircle, Activity, Clock, Zap, DollarSign,
  Ship, FileText, RefreshCw, Sparkles
} from "lucide-react";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Animated counter ────────────────────────────────────────
function AnimatedCounter({ value, prefix = "", suffix = "", className = "" }: {
  value: number; prefix?: string; suffix?: string; className?: string;
}) {
  const [displayed, setDisplayed] = useState(0);
  const prev = useRef(0);

  useEffect(() => {
    const start = prev.current;
    const end   = value;
    const delta = end - start;
    if (delta === 0) return;
    const duration = Math.min(Math.abs(delta) * 2, 1500);
    const startTime = performance.now();

    const tick = (now: number) => {
      const progress = Math.min((now - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(start + delta * ease));
      if (progress < 1) requestAnimationFrame(tick);
      else prev.current = end;
    };
    requestAnimationFrame(tick);
  }, [value]);

  return (
    <span className={className}>
      {prefix}{displayed.toLocaleString("en-ZA")}{suffix}
    </span>
  );
}

// ── Pulsing dot ─────────────────────────────────────────────
function PulseDot({ color = "bg-error-DEFAULT" }: { color?: string }) {
  return (
    <span className="relative flex h-3 w-3">
      <span className={cn("animate-ping absolute inline-flex h-full w-full rounded-full opacity-75", color)} />
      <span className={cn("relative inline-flex rounded-full h-3 w-3", color)} />
    </span>
  );
}

// ── Metric row ──────────────────────────────────────────────
function MetricRow({ label, value, sub, color = "text-text-primary" }: any) {
  return (
    <div className="flex justify-between items-baseline py-3 border-b border-white/10 last:border-0">
      <span className="text-xs text-slate-400">{label}</span>
      <div className="text-right">
        <span className={cn("font-mono text-sm font-semibold", color)}>{value}</span>
        {sub && <p className="text-2xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

// ── Event feed item ─────────────────────────────────────────
function EventItem({ event }: { event: any }) {
  const isPositive = event.type === "saved" || event.type === "recovered";
  const isNegative = event.type === "risk" || event.type === "flag";
  return (
    <div className={cn(
      "flex items-start gap-3 py-2.5 border-b border-white/5 last:border-0",
      "animate-in slide-in-from-top-2 duration-300"
    )}>
      <div className={cn(
        "w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0",
        isPositive ? "bg-emerald-400" :
        isNegative ? "bg-red-400" : "bg-amber-400"
      )} />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-slate-300 leading-relaxed">{event.message}</p>
        <p className="text-2xs text-slate-500 mt-0.5 font-mono">{event.timestamp}</p>
      </div>
      {event.value && (
        <span className={cn(
          "font-mono text-xs font-semibold flex-shrink-0",
          isPositive ? "text-emerald-400" : "text-red-400"
        )}>
          {isPositive ? "+" : ""}R{Math.abs(event.value).toLocaleString("en-ZA")}
        </span>
      )}
    </div>
  );
}

// ── Main Sentinel Page ──────────────────────────────────────
export default function SentinelPage() {
  const [liveEvents, setLiveEvents] = useState<any[]>([]);
  const [leakageTick, setLeakageTick] = useState(0);

  const { data: kpis,    refetch: refetchKPIs }  = useQuery({ queryKey: ["sentinel-kpis"],    queryFn: () => apiClient.get("/analytics/dashboard"),   refetchInterval: 15000 });
  const { data: roi }                             = useQuery({ queryKey: ["sentinel-roi"],     queryFn: () => apiClient.get("/analytics/roi"),          refetchInterval: 60000 });
  const { data: compData }                        = useQuery({ queryKey: ["sentinel-comp"],    queryFn: () => apiClient.get("/analytics/compliance-summary?days=30"), refetchInterval: 30000 });
  const { data: containers }                      = useQuery({ queryKey: ["sentinel-conts"],   queryFn: () => apiClient.get("/portals/containers?released=false"), refetchInterval: 30000 });
  const { data: certData }                        = useQuery({ queryKey: ["sentinel-cert"],    queryFn: () => apiClient.get("/audit/certificate/data"), refetchInterval: 60000 });
  const { data: waitingFindings, refetch: refetchWaiting } = useQuery({ queryKey: ["sentinel-waiting"], queryFn: () => apiClient.get("/analytics/waiting-time/findings?status=identified"), refetchInterval: 60000 });

  // Mark the "view Sentinel" onboarding step complete on first visit
  useEffect(() => {
    apiClient.post("/onboarding/sentinel-viewed", {}).catch(() => {});
  }, []);

  // Leakage counter ticks up every second by ~R550/hr estimate
  // Only if there are unreleased containers with demurrage
  useEffect(() => {
    const conts    = (containers as any[]) || [];
    const withRisk = conts.filter((c: any) => (c.demurrage_zar || 0) > 0);
    if (withRisk.length === 0) return;
    const hourlyRate = withRisk.length * 550;   // R550/container/hr
    const perSecond  = hourlyRate / 3600;
    const interval   = setInterval(() => {
      setLeakageTick(t => t + perSecond);
    }, 1000);
    return () => clearInterval(interval);
  }, [containers]);

  // Simulate live event feed (in production these come from Supabase Realtime)
  useEffect(() => {
    const events = [
      { type: "saved",     message: "Compliance Shield: HS code error caught on shipment CIQ-2026-00247 before SARS submission", value: 4500, timestamp: "just now" },
      { type: "flag",      message: "RLA Sentinel: Container MSCU1234567 approaching free-time limit (2 days remaining)", value: 25000, timestamp: "2 min ago" },
      { type: "recovered", message: "WiseLayer: 47 CargoWise updates compacted → 8 XML events. CargoWise bill reduced.", value: 14820, timestamp: "5 min ago" },
      { type: "risk",      message: "Port Alert: Container HLCU9876543 — Durban T2 demurrage accruing @ R12,500/day", value: 12500, timestamp: "12 min ago" },
      { type: "saved",     message: "Invoice/PL Cross-ref: Weight variance 1.4kg detected — R4,500 SARS fine prevented", value: 4500, timestamp: "18 min ago" },
      { type: "recovered", message: "Email Agent: New air import from Shenzhen Electronics extracted — 3 documents processed", value: null, timestamp: "24 min ago" },
    ];
    setLiveEvents(events);
  }, []);

  const activeLeakage  = leakageTick + ((containers as any[])?.reduce((sum: number, c: any) => sum + (c.demurrage_zar || 0), 0) || 0);
  const recoveredValue = (roi as any)?.total_value_delivered_zar || 0;
  const queueSize      = (kpis as any)?.queue_size || 0;
  const complianceFlags = (kpis as any)?.compliance_flags_today || 0;
  const passRate        = (compData as any)?.pass_rate_pct || 0;
  const certValue       = (certData as any)?.total_value_zar || 0;
  const certROI         = (certData as any)?.roi_multiple || 0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 font-sans">

      {/* Header */}
      <div className="border-b border-slate-800 px-8 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-slate-800 flex items-center justify-center">
            <Activity className="w-4 h-4 text-amber-500" />
          </div>
          <div>
            <span className="font-mono text-base font-bold text-white">Cargo<span className="text-amber-500">IQ</span></span>
            <span className="ml-3 text-xs text-slate-500 font-mono uppercase tracking-widest">Sentinel</span>
          </div>
        </div>
        <div className="flex items-center gap-4 text-2xs font-mono text-slate-500">
          <span className="flex items-center gap-1.5"><PulseDot color="bg-emerald-500" /> AI AGENTS ACTIVE</span>
          <span className="flex items-center gap-1.5"><PulseDot color="bg-blue-500" /> PORTAL WATCHERS RUNNING</span>
          <span>POPIA COMPLIANT · ZA-HOSTED</span>
        </div>
      </div>

      <div className="p-8 space-y-6">

        {/* Row 1: The 3 hero metrics */}
        <div className="grid grid-cols-3 gap-6">

          {/* ACTIVE LEAKAGE — pulsing red */}
          <div className={cn(
            "rounded-xl p-6 border",
            activeLeakage > 0
              ? "bg-red-950/40 border-red-800/50"
              : "bg-slate-900 border-slate-800"
          )}>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <PulseDot color={activeLeakage > 0 ? "bg-red-500" : "bg-slate-600"} />
                <span className="text-2xs font-mono uppercase tracking-widest text-slate-400">
                  Active Revenue at Risk
                </span>
              </div>
              <TrendingDown className="w-4 h-4 text-red-400" />
            </div>
            <div className={cn(
              "font-mono font-bold leading-none mb-2",
              activeLeakage > 0 ? "text-red-400" : "text-slate-600",
              activeLeakage > 100000 ? "text-5xl" : "text-4xl"
            )}>
              R <AnimatedCounter value={Math.round(activeLeakage)} />
            </div>
            <p className="text-2xs text-slate-500 mt-2">
              {(containers as any[])?.filter((c: any) => (c.demurrage_zar || 0) > 0).length || 0} containers accruing demurrage
            </p>
          </div>

          {/* RECOVERED THIS MONTH — green */}
          <div className="rounded-xl p-6 bg-emerald-950/30 border border-emerald-800/40">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <PulseDot color="bg-emerald-500" />
                <span className="text-2xs font-mono uppercase tracking-widest text-slate-400">
                  Value Delivered (MTD)
                </span>
              </div>
              <TrendingUp className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-4xl font-mono font-bold text-emerald-400 leading-none mb-2">
              R <AnimatedCounter value={Math.round(certValue || recoveredValue)} />
            </div>
            <p className="text-2xs text-slate-500 mt-2">
              {certROI > 0 ? `${certROI}× return on CargoIQ investment` : "Savings + fines prevented + time saved"}
            </p>
          </div>

          {/* COMPLIANCE PASS RATE */}
          <div className="rounded-xl p-6 bg-slate-900 border border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <PulseDot color={passRate >= 95 ? "bg-emerald-500" : passRate >= 80 ? "bg-amber-500" : "bg-red-500"} />
                <span className="text-2xs font-mono uppercase tracking-widest text-slate-400">
                  Compliance Pass Rate
                </span>
              </div>
              <Shield className="w-4 h-4 text-blue-400" />
            </div>
            <div className={cn(
              "text-4xl font-mono font-bold leading-none mb-2",
              passRate >= 95 ? "text-emerald-400" :
              passRate >= 80 ? "text-amber-400" : "text-red-400"
            )}>
              <AnimatedCounter value={Math.round(passRate)} suffix="%" />
            </div>
            <div className="w-full bg-slate-800 rounded-full h-1.5 mt-3">
              <div
                className={cn("h-1.5 rounded-full transition-all duration-1000",
                  passRate >= 95 ? "bg-emerald-500" :
                  passRate >= 80 ? "bg-amber-500" : "bg-red-500"
                )}
                style={{ width: `${passRate}%` }}
              />
            </div>
            <p className="text-2xs text-slate-500 mt-2">
              {complianceFlags > 0 ? `${complianceFlags} active flags today` : "No flags today"}
            </p>
          </div>
        </div>

        {/* Row 2: Operations + event feed */}
        <div className="grid grid-cols-3 gap-6">

          {/* Operations panel */}
          <div className="col-span-1 rounded-xl bg-slate-900 border border-slate-800 p-6">
            <p className="text-2xs font-mono uppercase tracking-widest text-slate-500 mb-4">
              System Status
            </p>
            <div className="space-y-1">
              <MetricRow
                label="Queue (awaiting review)"
                value={queueSize}
                color={queueSize > 20 ? "text-amber-400" : "text-white"}
              />
              <MetricRow
                label="AI Automation Rate"
                value={`${(kpis as any)?.automation_rate || 0}%`}
                color="text-emerald-400"
              />
              <MetricRow
                label="Avg Processing Time"
                value={(kpis as any)?.avg_processing_time_seconds
                  ? `${(kpis as any).avg_processing_time_seconds}s`
                  : "—"
                }
              />
              <MetricRow
                label="Containers Tracked"
                value={(containers as any[])?.length || 0}
                color="text-blue-400"
              />
              <MetricRow
                label="Unreleased Containers"
                value={(containers as any[])?.filter((c:any) => !c.is_released).length || 0}
                color={(containers as any[])?.some((c:any) => !c.is_released) ? "text-amber-400" : "text-white"}
              />
            </div>

            {/* Mini savings cert */}
            {certData && (
              <div className="mt-6 pt-5 border-t border-slate-800">
                <p className="text-2xs font-mono uppercase tracking-widest text-slate-500 mb-3">
                  This Month
                </p>
                <div className="space-y-2">
                  {[
                    { label: "SARS Fines Prevented", value: (certData as any).fines_prevented_zar, color: "text-emerald-400" },
                    { label: "CW Savings",           value: (certData as any).cw_savings_zar,       color: "text-emerald-400" },
                    { label: "Subscription Cost",    value: (certData as any).subscription_zar,     color: "text-red-400", neg: true },
                    { label: "Net EBITDA Boost",      value: (certData as any).net_benefit_zar,     color: "text-amber-400" },
                  ].map(m => m.value != null && (
                    <div key={m.label} className="flex justify-between text-xs">
                      <span className="text-slate-500">{m.label}</span>
                      <span className={cn("font-mono font-medium", m.color)}>
                        {m.neg ? "-" : "+"}R{Math.abs(m.value).toLocaleString("en-ZA")}
                      </span>
                    </div>
                  ))}
                </div>
                <a
                  href="/api/v1/audit/certificate"
                  target="_blank"
                  className="mt-4 w-full flex items-center justify-center gap-2 px-3 py-2 bg-amber-600/20 hover:bg-amber-600/30 border border-amber-600/40 text-amber-400 rounded text-xs font-medium transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" />
                  Download Savings Certificate
                </a>
                <a
                  href="/api/v1/audit/success-story"
                  target="_blank"
                  className="mt-2 w-full flex items-center justify-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 rounded text-xs font-medium transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  Generate Success Story (anonymized)
                </a>
              </div>
            )}
          </div>

          {/* Live event feed */}
          <div className="col-span-2 rounded-xl bg-slate-900 border border-slate-800 p-6">
            <div className="flex items-center justify-between mb-4">
              <p className="text-2xs font-mono uppercase tracking-widest text-slate-500">
                Live Intelligence Feed
              </p>
              <div className="flex items-center gap-1.5 text-2xs text-emerald-400 font-mono">
                <PulseDot color="bg-emerald-500" />
                LIVE
              </div>
            </div>
            <div className="space-y-0">
              {liveEvents.map((ev, i) => (
                <EventItem key={i} event={ev} />
              ))}
            </div>
          </div>
        </div>

        {/* Row 2.5: Unbilled Waiting Time — "double-tap to invoice" */}
        {(waitingFindings as any[])?.length > 0 && (
          <div className="rounded-xl bg-slate-900 border border-amber-900/30 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-semibold text-white">
                Unbilled Waiting Time — Found via Driver WhatsApp Check-Ins
              </span>
              <span className="ml-auto text-2xs font-mono text-amber-400">
                {(waitingFindings as any[]).length} pending
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-800">
                    {["Reference","Location","Arrived","Departed","Billable","Amount",""].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-2xs font-semibold uppercase tracking-wider text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(waitingFindings as any[]).map((f: any) => (
                    <tr key={f.id} className="border-b border-slate-800/50">
                      <td className="px-4 py-3 font-mono text-xs text-amber-400 font-medium">{f.reference || "—"}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{f.location_name || "—"}</td>
                      <td className="px-4 py-3 font-mono text-2xs text-slate-400">
                        {new Date(f.arrived_at).toLocaleString("en-ZA", { day:"2-digit", month:"short", hour:"2-digit", minute:"2-digit" })}
                      </td>
                      <td className="px-4 py-3 font-mono text-2xs text-slate-400">
                        {new Date(f.departed_at).toLocaleString("en-ZA", { day:"2-digit", month:"short", hour:"2-digit", minute:"2-digit" })}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-300">{f.billable_minutes}m</td>
                      <td className="px-4 py-3 font-mono text-sm font-bold text-emerald-400">
                        R{Number(f.unbilled_revenue_zar || 0).toLocaleString("en-ZA")}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <a
                          href={`${API_BASE}/api/v1/invoices/${f.id}/print`}
                          target="_blank"
                          className="text-2xs text-amber-400 hover:underline font-medium mr-3"
                        >
                          Generate Invoice →
                        </a>
                        <button
                          className="text-2xs text-slate-400 hover:text-slate-200 font-medium"
                          onClick={async () => {
                            await apiClient.post(`/invoices/from-finding/${f.id}`, { due_days: 30 });
                            refetchWaiting();
                          }}
                        >
                          Mark Invoiced
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Row 3: Container demurrage table */}
        {(containers as any[])?.some((c: any) => !c.is_released) && (
          <div className="rounded-xl bg-slate-900 border border-red-900/30 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <span className="text-xs font-semibold text-white">
                Containers Accruing Port Storage Fees
              </span>
              <span className="ml-auto text-2xs text-red-400 font-mono font-medium">
                R12,500/container/day
              </span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-slate-800">
                    {["Container","Line","Status","Location","ETA","Demurrage Exposure"].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-2xs font-semibold uppercase tracking-wider text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(containers as any[]).filter((c: any) => !c.is_released).map((c: any) => (
                    <tr key={c.id} className="border-b border-slate-800/50">
                      <td className="px-4 py-3 font-mono text-xs text-amber-400 font-medium">{c.container_number}</td>
                      <td className="px-4 py-3 text-xs text-slate-400">{c.shipping_line || "—"}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-0.5 rounded text-2xs font-semibold bg-amber-900/40 text-amber-400 border border-amber-700/40 uppercase">
                          {(c.status || "unknown").toUpperCase()}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-slate-400">{c.location || "—"}</td>
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">
                        {c.eta ? new Date(c.eta).toLocaleDateString("en-ZA") : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-sm font-bold text-red-400">
                        {(c.demurrage_zar || 0) > 0
                          ? `R${c.demurrage_zar.toLocaleString("en-ZA")}`
                          : <span className="text-emerald-400 text-xs">Within free time</span>
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
  );
}
