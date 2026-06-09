"use client";
import { useQuery } from "@tanstack/react-query";
import { Shield, AlertTriangle, CheckCircle, Activity } from "lucide-react";
import { analyticsApi, complianceApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import { cn } from "@/lib/utils";

const MODULE_LABELS: Record<string, string> = {
  invoice_pl_xref:   "Invoice ↔ Packing List",
  hs_code_validator: "HS Code Validator",
  vat_engine:        "VAT Formula Engine",
  rla_sentinel:      "RLA Status Sentinel",
  da65_detector:     "DA 65 Temp Export",
  da179_calculator:  "DA 179 Sugar Tax",
  rcg_matcher:       "RCG Manifest",
};

export default function CompliancePage() {
  const { data: summary, isLoading } = useQuery({
    queryKey: ["compliance-summary"],
    queryFn:  () => analyticsApi.compliance(30),
  });

  const { data: rla } = useQuery({
    queryKey: ["rla-statuses"],
    queryFn:  complianceApi.rla,
  });

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[{ label: "Compliance Shield" }]} />

      <div className="p-6 space-y-6">
        {/* Shield summary cards */}
        {isLoading ? (
          <div className="grid grid-cols-4 gap-4">
            {[1,2,3,4].map(i => <Skeleton key={i} className="h-28" />)}
          </div>
        ) : summary ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                {
                  label: "Compliant",
                  value: summary.shield_breakdown.pass,
                  icon: CheckCircle,
                  color: "text-success-DEFAULT",
                  bg: "bg-success-bg border-success-border",
                },
                {
                  label: "Under Review",
                  value: summary.shield_breakdown.hold,
                  icon: AlertTriangle,
                  color: "text-warning-DEFAULT",
                  bg: "bg-warning-bg border-warning-border",
                },
                {
                  label: "Compliance Failures",
                  value: summary.shield_breakdown.fail,
                  icon: Shield,
                  color: "text-error-DEFAULT",
                  bg: "bg-error-bg border-error-border",
                },
                {
                  label: "Penalty Risk Events",
                  value: summary.penalty_risk_events,
                  icon: AlertTriangle,
                  color: "text-error-DEFAULT",
                  bg: "bg-error-bg border-error-border",
                },
              ].map(({ label, value, icon: Icon, color, bg }) => (
                <div key={label} className={cn("card p-5 border", bg)}>
                  <div className="flex items-center justify-between mb-3">
                    <span className="section-label">{label}</span>
                    <Icon className={cn("w-4 h-4", color)} />
                  </div>
                  <div className={cn("text-3xl font-mono font-medium", color)}>{value}</div>
                  <p className="text-2xs text-text-tertiary mt-1">Last 30 days</p>
                </div>
              ))}
            </div>

            {/* Pass rate + top failing modules */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Pass rate */}
              <div className="card p-5">
                <h3 className="text-xs font-semibold text-text-primary mb-4">
                  Overall Compliance Pass Rate
                </h3>
                <div className="flex items-end gap-3 mb-3">
                  <span className={cn(
                    "text-5xl font-mono font-medium",
                    summary.pass_rate_pct >= 90 ? "text-success-DEFAULT" :
                    summary.pass_rate_pct >= 70 ? "text-warning-DEFAULT" :
                    "text-error-DEFAULT"
                  )}>
                    {summary.pass_rate_pct}%
                  </span>
                  <span className="text-xs text-text-tertiary mb-2">
                    of {summary.total_shipments} shipments
                  </span>
                </div>
                <div className="w-full bg-subtle rounded-full h-2">
                  <div
                    className={cn(
                      "h-2 rounded-full transition-all",
                      summary.pass_rate_pct >= 90 ? "bg-success-DEFAULT" :
                      summary.pass_rate_pct >= 70 ? "bg-warning-DEFAULT" :
                      "bg-error-DEFAULT"
                    )}
                    style={{ width: `${summary.pass_rate_pct}%` }}
                  />
                </div>
                <p className="text-2xs text-text-tertiary mt-2">
                  Target: ≥ 95% · Industry average: ~82%
                </p>
              </div>

              {/* Top failing modules */}
              <div className="card overflow-hidden">
                <div className="card-header">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-text-tertiary" />
                    <h3 className="text-xs font-semibold text-text-primary">
                      Top Compliance Issues (30 days)
                    </h3>
                  </div>
                </div>
                <div className="divide-y divide-border">
                  {summary.top_failing_modules.length === 0 ? (
                    <div className="px-4 py-6 text-center text-xs text-text-tertiary">
                      No issues detected
                    </div>
                  ) : summary.top_failing_modules.slice(0, 6).map((m: any) => (
                    <div key={m.module} className="flex items-center justify-between px-4 py-3">
                      <span className="text-xs text-text-primary">
                        {MODULE_LABELS[m.module] || m.module}
                      </span>
                      <span className="font-mono text-xs font-medium text-error-DEFAULT">
                        {m.count} issue{m.count !== 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </>
        ) : null}

        {/* RLA Monitor */}
        <div className="card overflow-hidden">
          <div className="card-header">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-text-tertiary" />
              <h3 className="text-xs font-semibold text-text-primary">
                RLA Status Monitor — Active Importers
              </h3>
            </div>
            <span className="text-2xs text-text-tertiary">
              Checked daily at 06:00 SA time
            </span>
          </div>

          {!rla || rla.length === 0 ? (
            <div className="px-4 py-8 text-center text-xs text-text-tertiary">
              No importers configured. Add importers in Settings → WiseLayer → RLA Sentinel.
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Importer</th>
                  <th>Code</th>
                  <th>RLA Status</th>
                  <th>Last Checked</th>
                  <th>Alert Sent</th>
                </tr>
              </thead>
              <tbody>
                {rla.map((r: any) => (
                  <tr key={r.id}>
                    <td className="text-xs font-medium">{r.importer_name || "—"}</td>
                    <td className="font-mono text-2xs text-text-secondary">{r.importer_code}</td>
                    <td>
                      <span className={cn(
                        "badge",
                        r.rla_status === "active"    ? "badge-pass" :
                        r.rla_status === "suspended" ? "badge-fail" :
                        r.rla_status === "inactive"  ? "badge-hold" :
                        "badge-neutral"
                      )}>
                        {r.rla_status.toUpperCase()}
                      </span>
                    </td>
                    <td className="font-mono text-2xs text-text-tertiary">
                      {r.last_checked_at
                        ? new Date(r.last_checked_at).toLocaleString("en-ZA")
                        : "Never"
                      }
                    </td>
                    <td>
                      {r.alert_sent
                        ? <CheckCircle className="w-4 h-4 text-success-DEFAULT" />
                        : <span className="text-text-tertiary text-xs">—</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
