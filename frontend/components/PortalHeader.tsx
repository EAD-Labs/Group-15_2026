"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

/** Shared portal chrome. The accent stripe differs so the two never blur. */
export function PortalHeader({
  user, tabs, right,
}: {
  user: SessionUser;
  tabs?: { href: string; label: string; active: boolean }[];
  right?: React.ReactNode;
}) {
  const router = useRouter();
  const isResearcher = user.role === "researcher";

  return (
    <header className="sticky top-0 z-20 border-b border-[var(--color-margin-edge)] bg-white">
      <div className="mx-auto flex max-w-5xl items-center gap-3 px-6 py-3">
        <Link href={isResearcher ? "/researcher" : "/student"} className="flex items-center gap-2.5">
          <div
            className="flex h-6 w-6 items-center justify-center rounded"
            style={{ background: isResearcher ? "var(--color-ink)" : "var(--color-accent)" }}
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2"
                 strokeLinecap="round" strokeLinejoin="round">
              {isResearcher ? (
                <><circle cx="11" cy="11" r="7" /><path d="M21 21l-4.3-4.3" /></>
              ) : (
                <><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" /></>
              )}
            </svg>
          </div>
          <span className="text-[13px] font-semibold tracking-tight text-[var(--color-ink)]">
            Story Studio
          </span>
        </Link>

        <span className="rounded px-1.5 py-0.5 font-mono text-[9.5px] uppercase tracking-wider"
              style={{
                background: isResearcher ? "var(--color-margin-deep)" : "var(--color-accent-soft)",
                color: isResearcher ? "var(--color-ink-soft)" : "var(--color-accent)",
              }}>
          {isResearcher ? "researcher portal" : "student portal"}
        </span>

        {tabs && (
          <nav className="ml-3 flex gap-0.5">
            {tabs.map((t) => (
              <Link
                key={t.href}
                href={t.href}
                className={[
                  "rounded-md px-2.5 py-1.5 text-[12px] transition-colors",
                  t.active
                    ? "bg-[var(--color-margin-deep)] font-medium text-[var(--color-ink)]"
                    : "text-[var(--color-ink-soft)] hover:bg-[var(--color-margin-deep)]",
                ].join(" ")}
              >
                {t.label}
              </Link>
            ))}
          </nav>
        )}

        <div className="ml-auto flex items-center gap-3">
          {right}
          <div className="text-right leading-tight">
            <div className="text-[12px] font-medium text-[var(--color-ink)]">{user.display_name}</div>
            {user.participant_code && (
              <div className="font-mono text-[9.5px] text-[var(--color-ink-faint)]">
                {user.participant_code}
              </div>
            )}
          </div>
          <button
            onClick={() => { clearSession(); router.push("/"); }}
            title="Switch portal"
            className="rounded-md px-2 py-1.5 font-mono text-[10.5px] text-[var(--color-ink-faint)] transition-colors hover:bg-[var(--color-margin-deep)] hover:text-[var(--color-ink)]"
          >
            switch
          </button>
        </div>
      </div>
    </header>
  );
}
