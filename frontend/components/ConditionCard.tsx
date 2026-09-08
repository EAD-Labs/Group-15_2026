"use client";

import { useState } from "react";
import type { AIRole, Arm, Intensity, Provider } from "@/lib/types";

const INTENSITIES: Intensity[] = ["light", "balanced", "deep"];

/**
 * A condition, summarised.
 *
 * Collapsed it reads as one line of configuration, because that is what a
 * researcher scans. The knobs only appear once you are actually changing
 * something - eight always-visible dropdowns made the page feel like a
 * settings screen rather than a study.
 */
export function ConditionCard({ arm, providers, roles, onChange, onDelete }: {
  arm: Arm;
  providers: Provider[];
  roles: AIRole[];
  onChange: (body: Partial<Arm>) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const providerLabel = providers.find((p) => p.id === arm.provider)?.label ?? arm.provider;
  const role = roles.find((r) => r.role_id === arm.role_id);
  const roleLabel = role?.name ?? arm.role_name ?? "no role";

  return (
    <div className={[
      "rounded-lg border bg-white transition-colors",
      arm.is_control ? "border-[var(--color-flag-line)]" : "border-[var(--color-margin-edge)]",
    ].join(" ")}>
      <div className="flex items-start gap-2 p-3.5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <input
              value={arm.name}
              onChange={(e) => onChange({ name: e.target.value })}
              className="min-w-0 max-w-[210px] flex-1 bg-transparent text-[13px] font-medium text-[var(--color-ink)] outline-none focus:underline focus:decoration-[var(--color-accent-line)] focus:underline-offset-4"
            />
            {arm.is_default && (
              <span title="Unassigned participants land here"
                    className="rounded bg-[var(--color-accent-soft)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--color-accent)]">
                default
              </span>
            )}
            {arm.is_control && (
              <span title="The baseline other conditions are compared against"
                    className="rounded bg-[var(--color-flag-soft)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--color-flag)]">
                control
              </span>
            )}
          </div>

          {/* The whole configuration as one scannable line. */}
          <div className="mt-1.5 font-mono text-[10.5px] text-[var(--color-ink-faint)]">
            {providerLabel} · {roleLabel} · {arm.scaffold_intensity} ·{" "}
            t{arm.temperature.toFixed(2)}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <div className="font-mono text-[13px] tabular-nums text-[var(--color-ink)]">
            {arm.participants}
          </div>
          <div className="font-mono text-[9px] uppercase tracking-wider text-[var(--color-ink-faint)]">
            {arm.participants === 1 ? "student" : "students"}
          </div>
        </div>

        <button
          onClick={() => setEditing((v) => !v)}
          className="shrink-0 rounded-md px-2 py-1 font-mono text-[10px] text-[var(--color-ink-faint)] transition-colors hover:bg-[var(--color-margin-deep)] hover:text-[var(--color-ink)]"
        >
          {editing ? "done" : "edit"}
        </button>
      </div>

      {editing && (
        <div className="animate-rise space-y-3 border-t border-[var(--color-margin-edge)] p-3.5">
          <div className="grid gap-2 sm:grid-cols-2">
            <Field label="model">
              <select value={arm.provider}
                      onChange={(e) => onChange({ provider: e.target.value, model_name: "" })}
                      className={selectCls}>
                {providers.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}
              </select>
            </Field>
            <Field label="AI role">
              <select value={arm.role_id}
                      onChange={(e) => onChange({ role_id: e.target.value })}
                      className={selectCls}>
                {roles.length === 0 && <option value="">no roles defined</option>}
                {roles.map((r) => (
                  <option key={r.role_id} value={r.role_id}>
                    {r.name}{r.may_produce_prose ? " — writes freely" : ""}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="scaffold">
              <select value={arm.scaffold_intensity}
                      onChange={(e) => onChange({ scaffold_intensity: e.target.value as Intensity })}
                      className={selectCls}>
                {INTENSITIES.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </Field>
            <Field label={`temperature ${arm.temperature.toFixed(2)}`}>
              <input type="range" min={0} max={1.5} step={0.05} value={arm.temperature}
                     onChange={(e) => onChange({ temperature: +e.target.value })}
                     className="w-full accent-[var(--color-accent)]" />
            </Field>
          </div>

          <Field label="custom system prompt — blank uses the role's prompt">
            <textarea
              value={arm.system_prompt}
              onChange={(e) => onChange({ system_prompt: e.target.value })}
              rows={4}
              placeholder="Leave blank to use the selected role's prompt."
              className="thin-scroll w-full resize-none rounded border border-[var(--color-margin-edge)] bg-[var(--color-margin)]/50 p-2 font-mono text-[10.5px] leading-relaxed text-[var(--color-ink)] outline-none focus:border-[var(--color-accent-line)]"
            />
          </Field>

          <div className="flex flex-wrap items-center gap-3">
            {([
              ["allow_student_intensity", "student sets scaffold"],
              ["allow_student_model", "student picks model"],
            ] as const).map(([k, label]) => (
              <label key={k} className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-[var(--color-ink-soft)]">
                <input type="checkbox" checked={arm[k]}
                       onChange={(e) => onChange({ [k]: e.target.checked } as Partial<Arm>)}
                       className="accent-[var(--color-accent)]" />
                {label}
              </label>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-[var(--color-margin-edge)] pt-2.5">
            {!arm.is_default && (
              <button onClick={() => onChange({ is_default: true })} className={ghostCls}>
                make default
              </button>
            )}
            {!arm.is_control && (
              <button onClick={() => onChange({ is_control: true })} className={ghostCls}>
                make control
              </button>
            )}
            {!arm.is_default && (
              <button onClick={onDelete}
                      className="ml-auto font-mono text-[10px] text-[var(--color-agency-low)] hover:underline">
                delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const selectCls =
  "w-full rounded border border-[var(--color-margin-edge)] bg-white px-2 py-1 font-mono text-[10.5px] text-[var(--color-ink-soft)]";
const ghostCls =
  "rounded-md border border-[var(--color-margin-edge)] px-2 py-1 font-mono text-[10px] text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:text-[var(--color-accent)]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="font-mono text-[9.5px] uppercase tracking-widest text-[var(--color-ink-faint)]">
        {label}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
