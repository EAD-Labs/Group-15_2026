"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import type { Workspace } from "@/lib/types";
import { useStudentPrefs } from "@/lib/prefs";
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
 * Stories can be renamed and archived. Archiving is a status change, never a
 * delete: the story leaves the list but stays in the research data, and can
 * be restored.
 */
export default function StudentPortal() {
  const { user, checked } = usePortal("student");
  const { prefs, update } = useStudentPrefs();
  const router = useRouter();
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [composing, setComposing] = useState(false);
  const [title, setTitle] = useState("");
  const [notes, setNotes] = useState("");
  const [firstLine, setFirstLine] = useState("");
  const [busy, setBusy] = useState(false);
  const [renaming, setRenaming] = useState("");
  const [renameText, setRenameText] = useState("");
  const [showArchived, setShowArchived] = useState(false);
  const [undo, setUndo] = useState<Workspace | null>(null);
  const titleRef = useRef<HTMLInputElement>(null);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!checked) return;
    api.listWorkspaces()
      .then(setWorkspaces)
      .catch(console.error)
      .finally(() => setLoaded(true));
  }, [checked]);

  useEffect(() => { if (composing) titleRef.current?.focus(); }, [composing]);

  if (!checked || !user) return <PortalLoading />;

  const theme = prefs.theme;
  const active = workspaces.filter((w) => w.status !== "archived");
  const archived = workspaces.filter((w) => w.status === "archived");
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

  const replace = (w: Workspace) =>
    setWorkspaces((prev) => prev.map((x) => (x.workspace_id === w.workspace_id ? w : x)));

  const setStatus = async (w: Workspace, status: "active" | "archived") => {
    replace({ ...w, status });
    replace(await api.updateWorkspace(w.workspace_id, { status }));
    api.logEvent({
      workspace_id: w.workspace_id,
      event_type: status === "archived" ? "story_archived" : "story_restored",
    });
    if (status === "archived") {
      setUndo(w);
      if (undoTimer.current) clearTimeout(undoTimer.current);
      undoTimer.current = setTimeout(() => setUndo(null), 6000);
    } else {
      setUndo(null);
    }
  };

  const saveRename = async (w: Workspace) => {
    const next = renameText.trim();
    setRenaming("");
    if (!next || next === w.title) return;
    replace({ ...w, title: next });
    replace(await api.updateWorkspace(w.workspace_id, { title: next }));
    api.logEvent({ workspace_id: w.workspace_id, event_type: "story_renamed" });
  };

  const row = (w: Workspace, isArchived: boolean) => (
    <li key={w.workspace_id} className="group flex items-start gap-2 border-t border-[var(--color-desk)] py-4 first:border-t-0">
      {renaming === w.workspace_id ? (
        <form
          className="flex-1"
          onSubmit={(e) => { e.preventDefault(); saveRename(w); }}
        >
          <input
            autoFocus
            value={renameText}
            onChange={(e) => setRenameText(e.target.value)}
            onBlur={() => saveRename(w)}
            onKeyDown={(e) => e.key === "Escape" && setRenaming("")}
            aria-label="New title"
            className="w-full border-b border-[var(--color-ink-blue)] bg-transparent pb-0.5 font-serif text-[20px] text-[var(--color-ink)] outline-none"
          />
          <p className="mt-1 text-[12px] text-[var(--color-graphite)]">Press Enter to save, Esc to cancel</p>
        </form>
      ) : (
        <Link href={`/student/story/${w.workspace_id}`} className="min-w-0 flex-1">
          <div className="flex items-baseline">
            <span className={[
              "truncate font-serif text-[20px] transition-colors group-hover:text-[var(--color-ink-blue)]",
              isArchived ? "text-[var(--color-graphite)]" : "text-[var(--color-ink)]",
            ].join(" ")}>
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
      )}

      {renaming !== w.workspace_id && (
        <div className="flex shrink-0 gap-0.5 pt-1 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:group-focus-within:opacity-100">
          {isArchived ? (
            <RowAction onClick={() => setStatus(w, "active")}>Restore</RowAction>
          ) : (
            <>
              <RowAction onClick={() => { setRenaming(w.workspace_id); setRenameText(w.title); }}>
                Rename
              </RowAction>
              <RowAction onClick={() => setStatus(w, "archived")}>Archive</RowAction>
            </>
          )}
        </div>
      )}
    </li>
  );

  return (
    <div className="student min-h-screen bg-[var(--color-desk)] pb-16" data-theme={theme}>
      <StudentHeader
        user={user}
        theme={theme}
        onTheme={() => update("theme", theme === "night" ? "day" : "night")}
      />

      <main className="mx-auto max-w-3xl px-5">
        <div className="sheet px-7 py-9 sm:px-14 sm:py-12">
          <div className="flex items-end justify-between gap-4">
            <h1 className="font-serif text-[34px] font-medium leading-none tracking-tight text-[var(--color-ink)]">
              Your stories
            </h1>
            {!composing && (
              <button
                onClick={() => setComposing(true)}
                className="shrink-0 rounded-md bg-[var(--color-ink-blue)] px-4 py-2 text-[13.5px] font-medium text-[var(--color-on-ink)] transition-opacity hover:opacity-90"
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
                  className="rounded-md bg-[var(--color-ink-blue)] px-4 py-2 text-[13.5px] font-medium text-[var(--color-on-ink)] transition-opacity hover:opacity-90 disabled:opacity-35"
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
            ) : active.length === 0 ? (
              !composing && (
                <p className="font-serif text-[17px] italic text-[var(--color-graphite)]">
                  Nothing here yet. Your first story starts with one line.
                </p>
              )
            ) : (
              <ol>{active.map((w) => row(w, false))}</ol>
            )}
          </div>

          {archived.length > 0 && (
            <div className="mt-8 border-t border-[var(--color-desk)] pt-5">
              <button
                onClick={() => setShowArchived((v) => !v)}
                aria-expanded={showArchived}
                className="text-[13px] text-[var(--color-graphite)] hover:text-[var(--color-ink)]"
              >
                {showArchived ? "Hide archived stories" : `Archived stories (${archived.length})`}
              </button>
              {showArchived && <ol className="mt-2">{archived.map((w) => row(w, true))}</ol>}
            </div>
          )}
        </div>
      </main>

      {undo && (
        <div role="status"
             className="animate-rise fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-4 rounded-lg bg-[var(--color-ink)] px-4 py-2.5 text-[13px] text-[var(--color-sheet)] shadow-lg">
          <span className="max-w-[40ch] truncate">“{undo.title}” archived</span>
          <button
            onClick={() => setStatus(undo, "active")}
            className="font-medium underline underline-offset-2 hover:no-underline"
          >
            Undo
          </button>
        </div>
      )}
    </div>
  );
}

function RowAction({ onClick, children }: { onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="rounded-md px-2 py-1 text-[12.5px] text-[var(--color-graphite)] transition-colors hover:bg-[var(--color-desk)] hover:text-[var(--color-ink)]"
    >
      {children}
    </button>
  );
}
