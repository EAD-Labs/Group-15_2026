"use client";

import { useState } from "react";
import type { AIRole, Archetype } from "@/lib/types";

/**
 * One configurable AI role.
 *
 * This is the seam the client asked for: the Socratic behaviour is not
 * hard-coded, it is this row, and a researcher can retune it here without a
 * redeploy. Saving is append-only on the server — every edit writes a new
 * version and the conditions that used the old one are repointed — so the
 * button says "save as v(N+1)", not "save".
 */
const ARCHETYPES: Archetype[] = ["tutor", "partner", "ghost", "custom"];
const BEHAVIOURS = [
  "socratic_questioning", "brainstorming", "critical_reflection",
  "direct_generation", "custom",
];

type Draft = Pick<AIRole,
  "name" | "archetype" | "behaviour" | "base_prompt" |
  "may_produce_prose" | "enforcement_level"
>;

const pick = (r: AIRole): Draft => ({
  name: r.name, archetype: r.archetype, behaviour: r.behaviour,
  base_prompt: r.base_prompt, may_produce_prose: r.may_produce_prose,
  enforcement_level: r.enforcement_level,
});

export function RoleCard({ role, usedByCount, onSave, onDelete }: {
  role: AIRole;
  usedByCount: number;
  onSave: (body: Partial<AIRole>) => void;
  onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Draft>(() => pick(role));

  // If the role prop changes under us (e.g. a save produced a new version and
  // the parent swapped it in), re-seed the draft.
  const [seededFrom, setSeededFrom] = useState(role.role_id);
  if (seededFrom !== role.role_id) {
    setSeededFrom(role.role_id);
    setDraft(pick(role));
  }

  const dirty = (Object.keys(draft) as (keyof Draft)[]).some((k) => draft[k] !== pick(role)[k]);
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => ({ ...d, [k]: v }));

  return (
    <div className="rounded-lg border border-[var(--color-margin-edge)] bg-white transition-colors">
      <div className="flex items-start gap-2 p-3.5">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[13px] font-medium text-[var(--color-ink)]">{role.name}</span>
            <span className="rounded bg-[var(--color-margin-deep)] px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--color-ink-faint)]">
              {role.archetype}
            </span>
            <span title="version — edits are append-only"
                  className="font-mono text-[9px] text-[var(--color-ink-faint)]">
              v{role.version}
            </span>
          </div>
          <div className="mt-1.5 font-mono text-[10.5px] text-[var(--color-ink-faint)]">
            {role.behaviour} · {role.may_produce_prose ? "may write prose" : "no prose"} ·{" "}
            enforcement {role.enforcement_level}
          </div>
        </div>

        <div className="shrink-0 text-right">
          <div className="font-mono text-[13px] tabular-nums text-[var(--color-ink)]">{usedByCount}</div>
          <div className="font-mono text-[9px] uppercase tracking-wider text-[var(--color-ink-faint)]">
            {usedByCount === 1 ? "condition" : "conditions"}
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
            <Field label="name">
              <input value={draft.name} onChange={(e) => set("name", e.target.value)}
                     className={inputCls} />
            </Field>
            <Field label="archetype (Steinhoff & Lehnen)">
              <select value={draft.archetype}
                      onChange={(e) => set("archetype", e.target.value as Archetype)}
                      className={selectCls}>
                {ARCHETYPES.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </Field>
            <Field label="behaviour">
              <select value={draft.behaviour}
                      onChange={(e) => set("behaviour", e.target.value)}
                      className={selectCls}>
                {BEHAVIOURS.map((b) => <option key={b} value={b}>{b}</option>)}
              </select>
            </Field>
            <Field label="enforcement level (0 none · 1 block prose · 2 strict)">
              <select value={draft.enforcement_level}
                      onChange={(e) => set("enforcement_level", +e.target.value)}
                      className={selectCls}>
                {[0, 1, 2].map((n) => <option key={n} value={n}>{n}</option>)}
              </select>
            </Field>
          </div>

          <label className="flex cursor-pointer items-center gap-1.5 text-[11.5px] text-[var(--color-ink-soft)]">
            <input type="checkbox" checked={draft.may_produce_prose}
                   onChange={(e) => set("may_produce_prose", e.target.checked)}
                   className="accent-[var(--color-accent)]" />
            may produce prose (the Ghost / baseline contract)
          </label>

          <Field label="base prompt — {mode_label} and {mode_lens} are filled per story">
            <textarea
              value={draft.base_prompt}
              onChange={(e) => set("base_prompt", e.target.value)}
              rows={8}
              className="thin-scroll w-full resize-none rounded border border-[var(--color-margin-edge)] bg-[var(--color-margin)]/50 p-2 font-mono text-[10.5px] leading-relaxed text-[var(--color-ink)] outline-none focus:border-[var(--color-accent-line)]"
            />
          </Field>

          <div className="flex flex-wrap items-center gap-2 border-t border-[var(--color-margin-edge)] pt-2.5">
            <button
              disabled={!dirty}
              onClick={() => { onSave(draft); setEditing(false); }}
              className="rounded-md bg-[var(--color-accent)] px-2.5 py-1 font-mono text-[10px] font-medium text-white transition-opacity enabled:hover:opacity-90 disabled:opacity-40"
            >
              save as v{role.version + 1}
            </button>
            {dirty && (
              <button onClick={() => setDraft(pick(role))} className={ghostCls}>revert</button>
            )}
            {usedByCount === 0 && (
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

const inputCls =
  "w-full rounded border border-[var(--color-margin-edge)] bg-white px-2 py-1 text-[12px] text-[var(--color-ink)] outline-none focus:border-[var(--color-accent-line)]";
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
