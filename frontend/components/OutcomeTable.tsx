"use client";

import { useState } from "react";
import type { ArmOutcome } from "@/lib/types";

type Measure = {
  key: keyof ArmOutcome;
  label: string;
  fmt: (v: number) => string;
  /** Which direction is the intervention hoping to move this? */
  hope: "up" | "down" | "none";
};

const ACTIVITY_ROWS: [string, string][] = [
  ["planning", "Planning"],
  ["translation", "Translation"],
  ["reviewing", "Reviewing"],
  ["other", "Other"],
];

const MEASURES: Measure[] = [
  { key: "mean_agency", label: "Human agency", fmt: (v) => `${Math.round(v * 100)}%`, hope: "up" },
  { key: "mean_ai_retention", label: "AI retention (ROUGE-L)", fmt: (v) => `${Math.round(v * 100)}%`, hope: "down" },
  { key: "intercept_rate", label: "Intercept rate", fmt: (v) => `${Math.round(v * 100)}%`, hope: "none" },
  { key: "words_per_exchange", label: "Words per exchange", fmt: (v) => v.toFixed(1), hope: "up" },
  { key: "mean_words", label: "Mean draft length", fmt: (v) => v.toFixed(0), hope: "none" },
  { key: "median_latency_ms", label: "Median latency", fmt: (v) => `${Math.round(v)}ms`, hope: "down" },
];

/**
 * Outcomes side by side, one row per measure.
 *
 * Deltas are shown against whichever arm is marked the control, because the
 * only question worth asking here is "compared to what?". Arms with too few
 * observations say so rather than showing a number nobody should trust.
 */
export function OutcomeTable({ arms }: { arms: ArmOutcome[] }) {
  const [showDelta, setShowDelta] = useState(true);
  const control = arms.find((a) => a.is_control) ?? null;

  if (arms.length === 0) {
    return (
      <p className="py-6 text-center text-[11.5px] text-[var(--color-ink-faint)]">
        No conditions defined yet.
      </p>
    );
  }

  const delta = (m: Measure, a: ArmOutcome) => {
    if (!control || a.is_control || !showDelta) return null;
    const mine = a[m.key] as number | null;
    const base = control[m.key] as number | null;
    if (mine == null || base == null || base === 0) return null;
    const pct = ((mine - base) / Math.abs(base)) * 100;
    if (Math.abs(pct) < 0.5) return null;
    const good = m.hope === "none" ? null : (pct > 0) === (m.hope === "up");
    return { pct, good };
  };

  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[10.5px] text-[var(--color-ink-faint)]">
          {control
            ? <>Deltas are against <strong className="font-medium text-[var(--color-ink-soft)]">{control.name}</strong>, the control condition.</>
            : "Mark a condition as control to see deltas."}
        </span>
        {control && (
          <button
            onClick={() => setShowDelta((v) => !v)}
            className="font-mono text-[10px] text-[var(--color-ink-faint)] hover:text-[var(--color-accent)]"
          >
            {showDelta ? "hide deltas" : "show deltas"}
          </button>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--color-margin-edge)] bg-white">
        <table className="w-full min-w-[560px] text-left">
          <thead>
            <tr className="border-b border-[var(--color-margin-edge)]">
              <th className="px-3.5 py-2 font-mono text-[10px] font-normal uppercase tracking-wider text-[var(--color-ink-faint)]">
                measure
              </th>
              {arms.map((a) => (
                <th key={a.arm_id} className="px-3.5 py-2 text-right">
                  <div className="text-[12px] font-medium text-[var(--color-ink)]">{a.name}</div>
                  <div className="font-mono text-[9.5px] font-normal text-[var(--color-ink-faint)]">
                    {a.is_control ? "control · " : ""}n={a.participants}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-[var(--color-margin-edge)] bg-[var(--color-margin)]/40">
              <td className="px-3.5 py-1.5 font-mono text-[10px] text-[var(--color-ink-faint)]">exchanges</td>
              {arms.map((a) => (
                <td key={a.arm_id} className="px-3.5 py-1.5 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">
                  {a.exchanges}
                </td>
              ))}
            </tr>

            {MEASURES.map((m) => (
              <tr key={String(m.key)} className="border-b border-[var(--color-margin-edge)] last:border-0">
                <td className="px-3.5 py-2.5 text-[12px] text-[var(--color-ink-soft)]">{m.label}</td>
                {arms.map((a) => {
                  const raw = a[m.key] as number | null;
                  const d = delta(m, a);
                  const thin = a.exchanges < 3;
                  return (
                    <td key={a.arm_id} className="px-3.5 py-2.5 text-right">
                      {raw == null ? (
                        <span className="font-mono text-[11px] text-[var(--color-ink-faint)]">—</span>
                      ) : (
                        <>
                          <span
                            className="font-mono text-[12px] tabular-nums text-[var(--color-ink)]"
                            style={thin ? { opacity: 0.45 } : undefined}
                            title={thin ? "Fewer than 3 exchanges — not yet meaningful" : undefined}
                          >
                            {m.fmt(raw)}
                          </span>
                          {d && (
                            <span
                              className="ml-1.5 font-mono text-[10px] tabular-nums"
                              style={{
                                color: d.good === null ? "var(--color-ink-faint)"
                                  : d.good ? "var(--color-agency)" : "var(--color-flag)",
                              }}
                            >
                              {d.pct > 0 ? "+" : ""}{d.pct.toFixed(0)}%
                            </span>
                          )}
                        </>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {arms.some((a) => a.exchanges < 3) && (
        <p className="mt-2 text-[10.5px] text-[var(--color-ink-faint)]">
          Dimmed figures come from fewer than three exchanges and are not yet
          worth reading.
        </p>
      )}

      {arms.some((a) =>
        a.retention_by_activity &&
        Object.values(a.retention_by_activity).some((v) => v != null),
      ) && (
        <details className="group mt-2.5">
          <summary className="cursor-pointer list-none font-mono text-[10px] text-[var(--color-ink-faint)] hover:text-[var(--color-ink-soft)]">
            <span className="group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span>{" "}
            AI retention by writing activity
          </summary>
          <div className="mt-2 overflow-x-auto rounded-lg border border-[var(--color-margin-edge)] bg-white">
            <table className="w-full min-w-[420px] text-left">
              <thead>
                <tr className="border-b border-[var(--color-margin-edge)] font-mono text-[10px] uppercase tracking-wider text-[var(--color-ink-faint)]">
                  <th className="px-3.5 py-2 font-normal">activity</th>
                  {arms.map((a) => (
                    <th key={a.arm_id} className="px-3.5 py-2 text-right font-normal">{a.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ACTIVITY_ROWS.map(([key, label]) => (
                  <tr key={key} className="border-b border-[var(--color-margin-edge)] last:border-0">
                    <td className="px-3.5 py-2 text-[12px] text-[var(--color-ink-soft)]">{label}</td>
                    {arms.map((a) => {
                      const v = a.retention_by_activity?.[key] ?? null;
                      return (
                        <td key={a.arm_id} className="px-3.5 py-2 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">
                          {v == null ? "—" : `${Math.round(v * 100)}%`}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-1.5 text-[10px] leading-snug text-[var(--color-ink-faint)]">
            ROUGE-L recall of that activity’s AI output within the draft.
            Chakrabarty et&nbsp;al. (footnote&nbsp;18) exclude Reviewing from the
            headline figure, since critique is not meant to enter the draft —
            shown here for comparison.
          </p>
        </details>
      )}
    </div>
  );
}
