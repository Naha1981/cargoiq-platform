"use client";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import {
  ArrowLeft, CheckCircle, XCircle, RefreshCw,
  FileText, Shield, Package, Clock, AlertTriangle, RotateCcw
} from "lucide-react";
import { shipmentsApi, complianceApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ComplianceShieldPanel } from "@/components/ui/ComplianceShieldPanel";
import { Skeleton } from "@/components/ui/LoadingSkeleton";
import {
  formatDate, formatDateTime, formatCurrency,
  formatWeight, truncate, cn
} from "@/lib/utils";
import toast from "react-hot-toast";

// ── Field Row ───────────────────────────────────────────────
function FieldRow({
  label, value, mono = false, confidence
}: {
  label: string; value: any; mono?: boolean; confidence?: string;
}) {
  const display = value == null || value === "" ? "—" : String(value);
  const confColor = confidence === "high"   ? "border-l-success-DEFAULT" :
                    confidence === "medium" ? "border-l-warning-DEFAULT" :
                    confidence === "low"    ? "border-l-error-DEFAULT" : "";

  return (
    <div className={cn(
      "flex justify-between items-start py-2.5 border-b border-border last:border-0 gap-4",
      confidence && confidence !== "high" && `border-l-2 pl-3 ${confColor}`
    )}>
      <span className="text-xs text-text-secondary flex-shrink-0 w-40">{label}</span>
      <span className={cn(
        "text-xs text-text-primary text-right leading-relaxed",
        mono && "font-mono",
        display === "—" && "text-text-tertiary"
      )}>
        {display}
      </span>
    </div>
  );
}

// ── Section Card ────────────────────────────────────────────
function Section({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode;
}) {
  return (
    <div className="card overflow-hidden">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-text-tertiary" />
          <h3 className="text-xs font-semibold text-text-primary">{title}</h3>
        </div>
      </div>
      <div className="divide-y divide-border px-4">{children}</div>
    </div>
  );
}

// ── Main Shipment Detail Page ───────────────────────────────
export default function ShipmentDetailPage() {
  const params  = useParams();
  const router  = useRouter();
  const qc      = useQueryClient();
  const id      = params.id as string;

  const { data: shipment, isLoading } = useQuery({
    queryKey: ["shipment", id],
    queryFn:  () => shipmentsApi.get(id),
  });

  const approveMut = useMutation({
    mutationFn: (acknowledgedRisks: boolean) =>
      shipmentsApi.approve(id, undefined, acknowledgedRisks),
    onSuccess: () => {
      toast.success("Approved — queued for CargoWise execution");
      qc.invalidateQueries({ queryKey: ["shipment", id] });
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
    onError: (err: any) => toast.error(err.message || "Approval failed"),
  });

  const rejectMut = useMutation({
    mutationFn: (reason: string) => shipmentsApi.reject(id, reason),
    onSuccess: () => {
      toast.success("Shipment rejected");
      qc.invalidateQueries({ queryKey: ["shipment", id] });
    },
  });

  const reAuditMut = useMutation({
    mutationFn: () => complianceApi.audit(id),
    onSuccess: () => {
      toast.success("Compliance re-audit complete");
      qc.invalidateQueries({ queryKey: ["shipment", id] });
    },
    onError: () => toast.error("Re-audit failed"),
  });

  const handleApprove = () => {
    const shieldStatus = shipment?.shield_status;
    if (shieldStatus === "fail") {
      const ok = window.confirm(
        "⚠️ This shipment has compliance FAILURES.\n\n" +
        "Approving will create an audit record that you overrode compliance checks.\n\n" +
        "Are you sure you want to proceed?"
      );
      if (ok) approveMut.mutate(true);
    } else {
      approveMut.mutate(false);
    }
  };

  const handleReject = () => {
    const reason = window.prompt("Enter rejection reason (required):");
    if (reason?.trim()) rejectMut.mutate(reason.trim());
  };

  if (isLoading) {
    return (
      <div className="flex flex-col min-h-full">
        <TopNav breadcrumbs={[
          { label: "Queue", href: "/queue" },
          { label: "Loading…" }
        ]} />
        <div className="p-6 grid grid-cols-3 gap-5">
          <div className="col-span-2 space-y-4">
            {[1,2,3].map(i => <Skeleton key={i} className="h-48 w-full" />)}
          </div>
          <Skeleton className="h-96 w-full" />
        </div>
      </div>
    );
  }

  if (!shipment) {
    return (
      <div className="p-6 text-sm text-text-secondary">Shipment not found.</div>
    );
  }

  const s = shipment;
  const conf = s.confidence_scores || {};
  const canApprove = !["approved","in_cargowise","rejected","extracting","shield_running"].includes(s.status);
  const canReject  = !["rejected","in_cargowise","extracting"].includes(s.status);

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[
          { label: "Queue", href: "/queue" },
          { label: s.reference || s.id.slice(0,8) }
        ]}
        actions={
          <div className="flex items-center gap-2">
            {canReject && (
              <button
                className="btn btn-danger btn-sm"
                onClick={handleReject}
                disabled={rejectMut.isPending}
              >
                <XCircle className="w-3.5 h-3.5" />
                Reject
              </button>
            )}
            {canApprove && (
              <button
                className="btn btn-primary btn-sm"
                onClick={handleApprove}
                disabled={approveMut.isPending}
              >
                <CheckCircle className="w-3.5 h-3.5" />
                {approveMut.isPending ? "Approving…" : "Approve → CargoWise"}
              </button>
            )}
          </div>
        }
      />

      <div className="p-6">
        {/* Header row */}
        <div className="flex items-center gap-4 mb-5">
          <button
            className="btn btn-ghost btn-sm p-1.5"
            onClick={() => router.back()}
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-semibold text-text-primary">
                {s.reference || "Processing…"}
              </h1>
              <StatusBadge value={s.status}         variant="status" />
              <StatusBadge value={s.shield_status}  variant="shield" />
              <StatusBadge value={s.overall_confidence} variant="confidence" />
            </div>
            <p className="text-xs text-text-tertiary mt-1 font-mono">
              {s.id} · Received {formatDateTime(s.created_at)}
            </p>
          </div>

          {/* Re-audit button */}
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => reAuditMut.mutate()}
            disabled={reAuditMut.isPending}
            title="Re-run Compliance Shield"
          >
            <RotateCcw className={cn("w-3.5 h-3.5", reAuditMut.isPending && "animate-spin")} />
            Re-audit
          </button>
        </div>

        {/* Penalty risk alert */}
        {s.shield_results?.penalty_risk_detected && (
          <div className="flex items-start gap-3 p-4 bg-error-bg border border-error-border rounded mb-5">
            <AlertTriangle className="w-4 h-4 text-error-DEFAULT flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-error-DEFAULT">SARS Penalty Risk Detected</p>
              <p className="text-xs text-text-primary mt-0.5">
                This shipment has compliance issues that could trigger SARS penalties under
                Section 91. Review all HOLD/FAIL modules before approving.
              </p>
            </div>
          </div>
        )}

        {/* AI flags alert */}
        {(s.ai_flags?.sars_query_flag || s.ai_flags?.description_change_flag) && (
          <div className="flex items-start gap-3 p-4 bg-warning-bg border border-warning-border rounded mb-5">
            <AlertTriangle className="w-4 h-4 text-warning-DEFAULT flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-semibold text-warning-DEFAULT">AI Flags Detected</p>
              <div className="text-xs text-text-primary mt-1 space-y-0.5">
                {s.ai_flags.sars_query_flag && <p>• Previous SARS query detected on this cargo</p>}
                {s.ai_flags.description_change_flag && <p>• Description appears to differ from prior shipment</p>}
                {s.ai_flags.missing_invoice && <p>• Commercial invoice not found</p>}
                {s.ai_flags.missing_packing_list && <p>• Packing list not found</p>}
              </div>
            </div>
          </div>
        )}

        {/* Main grid */}
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">

          {/* Left: extracted fields */}
          <div className="xl:col-span-2 space-y-5">

            <Section title="Parties" icon={Package}>
              <FieldRow label="Shipper"    value={s.shipper_name}    confidence={conf.shipper_name} />
              <FieldRow label="Address"    value={s.shipper_address} />
              <FieldRow label="Consignee"  value={s.consignee_name}  confidence={conf.consignee_name} />
              <FieldRow label="Address"    value={s.consignee_address} />
              <FieldRow label="Notify Party" value={s.notify_party} />
            </Section>

            <Section title="Routing" icon={Package}>
              <FieldRow label="Shipment Type"   value={s.shipment_type?.replace(/_/g," ")} confidence={conf.shipment_type} />
              <FieldRow label="Origin Port"     value={s.origin_port}       mono confidence={conf.origin_port} />
              <FieldRow label="Origin Country"  value={s.origin_country}    mono />
              <FieldRow label="Destination"     value={s.destination_port}  mono confidence={conf.destination_port} />
              <FieldRow label="ETD"             value={formatDate(s.etd)} />
              <FieldRow label="ETA"             value={formatDate(s.eta)} />
              <FieldRow label="Vessel / Flight" value={s.vessel_or_flight} />
              <FieldRow label="AWB / B/L"       value={s.awb_or_bl_number}  mono confidence={conf.awb_or_bl_number} />
            </Section>

            <Section title="Cargo & Commercial" icon={FileText}>
              <FieldRow label="Description"    value={s.cargo_description}  confidence={conf.cargo_description} />
              <FieldRow label="HS Code"        value={s.hs_code_primary}    mono confidence={conf.hs_code_primary} />
              <FieldRow label="Gross Weight"   value={formatWeight(s.gross_weight, s.weight_unit)} confidence={conf.gross_weight} />
              <FieldRow label="Net Weight"     value={formatWeight(s.net_weight, s.weight_unit)} />
              <FieldRow label="Packages"       value={s.number_of_packages} />
              <FieldRow label="Incoterms"      value={s.incoterms}          mono confidence={conf.incoterms} />
              <FieldRow label="Invoice No."    value={s.invoice_number}     mono confidence={conf.invoice_number} />
              <FieldRow label="Invoice Value"  value={formatCurrency(s.invoice_value, s.currency)} confidence={conf.invoice_value} />
            </Section>

            {/* Line items */}
            {s.line_items?.length > 0 && (
              <div className="card overflow-hidden">
                <div className="card-header">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-text-tertiary" />
                    <h3 className="text-xs font-semibold text-text-primary">
                      Cargo Line Items ({s.line_items.length})
                    </h3>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>HS Code</th>
                        <th>Description</th>
                        <th>Qty</th>
                        <th>Weight</th>
                        <th>Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.line_items.map((item: any) => (
                        <tr key={item.id}>
                          <td className="font-mono text-2xs text-text-tertiary">{item.line_number}</td>
                          <td className="font-mono text-xs">{item.hs_code || "—"}</td>
                          <td className="text-xs max-w-[200px] truncate">{item.description || "—"}</td>
                          <td className="font-mono text-xs">{item.quantity ? `${item.quantity} ${item.unit || ""}` : "—"}</td>
                          <td className="font-mono text-xs">{item.total_weight ? `${item.total_weight} ${s.weight_unit || "KGS"}` : "—"}</td>
                          <td className="font-mono text-xs">{item.total_value ? formatCurrency(item.total_value, item.currency || s.currency) : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Documents */}
            {s.documents?.length > 0 && (
              <div className="card overflow-hidden">
                <div className="card-header">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-text-tertiary" />
                    <h3 className="text-xs font-semibold text-text-primary">
                      Source Documents ({s.documents.length})
                    </h3>
                  </div>
                </div>
                <div className="divide-y divide-border">
                  {s.documents.map((doc: any) => (
                    <div key={doc.id} className="flex items-center justify-between px-4 py-3">
                      <div className="flex items-center gap-2">
                        <FileText className="w-4 h-4 text-text-tertiary" />
                        <span className="text-xs text-text-primary">{doc.filename}</span>
                      </div>
                      <StatusBadge value={doc.doc_type} variant="custom" />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right: compliance shield */}
          <div className="space-y-5">
            {s.shield_results?.modules ? (
              <ComplianceShieldPanel report={s.shield_results} />
            ) : (
              <div className="card p-6 text-center">
                <Shield className="w-8 h-8 text-text-tertiary mx-auto mb-2" />
                <p className="text-xs text-text-tertiary">
                  {s.status === "extracting" || s.status === "shield_running"
                    ? "Compliance check in progress…"
                    : "No compliance data yet"}
                </p>
              </div>
            )}

            {/* Processing metadata */}
            <div className="card overflow-hidden">
              <div className="card-header">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-text-tertiary" />
                  <h3 className="text-xs font-semibold text-text-primary">Processing</h3>
                </div>
              </div>
              <div className="divide-y divide-border px-4">
                <FieldRow label="Source"           value={s.source} />
                <FieldRow label="Confidence Score" value={s.confidence_percentage ? `${s.confidence_percentage}%` : "—"} mono />
                <FieldRow label="Reviewed By"      value={s.reviewed_by ? "Operator" : "—"} />
                <FieldRow label="Reviewed At"      value={formatDateTime(s.reviewed_at)} />
                <FieldRow label="Notes"            value={s.review_notes} />
                {s.cargowise_job_id && (
                  <FieldRow label="CW Job ID" value={s.cargowise_job_id} mono />
                )}
              </div>
            </div>

            {/* Extraction notes */}
            {s.extracted_fields?.extraction_notes && (
              <div className="card p-4">
                <p className="section-label mb-2">AI Extraction Notes</p>
                <p className="text-xs text-text-secondary leading-relaxed">
                  {s.extracted_fields.extraction_notes}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
