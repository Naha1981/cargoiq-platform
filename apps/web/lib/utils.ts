import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(d: string | Date | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("en-ZA", {
    day: "2-digit", month: "short", year: "numeric"
  });
}

export function formatDateTime(d: string | Date | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleString("en-ZA", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
}

export function formatCurrency(amount: number | null, currency = "USD"): string {
  if (amount == null) return "—";
  return new Intl.NumberFormat("en-ZA", {
    style: "currency", currency, minimumFractionDigits: 2
  }).format(amount);
}

export function formatWeight(weight: number | null, unit = "KGS"): string {
  if (weight == null) return "—";
  return `${weight.toLocaleString("en-ZA")} ${unit}`;
}

export function confidenceColor(confidence: string | null): string {
  switch (confidence) {
    case "high":   return "text-success-DEFAULT";
    case "medium": return "text-warning-DEFAULT";
    case "low":    return "text-error-DEFAULT";
    default:       return "text-text-tertiary";
  }
}

export function shieldColor(status: string | null): string {
  switch (status) {
    case "pass": return "text-success-DEFAULT bg-success-bg border-success-border";
    case "hold": return "text-warning-DEFAULT bg-warning-bg border-warning-border";
    case "fail": return "text-error-DEFAULT bg-error-bg border-error-border";
    default:     return "text-text-tertiary bg-subtle border-border";
  }
}

export function statusColor(status: string | null): string {
  switch (status) {
    case "approved":
    case "in_cargowise":    return "text-success-DEFAULT bg-success-bg border-success-border";
    case "review_required": return "text-warning-DEFAULT bg-warning-bg border-warning-border";
    case "rejected":
    case "error":           return "text-error-DEFAULT bg-error-bg border-error-border";
    case "extracting":
    case "shield_running":  return "text-info-DEFAULT bg-info-bg border-info-border";
    default:                return "text-text-tertiary bg-subtle border-border";
  }
}

export function truncate(str: string | null, n = 40): string {
  if (!str) return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}
