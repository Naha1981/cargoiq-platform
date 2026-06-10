"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, ListTodo, Shield, BarChart2,
  Settings, Package, ChevronLeft, ChevronRight,
  LogOut, Building2, Inbox, Globe
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const NAV_ITEMS = [
  { href: "/dashboard",   icon: LayoutDashboard, label: "Dashboard" },
  { href: "/inbox",       icon: Inbox,           label: "Email Inbox" },
  { href: "/portals",     icon: Globe,           label: "Portal Agents" },
  { href: "/queue",       icon: ListTodo,        label: "Shipment Queue" },
  { href: "/compliance",  icon: Shield,          label: "Compliance" },
  { href: "/analytics",   icon: BarChart2,       label: "Analytics" },
  { href: "/settings",    icon: Settings,        label: "Settings" },
];

interface SidebarProps {
  orgName?: string;
  userInitials?: string;
}

export function Sidebar({ orgName = "CargoIQ", userInitials = "U" }: SidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "flex flex-col h-screen sticky top-0 bg-nav transition-all duration-200 border-r border-nav-border flex-shrink-0",
        collapsed ? "w-14" : "w-60"
      )}
    >
      {/* Logo */}
      <div className={cn(
        "flex items-center border-b border-nav-border",
        collapsed ? "h-14 justify-center px-0" : "h-14 px-4 gap-2"
      )}>
        <Package className="w-5 h-5 text-accent flex-shrink-0" />
        {!collapsed && (
          <span className="font-mono text-base font-semibold text-text-inverse tracking-tight">
            Cargo<span className="text-accent">IQ</span>
          </span>
        )}
      </div>

      {/* Org name */}
      {!collapsed && (
        <div className="px-4 py-3 border-b border-nav-border">
          <div className="flex items-center gap-2">
            <Building2 className="w-3.5 h-3.5 text-nav-text-muted flex-shrink-0" />
            <span className="text-2xs text-nav-text-muted truncate">{orgName}</span>
          </div>
        </div>
      )}

      {/* Nav */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 px-3 h-9 rounded transition-colors duration-100",
                collapsed && "justify-center px-0",
                active
                  ? "bg-nav-active border-l-2 border-l-accent text-text-inverse"
                  : "text-nav-text hover:bg-nav-hover"
              )}
              title={collapsed ? label : undefined}
            >
              <Icon className={cn("w-4 h-4 flex-shrink-0", active ? "text-accent" : "text-nav-text-muted")} />
              {!collapsed && (
                <span className="text-xs font-medium truncate">{label}</span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Bottom: collapse + logout */}
      <div className="border-t border-nav-border p-2 space-y-0.5">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 px-3 h-9 w-full rounded text-nav-text hover:bg-nav-hover transition-colors"
          title={collapsed ? "Expand" : "Collapse"}
        >
          {collapsed
            ? <ChevronRight className="w-4 h-4 mx-auto text-nav-text-muted" />
            : <>
                <ChevronLeft className="w-4 h-4 text-nav-text-muted" />
                <span className="text-xs">Collapse</span>
              </>
          }
        </button>
        <Link
          href="/auth/login"
          className="flex items-center gap-3 px-3 h-9 w-full rounded text-nav-text hover:bg-nav-hover transition-colors"
        >
          <LogOut className="w-4 h-4 text-nav-text-muted flex-shrink-0" />
          {!collapsed && <span className="text-xs">Sign Out</span>}
        </Link>
      </div>
    </aside>
  );
}
