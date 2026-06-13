"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import {
  Search, Filter, RefreshCw, CheckCircle, XCircle,
  AlertTriangle, ChevronRight, Upload, Clock
} from "lucide-react";
import { shipmentsApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { TableSkeleton, Skeleton } from "@/components/ui/LoadingSkeleton";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDateTime, truncate, cn } from "@/lib/utils";
import toast from "react-hot-toast";

const STATUS_FILTERS = [
  { value: "",                 label: "All" },
  { value: "pending",          label: "Pending" },
  { value: "review_required",  label: "Review Required" },
  { value: "approved",         label: "Approved" },
  { value: "in_cargowise",     label: "In CargoWise" },
  { value: "rejected",         label: "Rejected" },
  { value: "error",            label: "Error" },
];

// CustomsStop risk dot — 1-5 score from the Compliance Shield,
// collapsed into a coloured dot with a hover tooltip showing the
// single most actionable fix.
function RiskDot({ riskScore }: { riskScore?: { score: number; label: string; top_issue?: { module: string; resolution: string } } }) {
  if (!riskScore) return <span className="text-2xs text-text-tertiary">—</span>;

  const colorMap: Record<string, string> = {
    clear:  "bg-success-DEFAULT",
    low:    "bg-info-DEFAULT",
    medium: "bg-warning-DEFAULT",
    high:   "bg-error-DEFAULT",
  };

  const tooltip = riskScore.top_issue
    ? `Risk ${riskScore.score}/5 (${riskScore.label}) — ${riskScore.top_issue.resolution}`
    : `Risk ${riskScore.score}/5 (${riskScore.label})`;

  return (
    <div className="flex items-center gap-1.5" title={tooltip}>
      <span className={cn("w-2.5 h-2.5 rounded-full flex-shrink-0", colorMap[riskScore.label] || "bg-text-tertiary")} />
      <span className="text-2xs font-mono text-text-tertiary">{riskScore.score}/5</span>
    </div>
  );
}

export default function QueuePage() {
  const router = useRouter();
  const qc = useQueryClient();
  const [status, setStatus]   = useState("");
  const [search, setSearch]   = useState("");
  const [page, setPage]       = useState(1);
  const LIMIT = 25;

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ["shipments", { status, search, page }],
    queryFn: () => shipmentsApi.list({ status, search, page, limit: LIMIT }),
    placeholderData: prev => prev,
  });

  const approveMut = useMutation({
    mutationFn: (id: string) => shipmentsApi.approve(id),
    onSuccess: (_, id) => {
      toast.success("Shipment approved — queued for CargoWise");
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
    onError: (err: any) => toast.error(err.message || "Approval failed"),
  });

  const rejectMut = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      shipmentsApi.reject(id, reason),
    onSuccess: () => {
      toast.success("Shipment rejected");
      qc.invalidateQueries({ queryKey: ["shipments"] });
    },
  });

  const shipments = data?.data || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div className="flex flex-col min-h-full">
      <TopNav
        breadcrumbs={[{ label: "Shipment Queue" }]}
        actions={
          <button
            className="btn btn-primary btn-sm"
            onClick={() => router.push("/queue/upload")}
          >
            <Upload className="w-3.5 h-3.5" />
            Upload Document
          </button>
        }
      />

      <div className="p-6">
        {/* Filters */}
        <div className="flex items-center gap-3 mb-4 flex-wrap">
          {/* Status filter tabs */}
          <div className="flex items-center bg-surface border border-border rounded overflow-hidden">
            {STATUS_FILTERS.map(f => (
              <button
                key={f.value}
                onClick={() => { setStatus(f.value); setPage(1); }}
                className={cn(
                  "px-3 h-8 text-xs font-medium border-r border-border last:border-r-0 transition-colors",
                  status === f.value
                    ? "bg-accent text-text-inverse"
                    : "text-text-secondary hover:bg-subtle"
                )}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
            <input
              type="text"
              placeholder="Search reference, shipper, consignee…"
              value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="form-input pl-9 w-72 h-8 text-xs"
            />
          </div>

          <button
            onClick={() => qc.invalidateQueries({ queryKey: ["shipments"] })}
            className="btn btn-secondary btn-sm"
            disabled={isFetching}
          >
            <RefreshCw className={cn("w-3.5 h-3.5", isFetching && "animate-spin")} />
            Refresh
          </button>

          <span className="ml-auto text-xs text-text-tertiary font-mono">
            {total.toLocaleString("en-ZA")} record{total !== 1 ? "s" : ""}
          </span>
        </div>

        {/* Table */}
        {isLoading ? (
          <TableSkeleton rows={8} cols={8} />
        ) : shipments.length === 0 ? (
          <div className="card">
            <EmptyState
              icon={ListTodo_}
              title="No shipments found"
              description={status || search
                ? "Try adjusting your filters"
                : "Upload a document to start processing shipments"
              }
              action={
                <button className="btn btn-primary btn-sm" onClick={() => router.push("/queue/upload")}>
                  Upload First Document
                </button>
              }
            />
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table>
                <thead>
                  <tr>
                    <th>Reference</th>
                    <th>Shipper</th>
                    <th>Consignee</th>
                    <th>Route</th>
                    <th>Type</th>
                    <th>Confidence</th>
                    <th>Shield</th>
                    <th title="CustomsStop risk — 1 (clear) to 5 (certain hold)">Risk</th>
                    <th>Status</th>
                    <th>Received</th>
                    <th style={{ width: 96 }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {shipments.map((s: any) => (
                    <tr
                      key={s.id}
                      className="cursor-pointer"
                      onClick={() => router.push(`/shipments/${s.id}`)}
                    >
                      <td>
                        <span className="font-mono text-xs text-accent">
                          {s.reference || "—"}
                        </span>
                      </td>
                      <td className="text-xs">{truncate(s.shipper_name, 28)}</td>
                      <td className="text-xs">{truncate(s.consignee_name, 28)}</td>
                      <td>
                        <span className="font-mono text-2xs text-text-secondary">
                          {s.origin_port || "?"} → {s.destination_port || "?"}
                        </span>
                      </td>
                      <td>
                        <span className="text-2xs text-text-tertiary uppercase">
                          {s.shipment_type?.replace("_", " ") || "—"}
                        </span>
                      </td>
                      <td>
                        <StatusBadge value={s.overall_confidence} variant="confidence" />
                      </td>
                      <td>
                        <StatusBadge value={s.shield_status} variant="shield" />
                      </td>
                      <td>
                        <RiskDot riskScore={s.shield_results?.risk_score} />
                      </td>
                      <td>
                        <StatusBadge value={s.status} variant="status" />
                      </td>
                      <td className="font-mono text-2xs text-text-tertiary whitespace-nowrap">
                        {formatDateTime(s.created_at)}
                      </td>
                      <td onClick={e => e.stopPropagation()}>
                        <div className="flex items-center gap-1">
                          {s.status === "review_required" && (
                            <>
                              <button
                                className="btn btn-sm p-1.5 text-success-DEFAULT hover:bg-success-bg"
                                title="Approve"
                                onClick={() => approveMut.mutate(s.id)}
                                disabled={approveMut.isPending}
                              >
                                <CheckCircle className="w-4 h-4" />
                              </button>
                              <button
                                className="btn btn-sm p-1.5 text-error-DEFAULT hover:bg-error-bg"
                                title="Reject"
                                onClick={() => {
                                  const reason = window.prompt("Rejection reason:");
                                  if (reason) rejectMut.mutate({ id: s.id, reason });
                                }}
                                disabled={rejectMut.isPending}
                              >
                                <XCircle className="w-4 h-4" />
                              </button>
                            </>
                          )}
                          <button
                            className="btn btn-sm p-1.5 text-text-tertiary hover:text-text-primary"
                            title="View detail"
                            onClick={() => router.push(`/shipments/${s.id}`)}
                          >
                            <ChevronRight className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-border bg-subtle">
              <span className="text-2xs font-mono text-text-tertiary">
                Page {page} of {totalPages} · {total} records
              </span>
              <div className="flex items-center gap-1">
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </button>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Needed because ListTodo is already imported above
function ListTodo_(props: any) {
  return <ListTodo {...props} />;
}
