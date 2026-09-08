"use client";

import { use, useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api, streamTurn } from "@/lib/api";
import type { DeclaredActivity, GraphNode, Intensity, StudentOptions, Turn, Workspace } from "@/lib/types";
import type { NodeStatus } from "@/components/NodePipeline";
import { AgencyMeter } from "@/components/AgencyMeter";
import { ActivityControl } from "@/components/ActivityControl";
import { Conversation } from "@/components/Chat";
import { ExportDialog } from "@/components/ExportDialog";
import { TemplateRail } from "@/components/TemplateRail";
import { ScaffoldControl } from "@/components/ScaffoldControl";
import { usePortal } from "@/components/PortalGuard";

const SAVE_DEBOUNCE = 900;

export default function WorkspacePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { user, checked } = usePortal("student");

  const [ws, setWs] = useState<Workspace | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [graph, setGraph] = useState<GraphNode[]>([]);
  const [draft, setDraft] = useState("");
  const [goals, setGoals] = useState("");
  const [message, setMessage] = useState("");
  const [probes, setProbes] = useState<string[]>([]);
  const [thinking, setThinking] = useState(false);
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatus>>({});
  const [liveIntent, setLiveIntent] = useState("");
  const [liveCognitive, setLiveCognitive] = useState("");
  const [liveIntercepted, setLiveIntercepted] = useState(false);
  const [saving, setSaving] = useState<"idle" | "saving" | "saved">("idle");
  const [showExport, setShowExport] = useState(false);
  const [provider, setProvider] = useState("");
  const [selection, setSelection] = useState("");
  const [degraded, setDegraded] = useState("");
  const [intensity, setIntensity] = useState<Intensity>("balanced");
  const [modelOverride, setModelOverride] = useState("");
  const [options, setOptions] = useState<StudentOptions | null>(null);
  const [declaredActivity, setDeclaredActivity] = useState<DeclaredActivity>("");

  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const keystrokes = useRef(0);
  const lastLen = useRef(0);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const editorRef = useRef<HTMLTextAreaElement>(null);

  // ---- load -------------------------------------------------------------
  useEffect(() => {
    if (!checked) return;
    (async () => {
      const [w, t, g, cfg, o] = await Promise.all([
        api.getWorkspace(id), api.turns(id), api.graph(), api.config(), api.options(),
      ]);
      setOptions(o);
      setWs(w);
      setIntensity(w.scaffold_intensity ?? "balanced");
      setGoals(w.goals ?? "");
      setDraft(w.current_content);
      lastLen.current = w.current_content.length;
      setTurns(t);
      setGraph(g);
      setProvider(cfg.provider);
      const lastAi = [...t].reverse().find((x) => x.speaker === "ai");
      if (lastAi?.suggestions?.length) setProbes(lastAi.suggestions);
    })().catch(console.error);
  }, [id, checked]);

  // Restore the writer's last declared activity for this story (a convenience,
  // not research state — the server records what was actually sent per turn).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(`story:${id}:activity`);
      if (saved === "planning" || saved === "translating" || saved === "reviewing") {
        setDeclaredActivity(saved);
      }
    } catch { /* private mode / storage disabled */ }
  }, [id]);

  const changeActivity = (next: DeclaredActivity) => {
    setDeclaredActivity(next);
    try {
      if (next) localStorage.setItem(`story:${id}:activity`, next);
      else localStorage.removeItem(`story:${id}:activity`);
    } catch { /* ignore */ }
    api.logEvent({
      workspace_id: id, event_type: "activity_declared",
      payload: { activity: next || "cleared" },
    });
  };

  // ---- autosave + keystroke telemetry ------------------------------------
  const onDraftChange = (value: string) => {
    setDraft(value);
    keystrokes.current += 1;
    setSaving("saving");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      const delta = value.length - lastLen.current;
      lastLen.current = value.length;
      const updated = await api.updateWorkspace(id, { current_content: value });
      setWs(updated);
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

  /* Selection-scoped asking. Chakrabarty et al. (3.2) had writers demarcate a
     span with < and > delimiters so an instruction applied locally rather than
     to the whole draft; a real editor can just read the selection. */
  const captureSelection = () => {
    const el = editorRef.current;
    if (!el) return;
    const picked = draft.slice(el.selectionStart, el.selectionEnd).trim();
    setSelection(picked.length >= 8 ? picked : "");
  };

  // ---- take a turn -------------------------------------------------------
  const send = useCallback(
    async (text: string) => {
      if (!text.trim() || thinking) return;
      setMessage("");
      setProbes([]);
      setThinking(true);
      setLiveIntent("");
      setLiveCognitive("");
      setLiveIntercepted(false);
      setNodeStatus(Object.fromEntries(graph.map((n) => [n.id, "idle" as NodeStatus])));

      // Optimistic user turn so the exchange feels immediate.
      const optimistic: Turn = {
        turn_id: `tmp-${Date.now()}`, speaker: "user", message_text: text,
        intent_type: "", cognitive_activity: "", declared_activity: declaredActivity,
        intercepted: false,
        node_path: [], suggestions: [],
        provider: "", model_name: "", latency_ms: 0, timestamp: new Date().toISOString(),
      };
      setTurns((prev) => [...prev, optimistic]);

      try {
        const result = await streamTurn(
          id, {
            message: text, draft, selection, intensity, provider,
            model: modelOverride, declared_activity: declaredActivity,
          },
          (nodeId, status, extra) => {
            setNodeStatus((prev) => ({ ...prev, [nodeId]: status as NodeStatus }));
            if (typeof extra.intent === "string") setLiveIntent(extra.intent);
            if (typeof extra.cognitive === "string") setLiveCognitive(extra.cognitive);
            if (typeof extra.intercepted === "boolean") setLiveIntercepted(extra.intercepted);
          },
        );

        setTurns((prev) =>
          prev.map((t) =>
            t.turn_id === optimistic.turn_id
              ? {
                  ...t, intent_type: result.intent,
                  cognitive_activity: result.cognitive,
                  declared_activity: result.declared_activity ?? declaredActivity,
                  intercepted: result.intercepted,
                }
              : t,
          ).concat({
            turn_id: result.turn_id, speaker: "ai", message_text: result.response_text,
            intent_type: result.intent, cognitive_activity: result.cognitive,
            declared_activity: result.declared_activity ?? declaredActivity,
            intercepted: result.intercepted,
            node_path: result.node_path, suggestions: result.probes,
            provider: result.provider, model_name: result.model_name,
            latency_ms: result.latency_ms, timestamp: new Date().toISOString(),
          }),
        );
        setProbes(result.probes);
        setSelection("");
        // Never let a silent downgrade pass as a normal answer.
        setDegraded(result.provider.includes("fallback") ? result.provider : "");
        if (result.provider) setProvider(result.provider);
        setWs(await api.getWorkspace(id));
      } catch (err) {
        console.error(err);
        setTurns((prev) => prev.filter((t) => t.turn_id !== optimistic.turn_id));
      } finally {
        setThinking(false);
      }
    },
    [id, draft, graph, thinking, selection, intensity, provider, modelOverride, declaredActivity],
  );

  if (!checked || !user || !ws) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-1 w-32 overflow-hidden rounded-full bg-[var(--color-margin-deep)]">
          <div className="animate-sweep h-full w-1/3 rounded-full bg-[var(--color-accent)]" />
        </div>
      </div>
    );
  }

  const words = draft.trim() ? draft.trim().split(/\s+/).length : 0;
  const exchanges = turns.filter((t) => t.speaker === "user").length;
  const intercepts = turns.filter((t) => t.speaker === "user" && t.intercepted).length;

  return (
    <div className="flex h-screen flex-col bg-[var(--color-margin)]">
      {/* ---- top bar ------------------------------------------------------ */}
      <header className="flex h-13 shrink-0 items-center gap-3 border-b border-[var(--color-margin-edge)] bg-white px-4 py-2.5">
        <Link
          href="/student"
          className="flex h-7 w-7 items-center justify-center rounded-md text-[var(--color-ink-faint)] transition-colors hover:bg-[var(--color-margin-deep)] hover:text-[var(--color-ink)]"
          aria-label="Back to your stories"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
        </Link>

        <div className="min-w-0 flex-1">
          <input
            value={ws.title}
            onChange={(e) => setWs({ ...ws, title: e.target.value })}
            onBlur={(e) => api.updateWorkspace(id, { title: e.target.value })}
            className="w-full max-w-md truncate bg-transparent text-[13.5px] font-medium text-[var(--color-ink)] outline-none focus:underline focus:decoration-[var(--color-accent-line)] focus:underline-offset-4"
          />
        </div>

        <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
          {saving === "saving" ? "saving…" : saving === "saved" ? "saved" : ""}
        </span>

        <ScaffoldControl
          intensity={intensity}
          provider={provider}
          disabled={thinking}
          onIntensity={(v) => {
            setIntensity(v);
            api.updateWorkspace(id, { scaffold_intensity: v });
            api.logEvent({
              workspace_id: id, event_type: "intensity_change",
              payload: { intensity: v },
            });
          }}
          onProvider={(p, m) => {
            setProvider(p);
            setModelOverride(m);
            api.logEvent({
              workspace_id: id, event_type: "student_model_change",
              payload: { provider: p, model: m },
            });
          }}
        />

        <AgencyMeter ratio={ws.agency_ratio} />

        <div className="h-5 w-px bg-[var(--color-margin-edge)]" />

        <button
          onClick={() => {
            setShowExport(true);
            api.logEvent({ workspace_id: id, event_type: "export", payload: { surface: "workspace" } });
          }}
          className="rounded-md px-2.5 py-1.5 text-[12px] text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-margin-deep)]"
        >
          Export
        </button>
      </header>

      {/* ---- split screen ------------------------------------------------- */}
      <div className="flex min-h-0 flex-1">
        {/* the student's half - warm paper, wider, theirs */}
        <section className="flex min-w-0 flex-[1.35] flex-col border-r border-[var(--color-margin-edge)] bg-[var(--color-paper)]">
          <div className="flex items-center justify-between border-b border-[var(--color-paper-edge)] px-6 py-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
              story workspace
            </span>
            <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
              {selection ? "passage selected" : "your control"}
            </span>
          </div>

          {/* the writer's own goal for the piece (Flower & Hayes: goal-setting) */}
          <div className="border-b border-[var(--color-paper-edge)] px-6 py-1.5">
            <input
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
              onBlur={(e) => {
                if ((e.target.value ?? "") === (ws.goals ?? "")) return;
                api.updateWorkspace(id, { goals: e.target.value }).then(setWs);
                api.logEvent({
                  workspace_id: id, event_type: "goal_set",
                  payload: { length: e.target.value.trim().length },
                });
              }}
              placeholder="Your goal for this piece (optional) — what are you trying to do with it?"
              className="w-full max-w-[68ch] bg-transparent font-serif text-[12px] italic text-[var(--color-ink-soft)] outline-none placeholder:not-italic placeholder:text-[var(--color-ink-faint)] focus:text-[var(--color-ink)]"
            />
          </div>

          <div className="thin-scroll flex-1 overflow-y-auto">
            <textarea
              ref={editorRef}
              value={draft}
              onChange={(e) => onDraftChange(e.target.value)}
              onSelect={captureSelection}
              onMouseUp={captureSelection}
              onKeyUp={captureSelection}
              spellCheck
              placeholder="Start writing. The page is yours — the partner on the right will not fill it for you."
              className="prose-editor mx-auto block h-full w-full max-w-[68ch] resize-none bg-transparent px-6 py-8"
            />
          </div>
        </section>

        {/* the AI's half - cooler, narrower, a margin note */}
        <aside className="flex w-[400px] shrink-0 flex-col bg-[var(--color-margin)] xl:w-[440px]">
          <div className="flex items-center justify-between border-b border-[var(--color-margin-edge)] px-4 py-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
              co-creative partner
            </span>
            <span
              className="font-mono text-[10px]"
              style={{ color: degraded ? "var(--color-flag)" : "var(--color-ink-faint)" }}
              title={degraded ? "The configured model was unreachable or rate-limited." : undefined}
            >
              {provider}
            </span>
          </div>

          {options && !options.guardrail_active && (
            <div className="border-b border-[var(--color-flag-line)] bg-[var(--color-flag-soft)] px-4 py-2">
              <div className="flex items-start gap-2">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="mt-[2px] shrink-0"
                     stroke="var(--color-flag)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
                  <path d="M12 9v4M12 17h.01" />
                </svg>
                <p className="text-[11.5px] leading-snug text-[var(--color-flag)]">
                  <strong className="font-semibold">Socratic guardrail is OFF</strong>
                  {options.condition ? <> — you are in the “{options.condition.name}” condition.</> : "."}{" "}
                  This partner will write your story if you ask it to, and none
                  of it will count as yours.
                </p>
              </div>
            </div>
          )}

          {degraded && (
            <div className="animate-rise border-b border-[var(--color-flag-line)] bg-[var(--color-flag-soft)] px-4 py-1.5">
              <p className="text-[11px] leading-snug text-[var(--color-flag)]">
                The configured model is unavailable — running on the offline
                scaffold. Interaction design is unaffected; reply quality is lower.
              </p>
            </div>
          )}

          <Conversation
            turns={turns}
            probes={probes}
            thinking={thinking}
            graph={graph}
            nodeStatus={nodeStatus}
            liveIntent={liveIntent}
            liveCognitive={liveCognitive}
            liveIntercepted={liveIntercepted}
            onProbe={(q) => send(q)}
            emptyHint="Ask about craft, tension, character, or what your draft is currently doing."
          />

          {/* templated ways to ask - paper Table 2, inverted */}
          <TemplateRail
            onPick={(p) => send(p)}
            disabled={thinking}
            hasSelection={!!selection}
          />

          {/* the writer's Monitor (Flower & Hayes) - declare the current activity */}
          <ActivityControl
            value={declaredActivity}
            onChange={changeActivity}
            disabled={thinking}
          />

          {/* composer */}
          <div className="shrink-0 border-t border-[var(--color-margin-edge)] bg-white/60 p-3">
            {selection && (
              <div className="animate-rise mb-2 flex items-start gap-2 rounded-md border border-[var(--color-accent-line)] bg-[var(--color-accent-soft)] px-2.5 py-1.5">
                <span className="mt-[3px] font-mono text-[9px] uppercase tracking-wider text-[var(--color-accent)]">
                  asking about
                </span>
                <span className="min-w-0 flex-1 truncate font-serif text-[11.5px] italic text-[var(--color-accent)]">
                  “{selection}”
                </span>
                <button
                  onClick={() => setSelection("")}
                  className="font-mono text-[10px] text-[var(--color-accent)]/60 hover:text-[var(--color-accent)]"
                >
                  clear
                </button>
              </div>
            )}
            <div className="rounded-lg border border-[var(--color-margin-edge)] bg-white focus-within:border-[var(--color-accent-line)] focus-within:ring-2 focus-within:ring-[var(--color-accent-soft)]">
              <textarea
                ref={composerRef}
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
                placeholder={selection ? "Ask about the selected passage…" : "Ask for a way in…"}
                className="thin-scroll block w-full resize-none bg-transparent px-3 py-2.5 text-[13px] leading-relaxed text-[var(--color-ink)] placeholder:text-[var(--color-ink-faint)] focus:outline-none disabled:opacity-50"
              />
              <div className="flex items-center justify-between px-3 pb-2">
                <span className="font-mono text-[10px] text-[var(--color-ink-faint)]">
                  ⏎ send · ⇧⏎ newline
                </span>
                <button
                  onClick={() => send(message)}
                  disabled={thinking || !message.trim()}
                  className="rounded-md bg-[var(--color-accent)] px-3 py-1 text-[11.5px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-25"
                >
                  {thinking ? "thinking…" : "Ask"}
                </button>
              </div>
            </div>
          </div>
        </aside>
      </div>

      {/* ---- status bar --------------------------------------------------- */}
      <footer className="flex h-7 shrink-0 items-center gap-4 border-t border-[var(--color-margin-edge)] bg-white px-4 font-mono text-[10.5px] text-[var(--color-ink-faint)]">
        <span>{words} words</span>
        <span>·</span>
        <span>{exchanges} exchanges</span>
        <span>·</span>
        <span>
          {intercepts} intercepted
        </span>
        <span>·</span>
        <span title="ROUGE-L recall of AI output inside your draft (paper Fig. 7)">
          AI retention {Math.round((ws.ai_retention ?? 0) * 100)}%
        </span>
        <span className="ml-auto">select any passage to ask about it</span>
      </footer>

      {showExport && (
        <ExportDialog
          workspace={{ ...ws, current_content: draft }}
          turns={turns}
          onClose={() => setShowExport(false)}
        />
      )}
    </div>
  );
}
