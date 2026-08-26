"use client";

import { useState } from "react";

const ORDER = ["executive", "instrumental", "brainstorm", "reflection"] as const;

const COPY: Record<string, string> = {
  executive: "Executive help",
  instrumental: "Instrumental help",
  brainstorm: "Brainstorming",
  reflection: "Reflection",
};

/**
 * Help-seeking distribution.
 *
 * One series, so no legend - each bar is named on its own row and colour is a
 * status encoding, not identity: executive is the category the guardrail
 * intercepts, so it wears the flag mark.
 */
export function IntentChart({ data }: { data: Record<string, number> }) {
  const [hover, setHover] = useState<string | null>(null);
  const total = Object.values(data).reduce((a, b) => a + b, 0);
  const max = Math.max(1, ...Object.values(data));

  if (total === 0) {
    return (
      <p className="py-6 text-center text-[11.5px] text-[var(--color-ink-faint)]">
        No exchanges recorded yet.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {ORDER.map((key) => {
        const value = data[key] ?? 0;
        const pct = (value / max) * 100;
        const isFlagged = key === "executive";
        return (
          <div
            key={key}
            className="grid grid-cols-[112px_1fr_auto] items-center gap-2.5"
            onMouseEnter={() => setHover(key)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="truncate text-[11.5px] text-[var(--color-ink-soft)]">
              {COPY[key]}
            </span>
            <div className="relative h-[18px] rounded-[3px] bg-[var(--color-mark-track)]">
              <div
                className="h-full rounded-l-[3px] rounded-r-[4px] transition-all duration-500"
                style={{
                  width: `${Math.max(pct, value > 0 ? 2 : 0)}%`,
                  background: isFlagged ? "var(--color-mark-flag)" : "var(--color-mark)",
                  opacity: hover && hover !== key ? 0.45 : 1,
                }}
              />
              {hover === key && (
                <div className="pointer-events-none absolute -top-8 left-2 z-10 whitespace-nowrap rounded-md bg-[var(--color-ink)] px-2 py-1 font-mono text-[10px] text-white shadow-lg">
                  {value} of {total} · {Math.round((value / total) * 100)}%
                  {isFlagged ? " · intercepted" : ""}
                </div>
              )}
            </div>
            <span className="w-6 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">
              {value}
            </span>
          </div>
        );
      })}
      <p className="pt-1 text-[10.5px] leading-snug text-[var(--color-ink-faint)]">
        Executive requests (amber) are the ones the Helsinki filter intercepts and
        converts into questions.
      </p>
    </div>
  );
}
