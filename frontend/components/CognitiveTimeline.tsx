"use client";

import { useState } from "react";
import type { TimelinePoint } from "@/lib/types";

const ROWS = [
  { id: "planning", label: "Planning", tone: "var(--color-cog-plan)" },
  { id: "translation", label: "Translation", tone: "var(--color-cog-trans)" },
  { id: "reviewing", label: "Reviewing", tone: "var(--color-cog-review)" },
  { id: "other", label: "Other", tone: "var(--color-ink-faint)" },
];

/**
 * Instruction type against instruction index.
 *
 * This is a direct reproduction of Figure 6 in Chakrabarty et al. (C&C '24),
 * which used it to show that professional writers move between planning,
 * translating and reviewing non-linearly rather than in tidy phases. Running
 * it per session lets the client test whether students under a Socratic
 * guardrail show the same zig-zag.
 *
 * Row position carries the category; colour is reinforcement, never the sole
 * encoding. Intercepted turns get a ring so the guardrail is visible here too.
 *
 * Phase 2: a second, hollow track shows what the writer *declared* they were
 * doing (their Monitor), so a researcher can see where declared and detected
 * diverge.
 */
const DECLARED_ROW: Record<string, number> = { planning: 0, translating: 1, reviewing: 2 };

export function CognitiveTimeline({ points }: { points: TimelinePoint[] }) {
  const [hover, setHover] = useState<number | null>(null);

  if (points.length === 0) {
    return (
      <p className="py-8 text-center text-[11.5px] text-[var(--color-ink-faint)]">
        No instructions recorded yet. The sequence appears once students start asking.
      </p>
    );
  }

  const rowIndex = (c: string) => ROWS.findIndex((r) => r.id === c);
  const W = Math.max(points.length * 26 + 40, 320);
  const ROW_H = 34;
  const H = ROWS.length * ROW_H + 24;
  const x = (i: number) => 20 + i * 26;
  const y = (c: string) => {
    const r = rowIndex(c);
    return r < 0 ? H - 12 : r * ROW_H + ROW_H / 2;
  };

  const path = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i)} ${y(p.cognitive)}`)
    .join(" ");

  // Declared track: only the turns where the writer declared an activity.
  const declaredRowY = (d: string) => {
    const r = DECLARED_ROW[d];
    return r === undefined ? H - 12 : r * ROW_H + ROW_H / 2;
  };
  const declaredPts = points
    .map((p, i) => ({ p, i }))
    .filter(({ p }) => p.declared && DECLARED_ROW[p.declared] !== undefined);
  const declaredPath = declaredPts
    .map(({ p, i }, k) => `${k === 0 ? "M" : "L"} ${x(i)} ${declaredRowY(p.declared) - 9}`)
    .join(" ");

  const active = hover !== null ? points[hover] : null;

  return (
    <div>
      <div className="flex gap-2">
        <div className="shrink-0 pt-[2px]">
          {ROWS.map((r) => (
            <div key={r.id} style={{ height: ROW_H }} className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full" style={{ background: r.tone }} />
              <span className="text-[10.5px] text-[var(--color-ink-soft)]">{r.label}</span>
            </div>
          ))}
        </div>

        <div className="thin-scroll min-w-0 flex-1 overflow-x-auto">
          <svg width={W} height={H} className="block">
            {ROWS.map((r, i) => (
              <line
                key={r.id}
                x1={0} x2={W}
                y1={i * ROW_H + ROW_H / 2} y2={i * ROW_H + ROW_H / 2}
                stroke="var(--color-margin-edge)" strokeWidth={1}
              />
            ))}
            <path d={path} fill="none" stroke="var(--color-margin-edge)" strokeWidth={1.5} />

            {/* declared track - hollow squares, dashed connector, sits above the row */}
            {declaredPath && (
              <path d={declaredPath} fill="none" stroke="var(--color-ink-faint)"
                    strokeWidth={1} strokeDasharray="2 3" />
            )}
            {declaredPts.map(({ p, i }) => (
              <rect
                key={`d-${p.index}`}
                x={x(i) - 3} y={declaredRowY(p.declared) - 12}
                width={6} height={6}
                fill="none" stroke="var(--color-ink-soft)" strokeWidth={1.5}
              />
            ))}

            {points.map((p, i) => {
              const tone = ROWS[rowIndex(p.cognitive)]?.tone ?? "var(--color-ink-faint)";
              return (
                <g key={p.index}
                   onMouseEnter={() => setHover(i)}
                   onMouseLeave={() => setHover(null)}>
                  <circle cx={x(i)} cy={y(p.cognitive)} r={11} fill="transparent" />
                  {p.intercepted && (
                    <circle cx={x(i)} cy={y(p.cognitive)} r={7}
                            fill="none" stroke="var(--color-flag)" strokeWidth={1.5} />
                  )}
                  <circle
                    cx={x(i)} cy={y(p.cognitive)} r={hover === i ? 5.5 : 4}
                    fill={tone} stroke="white" strokeWidth={2}
                    style={{ transition: "r 120ms" }}
                  />
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="mt-2 flex min-h-[32px] items-start gap-2">
        {active ? (
          <div className="animate-rise rounded-md border border-[var(--color-margin-edge)] bg-white px-2.5 py-1.5">
            <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
              #{active.index} · detected {active.cognitive} · {active.intent}
              {active.declared ? ` · declared ${active.declared}` : ""}
              {active.intercepted ? " · intercepted" : ""}
            </span>
            <p className="mt-0.5 text-[11.5px] text-[var(--color-ink-soft)]">“{active.message}”</p>
          </div>
        ) : (
          <p className="text-[10.5px] leading-snug text-[var(--color-ink-faint)]">
            Filled dot = detected activity, in order; ringed = intercepted.
            Hollow square = what the writer declared they were doing. Hover to read it.
          </p>
        )}
      </div>
    </div>
  );
}
