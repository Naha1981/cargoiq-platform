"use client";
import { useState } from "react";
import { Shield, ShieldAlert, ShieldX, ShieldCheck, ChevronDown, ChevronUp, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

interface ModuleResult {
  module: string;
  result: "pass" | "hold" | "fail";
  detail: Record<string, any>;
  penalty_risk: boolean;
  resolution?: string;
}

interface ShieldReport {
  overall: string;
  modules: ModuleResult[];
  penalty_risk_detected: boolean;
  block_cargowise: boolean;
}

const MODULE_LABELS: Record<string, string> = {
  invoice_pl_xref:    "Invoice ↔ Packing List Cross-Reference",
  hs_code_validator:  "HS Code Format Validator (8-digit SARS)",
  vat_engine:         "SACU / Non-SACU VAT Formula Engine",
  rla_sentinel:       "RLA eFiling Status Sentinel",
  da65_detector:      "DA 65 Temporary Export Detector",
  da179_calculator:   "DA 179 Sugar Tax Calculator",
  rcg_matcher:        "RCG Manifest Matcher",
};

const MODULE_ICONS: Record<string, string> = {
  invoice_pl_xref:   "⚖️",
  hs_code_validator: "🔢",
  vat_engine:        "🧮",
  rla_sentinel:      "🔍",
  da65_detector:     "🏷️",
  da179_calculator:  "🥤",
  rcg_matcher:       "📋",
};

function ModuleRow({ module }: { module: ModuleResult }) {
  const [expanded, setExpanded] = useState(module.result !== "pass");

  const rowBg = module.result === "fail"
    ? "border-l-2 border-l-error-DEFAULT bg-error-bg/30"
    : module.result === "hold"
    ? "border-l-2 border-l-warning-DEFAULT bg-warning-bg/30"
    : "";

  const badgeClass = module.result === "pass"
    ? "badge-pass" : module.result === "hold"
    ? "badge-hold" : "badge-fail";

  return (
    <div className={cn("border-b border-border last:border-b-0", rowBg)}>
      <div
        className="flex items-center justify-between px-4 py-3 cursor-pointer hover:bg-black/5"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <span className="text-lg">{MODULE_ICONS[module.module] || "🔒"}</span>
          <div>
            <div className="text-xs font-medium text-text-primary">
              {MODULE_LABELS[module.module] || module.module}
            </div>
            {module.penalty_risk && (
              <div className="flex items-center gap-1 mt-0.5">
                <AlertTriangle className="w-3 h-3 text-error-DEFAULT" />
                <span className="text-2xs text-error-DEFAULT font-medium">SARS penalty risk</span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className={cn("badge", badgeClass)}>
            {module.result.toUpperCase()}
          </span>
          {module.result !== "pass" && (
            expanded
              ? <ChevronUp className="w-4 h-4 text-text-tertiary" />
              : <ChevronDown className="w-4 h-4 text-text-tertiary" />
          )}
        </div>
      </div>

      {expanded && module.result !== "pass" && (
        <div className="px-4 pb-4 space-y-3">
          {/* Detail */}
          <div className="bg-surface rounded border border-border p-3">
            <p className="section-label mb-2">Detail</p>
            {Object.entries(module.detail).map(([k, v]) => (
              <div key={k} className="flex justify-between text-xs py-1 border-b border-border last:border-0">
                <span className="text-text-secondary capitalize">{k.replace(/_/g, " ")}</span>
                <span className="font-mono text-text-primary text-right max-w-[60%]">
                  {typeof v === "boolean" ? (v ? "Yes" : "No") : String(v)}
                </span>
              </div>
            ))}
          </div>

          {/* Resolution */}
          {module.resolution && (
            <div className={cn(
              "rounded border p-3 text-xs",
              module.result === "fail"
                ? "bg-error-bg border-error-border text-error-DEFAULT"
                : "bg-warning-bg border-warning-border text-warning-DEFAULT"
            )}>
              <p className="font-semibold mb-1">
                {module.result === "fail" ? "Required Action" : "Recommended Action"}
              </p>
              <p className="leading-relaxed">{module.resolution}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ComplianceShieldPanel({ report }: { report: ShieldReport }) {
  const OverallIcon =
    report.overall === "pass" ? ShieldCheck :
    report.overall === "hold" ? ShieldAlert : ShieldX;

  const headerBg =
    report.overall === "pass" ? "bg-success-bg border-success-border" :
    report.overall === "hold" ? "bg-warning-bg border-warning-border" :
    "bg-error-bg border-error-border";

  const headerText =
    report.overall === "pass" ? "text-success-DEFAULT" :
    report.overall === "hold" ? "text-warning-DEFAULT" :
    "text-error-DEFAULT";

  return (
    <div className="card overflow-hidden">
      {/* Header */}
      <div className={cn("flex items-center justify-between px-4 py-3 border-b", headerBg)}>
        <div className="flex items-center gap-2">
          <OverallIcon className={cn("w-4 h-4", headerText)} />
          <span className="text-xs font-semibold text-text-primary">Compliance Shield</span>
        </div>
        <div className="flex items-center gap-2">
          {report.penalty_risk_detected && (
            <span className="badge badge-fail">PENALTY RISK</span>
          )}
          <span className={cn("badge", headerText,
            report.overall === "pass" ? "badge-pass" :
            report.overall === "hold" ? "badge-hold" : "badge-fail"
          )}>
            {report.overall === "pass" ? "COMPLIANT" :
             report.overall === "hold" ? "REVIEW REQUIRED" :
             "COMPLIANCE FAILURE"}
          </span>
        </div>
      </div>

      {/* Modules */}
      <div>
        {report.modules.map((m) => (
          <ModuleRow key={m.module} module={m} />
        ))}
      </div>
    </div>
  );
}
