"use client";

import type { DeclaredActivity } from "@/lib/types";
import { DECLARED_ACTIVITIES } from "@/lib/types";

/**
 * The writer's Monitor (Flower & Hayes).
 *
 * Lets the writer say what they are doing right now so the partner can meet
 * them in it — questions that open ideas during Planning, a method (not a
 * phrasing) during Translating, pressure on assumptions during Reviewing.
 *
 * Deliberately NOT a stepper. Flower & Hayes are explicit that these are not
 * ordered stages — a writer plans, translates and reviews inside a single
 * sentence. So: three equal toggles, no arrows, no numbers, no "done", and
 * clicking the active one clears it back to undeclared.
 */
const META: Record<Exclude<DeclaredActivity, "">, { label: string; tone: string; hint: string }> = {
  planning: {
    label: "Planning", tone: "var(--color-cog-plan)",
    hint: "working out what happens, who someone is, what it's for",
  },
  translating: {
    label: "Translating", tone: "var(--color-cog-trans)",
    hint: "getting what you mean into actual sentences",
  },
  reviewing: {
    label: "Reviewing", tone: "var(--color-cog-review)",
    hint: "judging and revising what's already down",
  },
};

export function ActivityControl({ value, onChange, disabled }: {
  value: DeclaredActivity;
  onChange: (next: DeclaredActivity) => void;
  disabled?: boolean;
}) {
  return (
    <div className="border-t border-[var(--color-margin-edge)] bg-white/40 px-3 pb-2 pt-2">
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="font-mono text-[9.5px] uppercase tracking-widest text-[var(--color-ink-faint)]">
          what are you doing right now?
        </span>
        {value && (
          <button
            onClick={() => onChange("")}
            disabled={disabled}
            className="font-mono text-[9.5px] text-[var(--color-ink-faint)] hover:text-[var(--color-ink-soft)] disabled:opacity-40"
          >
            clear
          </button>
        )}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {DECLARED_ACTIVITIES.map((a) => {
          const on = value === a;
          const m = META[a];
          return (
            <button
              key={a}
              type="button"
              disabled={disabled}
              title={m.hint}
              aria-pressed={on}
              onClick={() => onChange(on ? "" : a)}
              className={[
                "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-[3px] font-mono text-[10.5px] transition-colors disabled:opacity-40",
                on
                  ? "border-transparent text-white"
                  : "border-[var(--color-margin-edge)] bg-white text-[var(--color-ink-soft)] hover:border-[var(--color-ink-faint)]",
              ].join(" ")}
              style={on ? { background: m.tone } : undefined}
            >
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: on ? "rgba(255,255,255,0.85)" : m.tone }}
              />
              {m.label}
            </button>
          );
        })}
      </div>

      <p className="mt-1.5 text-[10px] leading-snug text-[var(--color-ink-faint)]">
        Move between these freely — they’re not steps, and you can leave it unset.
      </p>
    </div>
  );
}
