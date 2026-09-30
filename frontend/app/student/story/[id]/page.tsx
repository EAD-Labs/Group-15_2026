"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, streamTurn } from "@/lib/api";
import type { Turn, Workspace } from "@/lib/types";
import { TEXT_SIZES, useStudentPrefs, type StudentPrefs } from "@/lib/prefs";
import { Conversation } from "@/components/Chat";
import { StoryEditor, type Range, type StoryEditorHandle } from "@/components/StoryEditor";
import { ThemeButton, ToolButton } from "@/components/StudentTools";
import { usePortal } from "@/components/PortalGuard";

const SAVE_DEBOUNCE = 900;

// What the student sees while the graph runs. Plain language, and never the
// writing activity - naming a "current phase" is exactly what the design
// rules out (CLAUDE.md: no phase indicator).
const STATUS: Record<string, string> = {
  intent_classifier: "Reading your question…",
  activity_monitor: "Looking at your draft…",
  role_arbiter: "Looking at your draft…",
  response_engine: "Thinking it through…",
  response_formatter: "Almost there…",
  agency_enforcer: "Almost there…",
};

/**
 * The student workspace: the story, and the partner. Nothing else.
 *
 * Everything the study needs - help-seeking and activity classification, the
 * Monitor's decision, agency, telemetry - is still computed per turn on the
 * server and read in the researcher portal. None of it is shown here, and the
 * student has no controls over the model, scaffold or writing activity. What
 * they do control is comfort: night mode, text size, focus mode.
 */
export default function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, checked } = usePortal("student");
  const { prefs, update } = useStudentPrefs();

  const [ws, setWs] = useState<Workspace | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [draft, setDraft] = useState("");
  const [message, setMessage] = useState("");
  const [thinking, setThinking] = useState(false);
  const [status, setStatus] = useState("");
  const [freshId, setFreshId] = useState("");
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [selection, setSelection] = useState("");
  const [pending, setPending] = useState<Range | null>(null);
  const [anchor, setAnchor] = useState<Range | null>(null);

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const keystrokes = useRef(0);
  const lastLen = useRef(0);
  const editorRef = useRef<StoryEditorHandle>(null);

  // ---- load -------------------------------------------------------------
  useEffect(() => {
    if (!checked) return;
    (async () => {
      const [w, t] = await Promise.all([api.getWorkspace(id), api.turns(id)]);
      setWs(w);
      setDraft(w.current_content);
      lastLen.current = w.current_content.length;
      setTurns(t);
    })().catch(console.error);
  }, [id, checked]);

  // Scroll to a passage once its highlight has rendered.
  useEffect(() => { if (anchor) editorRef.current?.revealAnchor(); }, [anchor]);

  // ---- autosave + keystroke telemetry ------------------------------------
  const onDraftChange = (value: string) => {
    setDraft(value);
    setAnchor(null); // offsets would drift as the text changes
    keystrokes.current += 1;
    setSaving("saving");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const delta = value.length - lastLen.current;
      lastLen.current = value.length;
      await api.updateWorkspace(id, { current_content: value });
      // Batched rather than per-keypress: HLD 11.1 requires zero input lag.
      api.logEvent({
        workspace_id: id,
        event_type: Math.abs(delta) > 120 ? "paste" : "keystroke",
        delta_change: delta,
        payload: { keystrokes: keystrokes.current, length: value.length },
      });
      keystrokes.current = 0;
      setSaving("saved");
      setTimeout(() => setSaving("idle"), 1400);
    }, SAVE_DEBOUNCE);
  };

  /* Selection-scoped asking (C&C '24 §3.2). Also one of the Monitor's
     signals: asking about a highlighted passage is working on existing text.
     The range stays highlighted while the writer types their question. */
  const captureSelection = () => {
    const r = editorRef.current?.selectionRange();
    if (!r) return;
    const picked = draft.slice(r.start, r.end);
    if (picked.trim().length >= 8) {
      setSelection(picked.trim());
      setPending(r);
    } else {
      setSelection("");
      setPending(null);
    }
  };

  const clearSelection = () => { setSelection(""); setPending(null); };

  /** Margin note → story: highlight the passage it was about. */
  const showPassage = (passage: string) => {
    const at = draft.indexOf(passage);
    if (at < 0) return false;
    setAnchor({ start: at, end: at + passage.length });
    api.logEvent({ workspace_id: id, event_type: "anchor_revisited", payload: { length: passage.length } });
    return true;
  };

  // ---- take a turn -------------------------------------------------------
  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || thinking) return;
      setMessage("");
      setThinking(true);
      setStatus(STATUS.intent_classifier);

      const optimistic: Turn = {
        turn_id: `tmp-${Date.now()}`, speaker: "user", message_text: text,
        selection, intent_type: "", cognitive_activity: "", intercepted: false,
        node_path: [], suggestions: [],
        provider: "", model_name: "", latency_ms: 0, timestamp: new Date().toISOString(),
      };
      setTurns((prev) => [...prev, optimistic]);

      try {
        const result = await streamTurn(id, { message: text, draft, selection }, (node, st) => {
          if (st === "running" && STATUS[node]) setStatus(STATUS[node]);
        });
        setTurns((prev) =>
          prev.concat({
            turn_id: result.turn_id, speaker: "ai", message_text: result.response_text,
            intent_type: result.intent, cognitive_activity: result.cognitive,
            intercepted: result.intercepted,
            node_path: result.node_path, suggestions: result.probes,
            provider: result.provider, model_name: result.model_name,
            latency_ms: result.latency_ms, timestamp: new Date().toISOString(),
          }),
        );
        setFreshId(result.turn_id);
        clearSelection();
      } catch (err) {
        console.error(err);
        setTurns((prev) => prev.filter((t) => t.turn_id !== optimistic.turn_id));
        setMessage(text);
      } finally {
        setThinking(false);
      }
    },
    [id, draft, thinking, selection],
  );

  const theme = prefs.theme;
  const fontSize = TEXT_SIZES[prefs.textSize] ?? 18;
  const words = draft.trim() ? draft.trim().split(/\s+/).length : 0;

  const setPref = <K extends keyof StudentPrefs>(key: K, value: StudentPrefs[K]) => {
    update(key, value);
    api.logEvent({ workspace_id: id, event_type: "preference_change", payload: { [key]: value } });
  };

  if (!checked || !user || !ws) {
    return (
      <div className="student flex h-screen items-center justify-center bg-[var(--color-desk)]" data-theme={theme}>
        <div className="h-1 w-32 overflow-hidden rounded-full bg-[var(--color-desk-edge)]">
          <div className="animate-sweep h-full w-1/3 rounded-full bg-[var(--color-ink-blue)]" />
        </div>
      </div>
    );
  }

  return (
    <div className="student flex h-screen flex-col bg-[var(--color-desk)] md:flex-row" data-theme={theme}>
      {/* the story - a sheet on the desk */}
      <section className="thin-scroll flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
        <div className="flex items-center gap-1 px-5 pt-4 md:px-8">
          <Link
            href="/student"
            className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[13px] text-[var(--color-graphite)] transition-colors hover:bg-[var(--color-desk-edge)]/60 hover:text-[var(--color-ink)]"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <path d="M15 18l-6-6 6-6" />
            </svg>
            Your stories
          </Link>

          <span className="ml-auto mr-2 text-[12.5px] text-[var(--color-graphite)]" aria-live="polite">
            {saving === "saving" ? "Saving…" : saving === "saved" ? "Saved" : ""}
          </span>

          <ToolButton
            label={prefs.focus ? "Turn off focus mode" : "Focus mode: fade everything but the paragraph you're writing"}
            pressed={prefs.focus}
            onClick={() => setPref("focus", !prefs.focus)}
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="1.9" strokeLinecap="round" aria-hidden>
              <path d="M4 6h16" opacity=".35" /><path d="M4 12h16" /><path d="M4 18h16" opacity=".35" />
            </svg>
          </ToolButton>
          <ToolButton
            label="Smaller text"
            disabled={prefs.textSize <= 0}
            onClick={() => setPref("textSize", prefs.textSize - 1)}
          >
            <span className="font-serif text-[13px]">A</span>
          </ToolButton>
          <ToolButton
            label="Larger text"
            disabled={prefs.textSize >= TEXT_SIZES.length - 1}
            onClick={() => setPref("textSize", prefs.textSize + 1)}
          >
            <span className="font-serif text-[17px]">A</span>
          </ToolButton>
          <ThemeButton theme={theme} onToggle={() => setPref("theme", theme === "night" ? "day" : "night")} />
        </div>

        <div className="flex flex-1 justify-center px-3 pb-6 pt-3 md:px-8 md:pb-10">
          <article className="sheet flex h-fit w-full max-w-[46rem] flex-col px-7 pb-8 pt-10 sm:px-16 sm:pt-14">
            <input
              value={ws.title}
              onChange={(e) => setWs({ ...ws, title: e.target.value })}
              onBlur={(e) => api.updateWorkspace(id, { title: e.target.value })}
              aria-label="Story title"
              className="w-full bg-transparent font-serif text-[30px] font-medium leading-tight tracking-tight text-[var(--color-ink)] outline-none sm:text-[36px]"
            />
            <div className="mb-6 mt-4 h-px w-12 bg-[var(--color-ink-blue)]/40" aria-hidden />

            <StoryEditor
              ref={editorRef}
              value={draft}
              onChange={onDraftChange}
              onSelectionChange={captureSelection}
              fontSize={fontSize}
              focusMode={prefs.focus}
              pending={pending}
              anchor={anchor}
            />

            <p className="mt-8 text-right text-[12px] tabular-nums text-[var(--color-graphite)]">
              {words.toLocaleString()} {words === 1 ? "word" : "words"}
            </p>
          </article>
        </div>
      </section>

      {/* the partner - notes in the margin */}
      <aside className="flex h-[45vh] shrink-0 flex-col border-t border-[var(--color-desk-edge)] md:h-auto md:w-[400px] md:border-l md:border-t-0 xl:w-[440px]">
        <Conversation
          turns={turns}
          thinking={thinking}
          status={status}
          freshId={freshId}
          onAnchor={showPassage}
        />

        <div className="shrink-0 px-4 pb-4 pt-2">
          {selection && (
            <div className="mb-2 flex items-center gap-2 rounded-md bg-[var(--color-ink-wash)] px-3 py-1.5 text-[12.5px] text-[var(--color-ink-blue)]">
              <span className="min-w-0 flex-1 truncate font-serif italic">
                Asking about “{selection}”
              </span>
              <button onClick={clearSelection} aria-label="Clear selection"
                      className="px-1 text-[15px] leading-none opacity-60 hover:opacity-100">
                ×
              </button>
            </div>
          )}
          <div className="flex items-end gap-2 rounded-xl bg-[var(--color-sheet)] p-1.5 shadow-[0_0_0_1px_rgba(30,37,50,0.08),0_4px_14px_-6px_rgba(30,37,50,0.2)] focus-within:shadow-[0_0_0_2px_var(--color-ink-blue)]">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(message);
                }
              }}
              rows={2}
              disabled={thinking}
              placeholder={selection ? "What do you want to know about it?" : "Ask your partner…"}
              aria-label="Message your writing partner"
              className="thin-scroll block flex-1 resize-none bg-transparent px-2.5 py-1.5 text-[14px] leading-relaxed text-[var(--color-ink)] placeholder:text-[var(--color-graphite)]/70 focus:outline-none disabled:opacity-50"
            />
            <button
              onClick={() => send(message)}
              disabled={thinking || !message.trim()}
              aria-label="Send"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[var(--color-ink-blue)] text-[var(--color-on-ink)] transition-opacity hover:opacity-90 disabled:opacity-25"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          </div>
        </div>
      </aside>
    </div>
  );
}
