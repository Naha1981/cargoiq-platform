"use client";
import { useQuery } from "@tanstack/react-query";
import { BarChart2 } from "lucide-react";
import { analyticsApi } from "@/lib/api";
import { TopNav } from "@/components/layout/TopNav";
import { Skeleton } from "@/components/ui/LoadingSkeleton";

export default function AnalyticsPage() {
  const { data: roi, isLoading } = useQuery({ queryKey: ["roi"], queryFn: analyticsApi.roi });

  return (
    <div className="flex flex-col min-h-full">
      <TopNav breadcrumbs={[{ label: "Analytics" }]} />
      <div className="p-6">
        <div className="flex items-center gap-2 mb-6">
          <BarChart2 className="w-5 h-5 text-text-tertiary" />
          <h1 className="text-xl font-semibold text-text-primary">Analytics & ROI</h1>
        </div>
        {isLoading ? <Skeleton className="h-48" /> : roi && (
          <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
            {[
              { label: "Shipments Processed", value: roi.total_shipments_processed, color: "text-text-primary" },
              { label: "Hours Saved",          value: `${roi.time_saved_hours}h`,     color: "text-success-DEFAULT" },
              { label: "Labour Cost Saved",    value: `R${roi.labour_cost_saved_zar?.toLocaleString("en-ZA")}`, color: "text-success-DEFAULT" },
              { label: "Penalties Prevented",  value: `R${roi.sars_penalties_prevented_zar?.toLocaleString("en-ZA")}`, color: "text-error-DEFAULT" },
              { label: "Errors Prevented",     value: roi.errors_prevented,           color: "text-error-DEFAULT" },
              { label: "Total Value Delivered",value: `R${roi.total_value_delivered_zar?.toLocaleString("en-ZA")}`, color: "text-accent" },
            ].map(({ label, value, color }) => (
              <div key={label} className="card p-5">
                <p className="section-label mb-2">{label}</p>
                <p className={`text-3xl font-mono font-medium ${color}`}>{value}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
