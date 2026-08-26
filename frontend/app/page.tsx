"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { clearSession, loadSession, saveSession } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

type Role = "student" | "researcher";

const PORTALS: {
  role: Role;
  title: string;
  blurb: string;
  bullets: string[];
}[] = [
  {
    role: "student",
    title: "Student",
    blurb: "Write, and be asked better questions about what you wrote.",
    bullets: [
      "A split-screen workspace you fully control",
      "A partner that will not write your story",
      "Export your story and the whole conversation",
    ],
  },
  {
    role: "researcher",
    title: "Researcher",
    blurb: "Configure the study and read what the cohort actually did.",
    bullets: [
      "Swap models and edit the Socratic scaffold live",
      "Help-seeking and cognitive-process analytics",
      "Anonymised JSON / CSV interaction datasets",
    ],
  },
];

export default function Entry() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("student");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [existing, setExisting] = useState<SessionUser | null>(null);

  useEffect(() => setExisting(loadSession()), []);

  const go = (u: SessionUser) => router.push(u.role === "researcher" ? "/researcher" : "/student");

  const enter = async () => {
    setBusy(true);
    try {
      const user = await api.signIn(name.trim(), role);
      saveSession(user);
      go(user);
    } finally {
      setBusy(false);
    }
  };

  const active = PORTALS.find((p) => p.role === role)!;

  return (
    <div className="flex min-h-screen flex-col bg-[var(--color-margin)]">
      <main className="mx-auto flex w-full max-w-4xl flex-1 flex-col justify-center px-6 py-12">
        <div className="mb-9">
          <div className="mb-5 flex items-center gap-2.5">
            <div className="flex h-6 w-6 items-center justify-center rounded bg-[var(--color-accent)]">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2"
                   strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>
            <span className="text-[13.5px] font-semibold tracking-tight text-[var(--color-ink)]">
              Story Studio
            </span>
          </div>

          <h1 className="max-w-2xl font-serif text-[32px] leading-[1.22] tracking-tight text-[var(--color-ink)]">
            A writing partner that asks instead of answers.
          </h1>
          <p className="mt-3 max-w-lg text-[13.5px] leading-relaxed text-[var(--color-ink-soft)]">
            Human–AI co-creative storytelling for higher education. Choose how
            you are entering — the two portals show different things.
          </p>
        </div>

        {existing && (
          <div className="animate-rise mb-5 flex items-center gap-3 rounded-lg border border-[var(--color-accent-line)] bg-[var(--color-accent-soft)] px-4 py-2.5">
            <span className="text-[12.5px] text-[var(--color-accent)]">
              Signed in as <strong>{existing.display_name}</strong>
              {existing.participant_code ? ` (${existing.participant_code})` : ""} ·{" "}
              {existing.role}
            </span>
            <button
              onClick={() => go(existing)}
              className="ml-auto rounded-md bg-[var(--color-accent)] px-2.5 py-1 text-[11.5px] font-medium text-white transition-opacity hover:opacity-90"
            >
              Continue
            </button>
            <button
              onClick={() => { clearSession(); setExisting(null); }}
              className="text-[11.5px] text-[var(--color-accent)]/70 hover:text-[var(--color-accent)]"
            >
              switch
            </button>
          </div>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {PORTALS.map((p) => {
            const on = role === p.role;
            return (
              <button
                key={p.role}
                onClick={() => setRole(p.role)}
                className={[
                  "flex flex-col rounded-xl border p-5 text-left transition-all",
                  on
                    ? "border-[var(--color-accent)] bg-[var(--color-accent-soft)]"
                    : "border-[var(--color-margin-edge)] bg-white hover:border-[var(--color-accent-line)]",
                ].join(" ")}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={[
                      "flex h-3.5 w-3.5 items-center justify-center rounded-full border transition-colors",
                      on
                        ? "border-[var(--color-accent)] bg-[var(--color-accent)]"
                        : "border-[var(--color-margin-edge)]",
                    ].join(" ")}
                  >
                    {on && <span className="h-1 w-1 rounded-full bg-white" />}
                  </span>
                  <span className={`text-[14px] font-semibold ${on ? "text-[var(--color-accent)]" : "text-[var(--color-ink)]"}`}>
                    {p.title}
                  </span>
                </div>
                <p className="mt-2 text-[12.5px] leading-snug text-[var(--color-ink-soft)]">
                  {p.blurb}
                </p>
                <ul className="mt-3 space-y-1">
                  {p.bullets.map((b) => (
                    <li key={b} className="flex gap-1.5 text-[11.5px] leading-snug text-[var(--color-ink-faint)]">
                      <span className="mt-[6px] h-1 w-1 shrink-0 rounded-full bg-[var(--color-ink-faint)]" />
                      {b}
                    </li>
                  ))}
                </ul>
              </button>
            );
          })}
        </div>

        <div className="mt-5 flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1">
            <label className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
              your name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && enter()}
              placeholder={active.role === "researcher" ? "e.g. Florence Lehnert" : "e.g. Tushar Bajaj"}
              className="mt-1.5 w-full rounded-lg border border-[var(--color-margin-edge)] bg-white px-3 py-2 text-[13px] text-[var(--color-ink)] outline-none focus:border-[var(--color-accent-line)] focus:ring-2 focus:ring-[var(--color-accent-soft)]"
            />
          </div>
          <button
            onClick={enter}
            disabled={busy}
            className="rounded-lg bg-[var(--color-accent)] px-5 py-2 text-[13px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
          >
            {busy ? "Entering…" : `Enter as ${active.title.toLowerCase()}`}
          </button>
        </div>

        <p className="mt-4 text-[11px] leading-relaxed text-[var(--color-ink-faint)]">
          Prototype sign-in: no password, stored only in this browser. Students
          are assigned a Participant_NN code that replaces their name in every
          research export.
        </p>
      </main>

      <footer className="border-t border-[var(--color-margin-edge)] px-6 py-3 text-center font-mono text-[10px] text-[var(--color-ink-faint)]">
        ET 617 · Group 15 · Human–AI Co-Creative Storytelling
      </footer>
    </div>
  );
}
