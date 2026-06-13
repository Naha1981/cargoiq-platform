"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { CheckCircle2, Circle, ArrowRight, Sparkles } from "lucide-react";
import { apiClient } from "@/lib/api";
import { cn } from "@/lib/utils";

export function OnboardingChecklist() {
  const { data, isLoading } = useQuery({
    queryKey: ["onboarding-status"],
    queryFn: () => apiClient.get("/onboarding/status"),
    staleTime: 30_000,
  });

  if (isLoading || !data) return null;
  if (data.all_required_complete) return null; // fully onboarded — get out of the way

  const pct = Math.round((data.required_completed / data.required_total) * 100);

  return (
    <div className="card overflow-hidden">
      <div className="card-header">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-accent" />
          <h3 className="text-xs font-semibold">Get Started with CargoIQ</h3>
        </div>
        <span className="text-2xs font-mono text-text-tertiary">
          {data.required_completed}/{data.required_total} steps complete
        </span>
      </div>

      <div className="px-5 pt-4">
        <div className="w-full bg-subtle rounded-full h-1.5">
          <div
            className="h-1.5 rounded-full bg-accent transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      <div className="divide-y divide-border">
        {data.steps.map((step: any) => (
          <Link
            key={step.id}
            href={step.action_path}
            className="flex items-start gap-3 px-5 py-4 hover:bg-subtle transition-colors group"
          >
            {step.complete ? (
              <CheckCircle2 className="w-4 h-4 text-success-DEFAULT flex-shrink-0 mt-0.5" />
            ) : (
              <Circle className="w-4 h-4 text-text-tertiary flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className={cn(
                  "text-xs font-medium",
                  step.complete ? "text-text-tertiary line-through" : "text-text-primary"
                )}>
                  {step.title}
                </p>
                {step.optional && (
                  <span className="text-2xs text-text-tertiary border border-border rounded px-1.5 py-0.5">optional</span>
                )}
                {step.progress && !step.complete && (
                  <span className="text-2xs font-mono text-accent">{step.progress}</span>
                )}
              </div>
              {!step.complete && (
                <p className="text-2xs text-text-secondary mt-1 leading-relaxed">{step.description}</p>
              )}
            </div>
            {!step.complete && (
              <ArrowRight className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0 mt-1 group-hover:text-accent transition-colors" />
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
