"use client";
import { useQuery } from "@tanstack/react-query";
import {
  ListTodo, CheckCircle, AlertTriangle, Shield, Clock, TrendingUp
} from "lucide-react";
import { analyticsApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { KPISkeleton, Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/utils";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid
} from "recharts";

// ── KPI Card ────────────────────────────────────────────────
function KPICard({
  label, value, sub, icon: Icon, color = "text-text-primary", alert = false
}: {
  label: string; value: string | number; sub?: string;
  icon: React.ElementType; color?: string; alert?: boolean;
}) {
  return (
    <div className={cn("card p-5", alert && "border-error-border")}>
      <div className="flex items-start justify-between mb-3">
        <span className="section-label">{label}</span>
        <Icon className={cn("w-4 h-4", color)} />
      </div>
      <div className={cn("text-3xl font-mono font-medium leading-none mb-1", color)}>
        {value}
      </div>
      {sub && <p className="text-2xs text-text-tertiary mt-1">{sub}</p>}
    </div>
  );
}

// ── Custom tooltip for chart ────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface border border-border rounded shadow-lg p-3 text-xs">
      <p className="font-semibold text-text-primary mb-2">{label}</p>
      {payload.map((p: any) => (
        <div key={p.dataKey} className="flex items-center gap-2 py-0.5">
          <span className="w-2 h-2 rounded-sm flex-shrink-0" style={{ background: p.fill }} />
          <span className="text-text-secondary capitalize">{p.dataKey.replace("_", " ")}</span>
          <span className="font-mono ml-auto text-text-primary">{p.value}</span>
        </div>
      ))}
    </div>
  );
}

// ── Main Dashboard ──────────────────────────────────────────
export default function DashboardPage() {
  const { data: kpis, isLoading: kpisLoading } = useQuery({
    queryKey: ["dashboard-kpis"],
    queryFn: analyticsApi.dashboard,
    refetchInterval: 30_000,
  });

  const { data: volumeData, isLoading: volumeLoading } = useQuery({
    queryKey: ["volume-30d"],
    queryFn: () => analyticsApi.volume(30),
  });

  const { data: roi } = useQuery({
    queryKey: ["roi"],
    queryFn: analyticsApi.roi,
  });

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[{ label: "Dashboard" }]} />

      <div className="p-6 space-y-6">
        {/* KPIs */}
        {kpisLoading ? (
          <KPISkeleton />
        ) : kpis ? (
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard
              label="Queue Size"
              value={kpis.queue_size}
              sub="Shipments awaiting review"
              icon={ListTodo}
              color={kpis.queue_size > 20 ? "text-warning-DEFAULT" : "text-text-primary"}
            />
            <KPICard
              label="Processed Today"
              value={kpis.processed_today}
              sub="Approved + Rejected"
              icon={CheckCircle}
              color="text-success-DEFAULT"
            />
            <KPICard
              label="Automation Rate"
              value={`${kpis.automation_rate}%`}
              sub="Auto-approved today"
              icon={TrendingUp}
              color={kpis.automation_rate >= 70 ? "text-success-DEFAULT" : "text-warning-DEFAULT"}
            />
            <KPICard
              label="Exceptions"
              value={kpis.exceptions_requiring_review}
              sub="Require human review"
              icon={AlertTriangle}
              color={kpis.exceptions_requiring_review > 0 ? "text-warning-DEFAULT" : "text-text-primary"}
              alert={kpis.exceptions_requiring_review > 5}
            />
            <KPICard
              label="Compliance Flags"
              value={kpis.compliance_flags_today}
              sub="SARS risk flags today"
              icon={Shield}
              color={kpis.compliance_flags_today > 0 ? "text-error-DEFAULT" : "text-text-primary"}
              alert={kpis.compliance_flags_today > 0}
            />
            <KPICard
              label="Avg Process Time"
              value={kpis.avg_processing_time_seconds
                ? `${kpis.avg_processing_time_seconds}s`
                : "—"
              }
              sub="Per shipment (7-day avg)"
              icon={Clock}
            />
          </div>
        ) : null}

        {/* Two-column row */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">

          {/* Volume Chart */}
          <div className="card xl:col-span-2">
            <div className="card-header">
              <div>
                <h2 className="text-sm font-semibold text-text-primary">Shipment Volume</h2>
                <p className="text-2xs text-text-tertiary mt-0.5">Last 30 days — daily processing breakdown</p>
              </div>
            </div>
            <div className="p-6">
              {volumeLoading ? (
                <Skeleton className="h-52 w-full" />
              ) : volumeData?.data ? (
                <ResponsiveContainer width="100%" height={210}>
                  <BarChart data={volumeData.data} barSize={8} barGap={2}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#DDE3EA" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10, fill: "#6B7E92", fontFamily: "monospace" }}
                      tickLine={false}
                      axisLine={false}
                      tickFormatter={d => d.slice(5)}
                      interval={4}
                    />
                    <YAxis
                      tick={{ fontSize: 10, fill: "#6B7E92", fontFamily: "monospace" }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Bar dataKey="auto_approved"   fill="#15632A" radius={[2,2,0,0]} name="Auto Approved" />
                    <Bar dataKey="manual_reviewed" fill="#B8860B" radius={[2,2,0,0]} name="Reviewed" />
                    <Bar dataKey="failed"          fill="#9B1C1C" radius={[2,2,0,0]} name="Failed" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-52 flex items-center justify-center text-xs text-text-tertiary">
                  No volume data yet
                </div>
              )}
              <div className="flex items-center gap-5 mt-4">
                {[
                  { color: "#15632A", label: "Auto Approved" },
                  { color: "#B8860B", label: "Manually Reviewed" },
                  { color: "#9B1C1C", label: "Failed / Error" },
                ].map(({ color, label }) => (
                  <div key={label} className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                    <span className="text-2xs text-text-tertiary">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* ROI Summary */}
          {roi && (
            <div className="card">
              <div className="card-header">
                <h2 className="text-sm font-semibold text-text-primary">ROI Summary</h2>
              </div>
              <div className="p-5 space-y-4">
                {[
                  {
                    label: "Shipments Processed",
                    value: roi.total_shipments_processed.toLocaleString("en-ZA"),
                    color: "text-text-primary",
                  },
                  {
                    label: "Hours Saved",
                    value: `${roi.time_saved_hours.toLocaleString("en-ZA")}h`,
                    color: "text-success-DEFAULT",
                  },
                  {
                    label: "Labour Cost Saved",
                    value: `R${roi.labour_cost_saved_zar.toLocaleString("en-ZA")}`,
                    color: "text-success-DEFAULT",
                  },
                  {
                    label: "SARS Penalties Prevented",
                    value: `R${roi.sars_penalties_prevented_zar.toLocaleString("en-ZA")}`,
                    color: "text-error-DEFAULT",
                  },
                  {
                    label: "Total Value Delivered",
                    value: `R${roi.total_value_delivered_zar.toLocaleString("en-ZA")}`,
                    color: "text-accent",
                  },
                ].map(({ label, value, color }) => (
                  <div key={label} className="flex justify-between items-baseline border-b border-border pb-3 last:border-0 last:pb-0">
                    <span className="text-xs text-text-secondary">{label}</span>
                    <span className={cn("font-mono text-sm font-medium", color)}>{value}</span>
                  </div>
                ))}

                <div className="mt-4 p-3 bg-success-bg border border-success-border rounded text-xs">
                  <p className="text-2xs text-success-DEFAULT font-semibold uppercase tracking-wide mb-1">
                    Errors Prevented
                  </p>
                  <p className="text-2xl font-mono font-medium text-success-DEFAULT">
                    {roi.errors_prevented}
                  </p>
                  <p className="text-text-tertiary mt-1">
                    Potential SARS penalty events caught before submission
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
