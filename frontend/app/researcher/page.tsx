"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { AIRole, Arm, Comparison, Provider, SessionUser } from "@/lib/types";
import { ConditionCard } from "@/components/ConditionCard";
import { RoleCard } from "@/components/RoleCard";
import { OutcomeTable } from "@/components/OutcomeTable";
import { PortalHeader } from "@/components/PortalHeader";
import { PortalLoading, usePortal } from "@/components/PortalGuard";

const TABS = [
  { href: "/researcher", label: "Study" },
  { href: "/researcher/data", label: "Data" },
];

function Section({ n, title, hint, action, children }: {
  n: string; title: string; hint: string;
  action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="mb-9">
      <div className="mb-3 flex flex-wrap items-baseline gap-2.5">
        <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">{n}</span>
        <h2 className="text-[13.5px] font-semibold text-[var(--color-ink)]">{title}</h2>
        <span className="text-[11px] text-[var(--color-ink-faint)]">{hint}</span>
        {action && <div className="ml-auto">{action}</div>}
      </div>
      {children}
    </section>
  );
}

/**
 * The whole study on one page: what you set up, who is in it, what happened.
 *
 * Provider, temperature and strictness used to live here *and* on a separate
 * experiments page. Since a condition overrides the global config, the global
 * copy was dead UI for anyone assigned to a condition - so it is gone, and a
 * condition is now the only place those variables exist.
 */
export default function StudyPage() {
  const { user, checked } = usePortal("researcher");
  const [arms, setArms] = useState<Arm[]>([]);
  const [roles, setRoles] = useState<AIRole[]>([]);
  const [cmp, setCmp] = useState<Comparison | null>(null);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [participants, setParticipants] = useState<SessionUser[]>([]);
  const [toast, setToast] = useState("");
  const [live, setLive] = useState(true);

  const refresh = useCallback(async () => {
    const [a, r, c, p, u] = await Promise.all([
      api.arms(), api.roles(), api.compare(), api.providers(), api.participants(),
    ]);
    setArms(a); setRoles(r); setCmp(c); setProviders(p.providers); setParticipants(u);
  }, []);

  useEffect(() => { if (checked) refresh().catch(console.error); }, [checked, refresh]);
  useEffect(() => {
    if (!live || !checked) return;
    const t = setInterval(() => refresh().catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [live, checked, refresh]);

  if (!checked || !user) return <PortalLoading />;

  const note = (m: string) => { setToast(m); setTimeout(() => setToast(""), 2200); };
  const patch = async (armId: string, body: Partial<Arm>) => {
    setArms((prev) => prev.map((a) => (a.arm_id === armId ? { ...a, ...body } : a)));
    await api.updateArm(armId, body);
    refresh();
  };

  const saveRole = async (roleId: string, body: Partial<AIRole>) => {
    // Append-only server-side: a new version row is written and every condition
    // that used the old one is repointed, so refresh both lists.
    await api.updateRole(roleId, body);
    note("Role saved as a new version");
    refresh();
  };
  const armsUsingRole = (roleId: string) => arms.filter((a) => a.role_id === roleId).length;

  const unassigned = cmp?.unassigned_participants ?? 0;

  return (
    <div className="min-h-screen bg-[var(--color-margin)]">
      <PortalHeader
        user={user}
        tabs={TABS.map((t) => ({ ...t, active: t.href === "/researcher" }))}
        right={
          <button
            onClick={() => setLive((v) => !v)}
            className="flex items-center gap-1.5 rounded-md px-2 py-1.5 font-mono text-[10.5px] text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-margin-deep)]"
          >
            <span className={`h-1.5 w-1.5 rounded-full ${live ? "animate-node bg-[var(--color-agency)]" : "bg-[var(--color-ink-faint)]"}`} />
            {live ? "live" : "paused"}
          </button>
        }
      />

      {toast && (
        <div className="animate-rise fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg bg-[var(--color-ink)] px-3.5 py-2 font-mono text-[11px] text-white shadow-lg">
          {toast}
        </div>
      )}

      <main className="mx-auto max-w-4xl px-6 py-8">
        {/* ---- 01 what you are varying ------------------------------------ */}
        <Section
          n="01"
          title="Conditions"
          hint="each one bundles every variable a student experiences"
          action={
            <button
              onClick={async () => {
                await api.createArm({
                  name: `Condition ${arms.length + 1}`,
                  description: "",
                  provider: providers[0]?.id ?? "gemini",
                  allowed_providers: providers.map((p) => p.id),
                });
                note("Condition added");
                refresh();
              }}
              className="rounded-md border border-dashed border-[var(--color-margin-edge)] px-2.5 py-1 text-[11.5px] text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:text-[var(--color-accent)]"
            >
              + Add
            </button>
          }
        >
          <div className="grid gap-2.5 sm:grid-cols-2">
            {arms.map((a) => (
              <ConditionCard
                key={a.arm_id}
                arm={a}
                providers={providers}
                roles={roles}
                onChange={(b) => patch(a.arm_id, b)}
                onDelete={async () => { await api.deleteArm(a.arm_id); note("Deleted"); refresh(); }}
              />
            ))}
          </div>
        </Section>

        {/* ---- 02 the AI roles conditions choose from ------------------- */}
        <Section
          n="02"
          title="AI roles"
          hint="the behaviour a condition points at — editable here, no redeploy"
          action={
            <button
              onClick={async () => {
                const tutor = roles.find((r) => r.archetype === "tutor");
                await api.createRole({
                  name: `Role ${roles.length + 1}`,
                  archetype: "custom",
                  behaviour: "custom",
                  base_prompt: tutor?.base_prompt ?? "",
                  enforcement_level: 2,
                });
                note("Role added");
                refresh();
              }}
              className="rounded-md border border-dashed border-[var(--color-margin-edge)] px-2.5 py-1 text-[11.5px] text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:text-[var(--color-accent)]"
            >
              + Add
            </button>
          }
        >
          <div className="grid gap-2.5 sm:grid-cols-2">
            {roles.map((r) => (
              <RoleCard
                key={r.role_id}
                role={r}
                usedByCount={armsUsingRole(r.role_id)}
                onSave={(b) => saveRole(r.role_id, b)}
                onDelete={async () => { await api.deleteRole(r.role_id); note("Deleted"); refresh(); }}
              />
            ))}
          </div>
        </Section>

        {/* ---- 03 who is in what ------------------------------------------ */}
        <Section
          n="03"
          title="Participants"
          hint={`${participants.length} total${unassigned ? ` · ${unassigned} unassigned` : ""}`}
          action={
            <button
              onClick={async () => {
                const r = await api.assign({ randomise: true });
                note(r.assigned ? `Randomised ${r.assigned}` : "Everyone is already assigned");
                refresh();
              }}
              className="rounded-md bg-[var(--color-accent)] px-2.5 py-1 text-[11.5px] font-medium text-white transition-opacity hover:opacity-90"
            >
              Randomise unassigned
            </button>
          }
        >
          <div className="overflow-hidden rounded-lg border border-[var(--color-margin-edge)] bg-white">
            {participants.length === 0 ? (
              <p className="px-3.5 py-6 text-center text-[11.5px] text-[var(--color-ink-faint)]">
                No participants yet. They appear here once a student signs in.
              </p>
            ) : participants.map((p) => (
              <div key={p.user_id}
                   className="flex items-center gap-3 border-b border-[var(--color-margin-edge)] px-3.5 py-2 last:border-0">
                <span className="w-[120px] shrink-0 truncate text-[12px] text-[var(--color-ink)]">
                  {p.display_name}
                </span>
                <span className="shrink-0 font-mono text-[10px] text-[var(--color-ink-faint)]">
                  {p.participant_code}
                </span>
                <select
                  value={p.arm_id || ""}
                  onChange={async (e) => {
                    await api.assign({ user_id: p.user_id, arm_id: e.target.value });
                    note(`${p.display_name} → ${arms.find((a) => a.arm_id === e.target.value)?.name}`);
                    refresh();
                  }}
                  className="ml-auto rounded border border-[var(--color-margin-edge)] bg-white px-2 py-1 font-mono text-[10.5px] text-[var(--color-ink-soft)]"
                >
                  <option value="">unassigned → default</option>
                  {arms.map((a) => <option key={a.arm_id} value={a.arm_id}>{a.name}</option>)}
                </select>
              </div>
            ))}
          </div>
        </Section>

        {/* ---- 04 what happened ------------------------------------------- */}
        <Section n="04" title="Results" hint="change one variable, read the effect">
          <OutcomeTable arms={cmp?.arms ?? []} />
          {cmp && (
            <details className="group mt-2.5">
              <summary className="cursor-pointer list-none font-mono text-[10px] text-[var(--color-ink-faint)] hover:text-[var(--color-ink-soft)]">
                <span className="group-open:hidden">▸</span><span className="hidden group-open:inline">▾</span> how each measure is defined
              </summary>
              <dl className="mt-2 space-y-1.5 rounded-lg border border-[var(--color-margin-edge)] bg-white p-3">
                {Object.entries(cmp.measures).map(([k, v]) => (
                  <div key={k}>
                    <dt className="font-mono text-[10.5px] text-[var(--color-ink-soft)]">{k}</dt>
                    <dd className="text-[11px] leading-snug text-[var(--color-ink-faint)]">{v}</dd>
                  </div>
                ))}
              </dl>
            </details>
          )}
        </Section>
      </main>
    </div>
  );
}
