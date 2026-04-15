"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ListChecks, LogOut } from "lucide-react";
import { logoutAction } from "@/app/admin/actions";

interface SidebarProps {
  username: string;
}

export function Sidebar({ username }: SidebarProps) {
  const pathname = usePathname() ?? "";
  const isLeads = pathname.startsWith("/admin/leads");

  return (
    <aside
      className="flex flex-col w-[220px] shrink-0 h-screen sticky top-0 bg-[var(--surface-1)] border-r border-[var(--surface-3)]"
      aria-label="Admin navigation"
    >
      <div className="px-4 py-5 border-b border-[var(--surface-3)]">
        <div className="text-sm font-semibold text-[var(--text-primary)]">
          BetterSite
        </div>
        <div className="text-xs text-[var(--text-secondary)] mt-0.5">Admin</div>
      </div>

      <nav className="flex-1 py-2">
        <Link
          href="/admin/leads"
          aria-current={isLeads ? "page" : undefined}
          className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
            isLeads
              ? "bg-[var(--surface-2)] text-[var(--text-primary)] font-medium"
              : "text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
          }`}
        >
          <ListChecks size={16} aria-hidden="true" />
          <span>Leads</span>
        </Link>
      </nav>

      <div className="p-4 border-t border-[var(--surface-3)]">
        <div className="text-xs text-[var(--text-tertiary)] mb-2">
          Signed in as
        </div>
        <div className="text-sm font-medium text-[var(--text-primary)] mb-3 truncate">
          {username}
        </div>
        <form action={logoutAction}>
          <button
            type="submit"
            className="flex items-center gap-2 w-full px-2 py-1.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)] rounded-md transition-colors"
          >
            <LogOut size={14} aria-hidden="true" />
            Log out
          </button>
        </form>
      </div>
    </aside>
  );
}
