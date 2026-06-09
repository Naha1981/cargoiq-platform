import { cn, shieldColor, statusColor, confidenceColor } from "@/lib/utils";

type BadgeVariant = "shield" | "status" | "confidence" | "custom";

interface StatusBadgeProps {
  value: string | null;
  variant?: BadgeVariant;
  className?: string;
}

const LABELS: Record<string, string> = {
  pass:             "PASS",
  hold:             "REVIEW",
  fail:             "FAIL",
  pending:          "PENDING",
  extracting:       "EXTRACTING",
  extracted:        "EXTRACTED",
  shield_running:   "CHECKING",
  review_required:  "REVIEW REQUIRED",
  approved:         "APPROVED",
  rejected:         "REJECTED",
  pushing_to_cw:    "SENDING TO CW",
  in_cargowise:     "IN CARGOWISE",
  error:            "ERROR",
  high:             "HIGH",
  medium:           "MEDIUM",
  low:              "LOW",
  active:           "ACTIVE",
  suspended:        "SUSPENDED",
  inactive:         "INACTIVE",
  unverified:       "UNVERIFIED",
};

export function StatusBadge({ value, variant = "status", className }: StatusBadgeProps) {
  if (!value) return <span className="text-text-tertiary text-2xs">—</span>;

  const label = LABELS[value] || value.toUpperCase().replace(/_/g, " ");

  let colorClass = "";
  if (variant === "shield")     colorClass = shieldColor(value);
  else if (variant === "status") colorClass = statusColor(value);
  else if (variant === "confidence") colorClass = cn(
    confidenceColor(value),
    value === "high"   ? "bg-success-bg border-success-border" :
    value === "medium" ? "bg-warning-bg border-warning-border" :
                         "bg-error-bg   border-error-border"
  );

  return (
    <span className={cn("badge", colorClass, className)}>
      {label}
    </span>
  );
}
