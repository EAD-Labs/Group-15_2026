"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { SessionUser, Summary, TelemetryEvent, TimelinePoint } from "@/lib/types";
import { IntentChart } from "@/components/IntentChart";
import { CognitiveChart } from "@/components/CognitiveChart";
import { AgencyMeter } from "@/components/AgencyMeter";
import { CognitiveTimeline } from "@/components/CognitiveTimeline";
import { PortalHeader } from "@/components/PortalHeader";
import { PortalLoading, usePortal } from "@/components/PortalGuard";

function Section({ n, title, hint, children }: {
  n: string; title: string; hint: string; children: React.ReactNode;
}) {
  return (
    <section className="mb-8">
      <div className="mb-3 flex items-baseline gap-2.5">
        <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">{n}</span>
        <h2 className="text-[13.5px] font-semibold text-[var(--color-ink)]">{title}</h2>
        <span className="text-[11px] text-[var(--color-ink-faint)]">{hint}</span>
      </div>
      {children}
    </section>
  );
}

export default function DataPage() {
  const { user, checked } = usePortal("researcher");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [events, setEvents] = useState<TelemetryEvent[]>([]);
  const [timeline, setTimeline] = useState<TimelinePoint[]>([]);
  const [participants, setParticipants] = useState<SessionUser[]>([]);
  const [scope, setScope] = useState("");
  const [live, setLive] = useState(true);

  const refresh = useCallback(async (workspaceId: string) => {
    const [s, e, t, p] = await Promise.all([
      api.summary(),
      api.events(60, workspaceId),
      api.timeline(workspaceId),
      api.participants(),
    ]);
    setSummary(s); setEvents(e); setTimeline(t); setParticipants(p);
  }, []);

  useEffect(() => {
    if (!checked) return;
    refresh(scope).catch(console.error);
  }, [checked, scope, refresh]);

  useEffect(() => {
    if (!live || !checked) return;
    const t = setInterval(() => refresh(scope).catch(() => {}), 4000);
    return () => clearInterval(t);
  }, [live, checked, scope, refresh]);

  if (!checked || !user) return <PortalLoading />;

  const scopeLabel =
    summary?.per_workspace.find((w) => w.workspace_id === scope)?.title ?? "All sessions";

  return (
    <div className="min-h-screen bg-[var(--color-margin)]">
      <PortalHeader
        user={user}
        tabs={[
          { href: "/researcher", label: "Study", active: false },
          { href: "/researcher/data", label: "Data", active: true },
        ]}
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

      <main className="mx-auto max-w-5xl px-6 py-8">
        {/* scope filter - one row above the charts */}
        <div className="mb-6 flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
            scope
          </span>
          <button
            onClick={() => setScope("")}
            className={[
              "rounded-md px-2.5 py-1 text-[11.5px] transition-colors",
              !scope ? "bg-[var(--color-accent)] text-white"
                     : "bg-white text-[var(--color-ink-soft)] hover:bg-[var(--color-margin-deep)]",
            ].join(" ")}
          >
            All sessions
          </button>
          {summary?.per_workspace.map((w) => (
            <button
              key={w.workspace_id}
              onClick={() => setScope(w.workspace_id)}
              className={[
                "max-w-[190px] truncate rounded-md px-2.5 py-1 text-[11.5px] transition-colors",
                scope === w.workspace_id
                  ? "bg-[var(--color-accent)] text-white"
                  : "bg-white text-[var(--color-ink-soft)] hover:bg-[var(--color-margin-deep)]",
              ].join(" ")}
            >
              {w.title}
            </button>
          ))}
          <span className="ml-auto font-mono text-[10px] text-[var(--color-ink-faint)]">
            {participants.length} participant{participants.length === 1 ? "" : "s"}
          </span>
        </div>

        <Section
          n="01"
          title="Writing process over time"
          hint={`${scopeLabel} · reproduces Chakrabarty et al. Fig. 6`}
        >
          <div className="rounded-lg border border-[var(--color-margin-edge)] bg-white p-4">
            <CognitiveTimeline points={timeline} />
          </div>
        </Section>

        <Section n="02" title="How students asked" hint="both classification axes, across the current scope">
          <div className="grid gap-2.5 lg:grid-cols-2">
            <div className="rounded-lg border border-[var(--color-margin-edge)] bg-white p-4">
              <h3 className="mb-3 text-[12px] font-medium text-[var(--color-ink)]">
                Help-seeking
              </h3>
              <IntentChart data={summary?.intent_distribution ?? {}} />
            </div>
            <div className="rounded-lg border border-[var(--color-margin-edge)] bg-white p-4">
              <h3 className="mb-3 text-[12px] font-medium text-[var(--color-ink)]">
                Cognitive activity
              </h3>
              <CognitiveChart data={summary?.cognitive_distribution ?? {}} />
            </div>
          </div>
          {summary && Object.keys(summary.enforcement_actions).length > 0 && (
            <div className="mt-2.5 rounded-lg border border-[var(--color-flag-line)] bg-[var(--color-flag-soft)] p-3.5">
              <h3 className="text-[11.5px] font-medium text-[var(--color-flag)]">
                Agency Enforcer actions
              </h3>
              <p className="mt-1 text-[10.5px] text-[var(--color-flag)]/75">
                Times the post-hoc filter stripped narrative prose a model tried to emit.
              </p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {Object.entries(summary.enforcement_actions).map(([k, v]) => (
                  <span key={k} className="rounded bg-white/70 px-2 py-0.5 font-mono text-[10px] text-[var(--color-flag)]">
                    {k.replace(/_/g, " ")} · {v}
                  </span>
                ))}
              </div>
            </div>
          )}
        </Section>

        <Section n="03" title="Sessions" hint="agency retention and model contribution per workspace">
          <div className="overflow-x-auto rounded-lg border border-[var(--color-margin-edge)] bg-white">
            <table className="w-full min-w-[620px] text-left">
              <thead>
                <tr className="border-b border-[var(--color-margin-edge)] font-mono text-[10px] uppercase tracking-wider text-[var(--color-ink-faint)]">
                  <th className="px-3.5 py-2 font-normal">story</th>
                  <th className="px-3.5 py-2 font-normal">mode</th>
                  <th className="px-3.5 py-2 text-right font-normal">words</th>
                  <th className="px-3.5 py-2 text-right font-normal">turns</th>
                  <th className="px-3.5 py-2 text-right font-normal" title="ROUGE-L recall of AI output inside the draft">
                    ai retention
                  </th>
                  <th className="px-3.5 py-2 text-right font-normal">agency</th>
                </tr>
              </thead>
              <tbody>
                {(summary?.per_workspace ?? []).map((w) => (
                  <tr key={w.workspace_id} className="border-b border-[var(--color-margin-edge)] last:border-0">
                    <td className="max-w-[190px] truncate px-3.5 py-2.5 text-[12px] text-[var(--color-ink)]">
                      <button onClick={() => setScope(w.workspace_id)} className="hover:text-[var(--color-accent)] hover:underline">
                        {w.title}
                      </button>
                    </td>
                    <td className="px-3.5 py-2.5 font-mono text-[10.5px] text-[var(--color-ink-faint)]">
                      {w.mode.replace(/_/g, " ")}
                    </td>
                    <td className="px-3.5 py-2.5 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">{w.words}</td>
                    <td className="px-3.5 py-2.5 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">{w.turns}</td>
                    <td className="px-3.5 py-2.5 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">
                      {Math.round((w.ai_retention ?? 0) * 100)}%
                    </td>
                    <td className="px-3.5 py-2.5">
                      <div className="flex items-center justify-end gap-2">
                        <AgencyMeter ratio={w.agency_ratio} size={20} showLabel={false} />
                        <span className="w-8 text-right font-mono text-[11px] tabular-nums text-[var(--color-ink-soft)]">
                          {Math.round(w.agency_ratio * 100)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
                {(summary?.per_workspace ?? []).length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-3.5 py-8 text-center text-[11.5px] text-[var(--color-ink-faint)]">
                      No sessions yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Section>

        <Section n="04" title="Event stream" hint={`${summary?.event_count ?? 0} events captured`}>
          <div className="mb-2.5 flex flex-wrap gap-2">
            <a href="/api/research/export.json"
               className="rounded-md border border-[var(--color-margin-edge)] bg-white px-3 py-1.5 font-mono text-[11px] text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:text-[var(--color-accent)]">
              ↓ export.json
            </a>
            <a href="/api/research/export.csv"
               className="rounded-md border border-[var(--color-margin-edge)] bg-white px-3 py-1.5 font-mono text-[11px] text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:text-[var(--color-accent)]">
              ↓ export.csv
            </a>
            <span className="self-center text-[10.5px] text-[var(--color-ink-faint)]">
              Names replaced with Participant_NN on export.
            </span>
          </div>

          <div className="thin-scroll max-h-[320px] overflow-y-auto rounded-lg border border-[var(--color-margin-edge)] bg-white">
            {events.length === 0 ? (
              <p className="px-3.5 py-6 text-center text-[11.5px] text-[var(--color-ink-faint)]">
                No events in scope yet.
              </p>
            ) : (
              events.map((e) => (
                <div key={e.event_id}
                     className="flex items-center gap-2.5 border-b border-[var(--color-margin-edge)] px-3.5 py-1.5 font-mono text-[10.5px] last:border-0">
                  <span className="w-[62px] shrink-0 tabular-nums text-[var(--color-ink-faint)]">
                    {new Date(e.timestamp + "Z").toLocaleTimeString("en-GB", {
                      hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit",
                    })}
                  </span>
                  <span className={[
                    "w-[104px] shrink-0 truncate rounded px-1.5 py-0.5",
                    e.event_type === "intercept"
                      ? "bg-[var(--color-flag-soft)] text-[var(--color-flag)]"
                      : "bg-[var(--color-margin-deep)] text-[var(--color-ink-soft)]",
                  ].join(" ")}>
                    {e.event_type}
                  </span>
                  <span className="truncate text-[var(--color-ink-faint)]">
                    {typeof e.payload?.intent === "string" ? `${e.payload.intent} ` : ""}
                    {typeof e.payload?.cognitive === "string" ? `· ${e.payload.cognitive} ` : ""}
                    {e.delta_change ? `Δ${e.delta_change > 0 ? "+" : ""}${e.delta_change} ` : ""}
                    {e.duration_ms ? `${e.duration_ms}ms ` : ""}
                    {typeof e.payload?.model === "string" ? e.payload.model : ""}
                  </span>
                </div>
              ))
            )}
          </div>
        </Section>

        <p className="text-[10.5px] leading-relaxed text-[var(--color-ink-faint)]">
          Agency = 1 − (draft 5-grams also found in AI output) ÷ draft 5-grams. AI
          retention = ROUGE-L recall of AI output within the draft, the statistic
          used by{" "}
          <Link href="https://doi.org/10.1145/3635636.3656201" target="_blank"
                className="underline underline-offset-2 hover:text-[var(--color-accent)]">
            Chakrabarty et al., C&amp;C ’24
          </Link>
          . Both ship with raw counts in every export.
        </p>
      </main>
    </div>
  );
}
