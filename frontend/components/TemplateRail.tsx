"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Template } from "@/lib/types";

const COGNITIVE_TONE: Record<string, string> = {
  planning: "var(--color-cog-plan)",
  translation: "var(--color-cog-trans)",
  reviewing: "var(--color-cog-review)",
};

/**
 * Templated instructions.
 *
 * Chakrabarty et al. (C&C '24) found templated prompts to be the single most
 * appreciated feature of their writing interface, so the affordance is worth
 * keeping. Four of their five templates ask the model to produce prose, which
 * our guardrail exists to refuse - each is inverted into the instrumental
 * question serving the same need. Hovering a chip shows what it was.
 */
export function TemplateRail({
  onPick, disabled, hasSelection,
}: {
  onPick: (prompt: string) => void;
  disabled: boolean;
  hasSelection: boolean;
}) {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => {});
  }, []);

  if (!templates.length) return null;

  return (
    <div className="border-t border-[var(--color-margin-edge)] px-3 py-2">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)] transition-colors hover:text-[var(--color-ink-soft)]"
      >
        <span>{open ? "▾" : "▸"}</span>
        ways to ask
        {hasSelection && (
          <span className="ml-1 rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 text-[9px] normal-case tracking-normal text-[var(--color-accent)]">
            about your selection
          </span>
        )}
      </button>

      {open && (
        <div className="animate-rise mt-2 flex flex-wrap gap-1.5">
          {templates.map((t) => (
            <button
              key={t.id}
              disabled={disabled}
              onClick={() => onPick(t.prompt)}
              title={
                t.inverted
                  ? `Socratic inversion of the paper's "${t.origin}" template · ${t.cognitive}`
                  : `From the paper's "${t.origin}" template · ${t.cognitive}`
              }
              className="group flex items-center gap-1.5 rounded-full border border-[var(--color-margin-edge)] bg-white px-2.5 py-1 text-[11px] text-[var(--color-ink-soft)] transition-all hover:border-[var(--color-accent-line)] hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)] disabled:opacity-40"
            >
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full"
                style={{ background: COGNITIVE_TONE[t.cognitive] ?? "var(--color-ink-faint)" }}
              />
              {t.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
