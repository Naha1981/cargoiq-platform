"use client";
import { Bell, Search, Menu } from "lucide-react";
import { useState } from "react";

interface TopNavProps {
  breadcrumbs?: { label: string; href?: string }[];
  title?: string;
  actions?: React.ReactNode;
}

export function TopNav({ breadcrumbs = [], title, actions }: TopNavProps) {
  const [searchValue, setSearchValue] = useState("");

  return (
    <header className="sticky top-0 z-40 h-14 bg-surface border-b border-border flex items-center justify-between px-6 gap-4">
      {/* Left: breadcrumb */}
      <div className="flex items-center gap-2 min-w-0">
        {breadcrumbs.map((crumb, i) => (
          <span key={i} className="flex items-center gap-2">
            {i > 0 && <span className="text-border-strong text-xs">/</span>}
            <span className={i === breadcrumbs.length - 1
              ? "text-xs font-semibold text-text-primary truncate"
              : "text-xs text-text-tertiary truncate"
            }>
              {crumb.label}
            </span>
          </span>
        ))}
      </div>

      {/* Right: search + notifications */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-tertiary" />
          <input
            type="text"
            placeholder="Search shipments…"
            value={searchValue}
            onChange={e => setSearchValue(e.target.value)}
            className="form-input pl-9 w-56 h-8 text-xs"
          />
        </div>
        <button className="relative w-8 h-8 flex items-center justify-center rounded hover:bg-subtle transition-colors">
          <Bell className="w-4 h-4 text-text-secondary" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-error-DEFAULT rounded-full" />
        </button>
        {actions}
      </div>
    </header>
  );
}
