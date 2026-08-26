"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Intensity, StudentOptions } from "@/lib/types";

const DOT: Record<string, number> = { light: 1, balanced: 2, deep: 3 };

/**
 * The student's own controls.
 *
 * What they can change is how much scaffolding they get, not whether the
 * guardrail applies - so the panel says so out loud. Which controls appear at
 * all is decided by the experiment condition they are assigned to: a locked
 * condition simply does not offer them.
 */
export function ScaffoldControl({
  intensity, provider, onIntensity, onProvider, disabled,
}: {
  intensity: Intensity;
  provider: string;
  onIntensity: (v: Intensity) => void;
  onProvider: (id: string, model: string) => void;
  disabled: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [opts, setOpts] = useState<StudentOptions | null>(null);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => { api.options().then(setOpts).catch(() => {}); }, []);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  if (!opts || (!opts.allow_intensity && !opts.allow_model)) return null;

  const current = opts.intensities.find((i) => i.id === intensity);
  const level = DOT[intensity] ?? 2;

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[12px] text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-margin-deep)]"
        title="How much scaffolding you want"
      >
        <span className="flex items-end gap-[2px]" aria-hidden>
          {[1, 2, 3].map((n) => (
            <span
              key={n}
              className="w-[3px] rounded-[1px] transition-colors"
              style={{
                height: 4 + n * 3,
                background: n <= level ? "var(--color-accent)" : "var(--color-margin-edge)",
              }}
            />
          ))}
        </span>
        {current?.label ?? "Scaffold"}
      </button>

      {open && (
        <div className="animate-rise absolute right-0 top-9 z-40 w-[290px] rounded-xl border border-[var(--color-margin-edge)] bg-white p-3 shadow-lg">
          {opts.allow_intensity && (
            <>
              <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
                how much scaffolding
              </div>
              <div className="mt-2 space-y-1">
                {opts.intensities.map((i) => (
                  <button
                    key={i.id}
                    disabled={disabled}
                    onClick={() => { onIntensity(i.id); setOpen(false); }}
                    className={[
                      "flex w-full flex-col rounded-lg border p-2.5 text-left transition-all disabled:opacity-40",
                      intensity === i.id
                        ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]"
                        : "border-transparent hover:bg-[var(--color-margin)]",
                    ].join(" ")}
                  >
                    <span className={`text-[12.5px] font-medium ${intensity === i.id ? "text-[var(--color-accent)]" : "text-[var(--color-ink)]"}`}>
                      {i.label}
                    </span>
                    <span className="mt-0.5 text-[11px] leading-snug text-[var(--color-ink-faint)]">
                      {i.blurb}
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          {opts.allow_model && opts.providers.length > 0 && (
            <>
              <div className="mt-3 border-t border-[var(--color-margin-edge)] pt-3 font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
                which model
              </div>
              <div className="mt-2 space-y-1">
                {opts.providers.map((p) => (
                  <button
                    key={p.id}
                    disabled={disabled}
                    onClick={() => { onProvider(p.id, p.model); setOpen(false); }}
                    className={[
                      "flex w-full items-center gap-2 rounded-lg border p-2 text-left transition-all disabled:opacity-40",
                      provider === p.id
                        ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]"
                        : "border-transparent hover:bg-[var(--color-margin)]",
                    ].join(" ")}
                  >
                    <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${p.healthy ? "bg-[var(--color-agency)]" : "bg-[var(--color-ink-faint)]"}`} />
                    <span className="min-w-0 flex-1">
                      <span className={`block text-[12px] ${provider === p.id ? "text-[var(--color-accent)]" : "text-[var(--color-ink)]"}`}>
                        {p.label}
                      </span>
                      <span className="block truncate font-mono text-[9.5px] text-[var(--color-ink-faint)]">
                        {p.status}
                      </span>
                    </span>
                  </button>
                ))}
              </div>
            </>
          )}

          <p className="mt-3 border-t border-[var(--color-margin-edge)] pt-2.5 text-[10.5px] leading-relaxed text-[var(--color-ink-faint)]">
            {opts.guardrail_active ? (
              <>None of these change the one rule: the partner will not write your
              story at any setting.</>
            ) : (
              <>The Socratic guardrail is switched off in your session, so this
              partner will write text if you ask it to.</>
            )}
            {opts.condition && (
              <> You are in the <span className="text-[var(--color-ink-soft)]">{opts.condition.name}</span> condition.</>
            )}
          </p>
        </div>
      )}
    </div>
  );
}
