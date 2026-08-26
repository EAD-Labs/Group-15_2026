"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Mode, Workspace } from "@/lib/types";
import { AgencyMeter } from "@/components/AgencyMeter";
import { PortalHeader } from "@/components/PortalHeader";
import { PortalLoading, usePortal } from "@/components/PortalGuard";

function timeAgo(iso: string) {
  const mins = Math.floor((Date.now() - new Date(iso + "Z").getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const h = Math.floor(mins / 60);
  return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
}

export default function StudentPortal() {
  const { user, checked } = usePortal("student");
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [modes, setModes] = useState<Mode[]>([]);
  const [composing, setComposing] = useState(false);
  const [mode, setMode] = useState("educational_narrative");
  const [title, setTitle] = useState("");
  const [seed, setSeed] = useState("");
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!checked) return;
    Promise.all([api.listWorkspaces(), api.modes()])
      .then(([w, m]) => { setWorkspaces(w); setModes(m); })
      .catch(console.error)
      .finally(() => setLoaded(true));
  }, [checked]);

  if (!checked || !user) return <PortalLoading />;

  const active = modes.find((m) => m.id === mode);

  const create = async () => {
    setBusy(true);
    try {
      const ws = await api.createWorkspace({
        title: title.trim() || "Untitled Story",
        initial_prompt: seed.trim(),
        mode,
      });
      router.push(`/student/story/${ws.workspace_id}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[var(--color-margin)]">
      <PortalHeader user={user} />

      <main className="mx-auto max-w-5xl px-6 py-9">
        {!composing ? (
          <div className="mb-9">
            <h1 className="max-w-2xl font-serif text-[27px] leading-[1.28] tracking-tight text-[var(--color-ink)]">
              Welcome back, {user.display_name.split(" ")[0]}.
            </h1>
            <p className="mt-2.5 max-w-lg text-[13.5px] leading-relaxed text-[var(--color-ink-soft)]">
              Every word in your story stays yours. When you ask this AI to write
              for you, it will decline — and give you the question that gets you
              unstuck instead.
            </p>
            <button
              onClick={() => setComposing(true)}
              className="mt-5 rounded-lg bg-[var(--color-accent)] px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90"
            >
              Start a new story
            </button>
          </div>
        ) : (
          <div className="animate-rise mb-9 rounded-xl border border-[var(--color-margin-edge)] bg-white p-6">
            <div className="flex items-start justify-between">
              <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">New story</h2>
              <button onClick={() => setComposing(false)}
                      className="text-[11.5px] text-[var(--color-ink-faint)] hover:text-[var(--color-ink)]">
                cancel
              </button>
            </div>

            <div className="mt-5">
              <label className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
                what kind of piece
              </label>
              <div className="mt-2 grid gap-2 sm:grid-cols-3">
                {modes.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => { setMode(m.id); setSeed(""); }}
                    className={[
                      "flex flex-col rounded-lg border p-3 text-left transition-all",
                      mode === m.id
                        ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]"
                        : "border-[var(--color-margin-edge)] hover:border-[var(--color-accent-line)]",
                    ].join(" ")}
                  >
                    <div className={`text-[12.5px] font-medium ${mode === m.id ? "text-[var(--color-accent)]" : "text-[var(--color-ink)]"}`}>
                      {m.label}
                    </div>
                    <div className="mt-1 text-[11px] leading-snug text-[var(--color-ink-faint)]">
                      {m.blurb}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5">
              <label className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
                title
              </label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Untitled Story"
                className="mt-1.5 w-full rounded-lg border border-[var(--color-margin-edge)] px-3 py-2 text-[13px] text-[var(--color-ink)] outline-none focus:border-[var(--color-accent-line)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
              />
            </div>

            <div className="mt-5">
              <label className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
                opening line — write your own, or take one of these
              </label>
              <textarea
                value={seed}
                onChange={(e) => setSeed(e.target.value)}
                rows={3}
                placeholder="The first sentence, or just the idea you're chasing…"
                className="prose-editor mt-1.5 w-full resize-none rounded-lg border border-[var(--color-margin-edge)] px-3 py-2.5 text-[14px] outline-none focus:border-[var(--color-accent-line)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
              />
              <div className="mt-2 space-y-1.5">
                {active?.starters.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => setSeed(s)}
                    className="block w-full rounded-md border border-transparent bg-[var(--color-margin)] px-2.5 py-1.5 text-left font-serif text-[12.5px] leading-snug text-[var(--color-ink-soft)] transition-colors hover:border-[var(--color-accent-line)] hover:bg-[var(--color-accent-soft)] hover:text-[var(--color-accent)]"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>

            <button
              onClick={create}
              disabled={busy}
              className="mt-6 rounded-lg bg-[var(--color-accent)] px-4 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
            >
              {busy ? "Opening…" : "Open workspace"}
            </button>
          </div>
        )}

        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
            your stories
          </h2>
          {workspaces.length > 0 && (
            <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">{workspaces.length}</span>
          )}
        </div>

        {!loaded ? (
          <div className="h-1 w-24 overflow-hidden rounded-full bg-[var(--color-margin-deep)]">
            <div className="animate-sweep h-full w-1/3 rounded-full bg-[var(--color-accent)]" />
          </div>
        ) : workspaces.length === 0 ? (
          <div className="rounded-xl border border-dashed border-[var(--color-margin-edge)] px-6 py-10 text-center">
            <p className="text-[12.5px] text-[var(--color-ink-faint)]">
              Nothing here yet. Your stories and their conversation histories will collect here.
            </p>
          </div>
        ) : (
          <div className="grid gap-2.5 sm:grid-cols-2">
            {workspaces.map((w) => (
              <Link
                key={w.workspace_id}
                href={`/student/story/${w.workspace_id}`}
                className="group rounded-xl border border-[var(--color-margin-edge)] bg-white p-4 transition-all hover:border-[var(--color-accent-line)] hover:shadow-[0_2px_8px_rgba(28,25,23,0.05)]"
              >
                <div className="flex items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-[13.5px] font-medium text-[var(--color-ink)] group-hover:text-[var(--color-accent)]">
                      {w.title}
                    </div>
                    <p className="mt-1 line-clamp-2 font-serif text-[12px] leading-snug text-[var(--color-ink-faint)]">
                      {w.current_content || "Empty page."}
                    </p>
                  </div>
                  <AgencyMeter ratio={w.agency_ratio} size={28} showLabel={false} />
                </div>
                <div className="mt-3 flex items-center gap-2 font-mono text-[10px] text-[var(--color-ink-faint)]">
                  <span>{w.word_count}w</span><span>·</span>
                  <span>{Math.floor(w.turn_count / 2)} exchanges</span><span>·</span>
                  <span>{timeAgo(w.updated_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
