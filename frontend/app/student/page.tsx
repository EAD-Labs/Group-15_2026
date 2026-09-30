"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { StudentHeader } from "@/components/StudentHeader";
import { PortalLoading, usePortal } from "@/components/PortalGuard";

// No kind-of-piece picker for students; every story is written under one mode
// so the Tutor's lens stays constant across participants.
const STUDENT_MODE = "educational_narrative";

function edited(iso: string) {
  const mins = Math.floor((Date.now() - new Date(iso + "Z").getTime()) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins} min ago`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h} h ago`;
  const d = Math.floor(h / 24);
  return d === 1 ? "yesterday" : `${d} days ago`;
}

/**
 * The student's home, laid out as a notebook's contents page: each story is a
 * title running along a dotted leader to when it was last touched. Starting a
 * new story turns the top of the page into a fresh sheet - title, an optional
 * note to self, and the first line.
 *
 * Deliberately bare: no metrics, no modes, no starters.
 */
export default function StudentPortal() {
  const { user, checked } = usePortal("student");
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [firstLine, setFirstLine] = useState("");
  const [busy, setBusy] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!checked) return;
    api.listWorkspaces()
      .then(setWorkspaces)
      .catch(console.error)
      .finally(() => setLoaded(true));
  }, [checked]);

  useEffect(() => { if (composing) titleRef.current?.focus(); }, [composing]);

  if (!checked || !user) return <PortalLoading />;

  const ready = title.trim() && firstLine.trim();

  const create = async () => {
    if (!ready || busy) return;
    setBusy(true);
    try {
      const ws = await api.createWorkspace({
        title: title.trim(),
        initial_prompt: firstLine.trim(),
        notes: notes.trim(),
        mode: STUDENT_MODE,
      });
      router.push(`/student/story/${ws.workspace_id}`);
    } catch (err) {
      console.error(err);
      setBusy(false);
    }
  };

  return (
    <div className="student min-h-screen bg-[var(--color-desk)] pb-16">
      <StudentHeader user={user} />

      <main className="mx-auto max-w-3xl px-5">
        <div className="sheet px-7 py-9 sm:px-14 sm:py-12">
          <div className="flex items-end justify-between gap-4">
            <h1 className="font-serif text-[34px] font-medium leading-none tracking-tight text-[var(--color-ink)]">
              Your stories
            </h1>
            {!composing && (
              <button
                onClick={() => setComposing(true)}
                className="shrink-0 rounded-md bg-[var(--color-ink-blue)] px-4 py-2 text-[13.5px] font-medium text-white transition-opacity hover:opacity-90"
              >
                New story
              </button>
            )}
          </div>

          {composing && (
            <form
              onSubmit={(e) => { e.preventDefault(); create(); }}
              className="animate-rise mt-9 rounded-sm border border-[var(--color-desk-edge)] px-6 py-6 sm:px-8"
            >
              <input
                ref={titleRef}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Title"
                aria-label="Title"
                className="w-full border-b border-transparent bg-transparent pb-1 font-serif text-[26px] font-medium tracking-tight text-[var(--color-ink)] outline-none placeholder:text-[var(--color-desk-edge)] focus:border-[var(--color-desk-edge)]"
              />

              <label className="mt-6 block rounded-sm bg-[var(--color-ink-wash)] px-4 py-3">
                <span className="text-[12.5px] text-[var(--color-ink-blue)]">
                  A brief idea about your story <span className="opacity-60">(optional)</span>
                </span>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  rows={3}
                  placeholder="What it's about, what you're thinking, a journal entry — anything that helps your partner understand."
                  className="mt-1 block w-full resize-none bg-transparent text-[14px] leading-relaxed text-[var(--color-ink)] outline-none placeholder:text-[var(--color-graphite)]/60"
                />
              </label>

              <label className="mt-6 block">
                <span className="text-[12.5px] text-[var(--color-graphite)]">The first line of your story</span>
                <textarea
                  value={firstLine}
                  onChange={(e) => setFirstLine(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); create(); }
                  }}
                  rows={2}
                  className="prose-editor mt-1 block w-full resize-none border-b border-[var(--color-desk-edge)] bg-transparent pb-1 text-[18px] focus:border-[var(--color-ink-blue)]"
                />
              </label>

              <div className="mt-7 flex items-center gap-4">
                <button
                  type="submit"
                  disabled={!ready || busy}
                  className="rounded-md bg-[var(--color-ink-blue)] px-4 py-2 text-[13.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-35"
                >
                  {busy ? "Opening…" : "Start writing"}
                </button>
                <button
                  type="button"
                  onClick={() => setComposing(false)}
                  className="text-[13.5px] text-[var(--color-graphite)] hover:text-[var(--color-ink)]"
                >
                  Cancel
                </button>
                {!ready && (title || firstLine) && (
                  <span className="ml-auto text-[12px] text-[var(--color-graphite)]">
                    Add a title and a first line to begin
                  </span>
                )}
              </div>
            </form>
          )}

          <div className="mt-10">
            {!loaded ? (
              <div className="h-1 w-24 overflow-hidden rounded-full bg-[var(--color-desk)]">
                <div className="animate-sweep h-full w-1/3 rounded-full bg-[var(--color-ink-blue)]" />
              </div>
            ) : workspaces.length === 0 ? (
              !composing && (
                <p className="font-serif text-[17px] italic text-[var(--color-graphite)]">
                  Nothing here yet. Your first story starts with one line.
                </p>
              )
            ) : (
              <ol>
                {workspaces.map((w) => (
                  <li key={w.workspace_id} className="border-t border-[var(--color-desk)] first:border-t-0">
                    <Link
                      href={`/student/story/${w.workspace_id}`}
                      className="group block py-4"
                    >
                      <div className="flex items-baseline">
                        <span className="truncate font-serif text-[20px] text-[var(--color-ink)] transition-colors group-hover:text-[var(--color-ink-blue)]">
                          {w.title}
                        </span>
                        <span className="leader" aria-hidden />
                        <span className="shrink-0 text-[12.5px] text-[var(--color-graphite)]">
                          {edited(w.updated_at)}
                        </span>
                      </div>
                      <p className="mt-1 line-clamp-1 max-w-[60ch] font-serif text-[14.5px] italic text-[var(--color-graphite)]">
                        {w.current_content || "An empty page."}
                      </p>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
