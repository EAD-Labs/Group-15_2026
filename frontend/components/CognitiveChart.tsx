"use client";

import { useState } from "react";

const ROWS = [
  { id: "planning", label: "Planning", tone: "var(--color-cog-plan)",
    blurb: "goals, ideas, what should happen" },
  { id: "translation", label: "Translation", tone: "var(--color-cog-trans)",
    blurb: "getting thoughts into sentences" },
  { id: "reviewing", label: "Reviewing", tone: "var(--color-cog-review)",
    blurb: "judging or revising what exists" },
];

/**
 * Cognitive activity distribution (Flower & Hayes, via the paper's Figure 5).
 *
 * The paper's headline finding is that writers seek help across all three
 * activities but find LLMs most useful for translation and reviewing, least
 * for planning. Under a Socratic guardrail that may invert - which is exactly
 * the comparison this chart exists to support.
 */
export function CognitiveChart({ data }: { data: Record<string, number> }) {
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
      {ROWS.map((r) => {
        const value = data[r.id] ?? 0;
        const pct = (value / max) * 100;
        return (
          <div
            key={r.id}
            className="grid grid-cols-[112px_1fr_auto] items-center gap-2.5"
            onMouseEnter={() => setHover(r.id)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="flex items-center gap-1.5 truncate text-[11.5px] text-[var(--color-ink-soft)]">
              <span className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: r.tone }} />
              {r.label}
            </span>
            <div className="relative h-[18px] rounded-[3px] bg-[var(--color-mark-track)]">
              <div
                className="h-full rounded-l-[3px] rounded-r-[4px] transition-all duration-500"
                style={{
                  width: `${Math.max(pct, value > 0 ? 2 : 0)}%`,
                  background: r.tone,
                  opacity: hover && hover !== r.id ? 0.45 : 1,
                }}
              />
              {hover === r.id && (
                <div className="pointer-events-none absolute -top-8 left-2 z-10 whitespace-nowrap rounded-md bg-[var(--color-ink)] px-2 py-1 font-mono text-[10px] text-white shadow-lg">
                  {value} of {total} · {Math.round((value / total) * 100)}% · {r.blurb}
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
        Flower &amp; Hayes cognitive activities, labelled per turn alongside
        help-seeking type. Chakrabarty et al. found professional writers use
        LLMs least for planning.
      </p>
    </div>
  );
}
