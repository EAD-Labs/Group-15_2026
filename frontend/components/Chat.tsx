"use client";

import { useEffect, useRef } from "react";
import type { GraphNode, Intent, Turn } from "@/lib/types";
import { NodePipeline, type NodeStatus } from "./NodePipeline";

const INTENT_COPY: Record<string, { label: string; blurb: string }> = {
  executive: { label: "executive help", blurb: "asking the AI to do the work" },
  instrumental: { label: "instrumental help", blurb: "asking for help doing it yourself" },
  brainstorm: { label: "brainstorming", blurb: "widening the option space" },
  reflection: { label: "reflection", blurb: "thinking it through aloud" },
};

const COGNITIVE_COPY: Record<string, { label: string; blurb: string; tone: string }> = {
  planning: { label: "planning", blurb: "goals, ideas, what should happen", tone: "var(--color-cog-plan)" },
  translation: { label: "translating", blurb: "getting thoughts into sentences", tone: "var(--color-cog-trans)" },
  reviewing: { label: "reviewing", blurb: "judging or revising what exists", tone: "var(--color-cog-review)" },
};

// "translation" (detected) and "translating" (declared) are the same activity.
const sameActivity = (a: string, b: string) =>
  (a === "translation" ? "translating" : a) === (b === "translation" ? "translating" : b);

/** The writer's own declaration (Monitor), shown only when they made one. */
function DeclaredChip({ declared, detected }: { declared: string; detected: string }) {
  if (!declared) return null;
  const agrees = sameActivity(declared, detected);
  return (
    <span
      title={
        agrees
          ? "You said what you were doing, and the classifier agrees"
          : `You said ${declared}; the classifier read this as ${detected === "translation" ? "translating" : detected}`
      }
      className="inline-flex items-center gap-1 rounded-full border border-dashed border-[var(--color-margin-edge)] px-2 py-[3px] font-mono text-[10px] tracking-tight text-[var(--color-ink-faint)]"
    >
      you: {declared}{!agrees && detected ? " ≠" : ""}
    </span>
  );
}

/** Flower & Hayes cognitive activity for this turn (paper Section 2.4). */
export function CognitiveChip({ activity }: { activity: string }) {
  const meta = COGNITIVE_COPY[activity];
  if (!meta) return null;
  return (
    <span
      title={`Cognitive activity: ${meta.blurb}`}
      className="inline-flex items-center gap-1 rounded-full bg-[var(--color-margin-deep)] px-2 py-[3px] font-mono text-[10px] tracking-tight text-[var(--color-ink-soft)]"
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: meta.tone }} />
      {meta.label}
    </span>
  );
}

export function IntentChip({ intent }: { intent: Intent }) {
  if (!intent) return null;
  const meta = INTENT_COPY[intent];
  if (!meta) return null;
  const isExec = intent === "executive";
  return (
    <span
      title={meta.blurb}
      className={[
        "inline-flex items-center gap-1 rounded-full px-2 py-[3px] font-mono text-[10px] tracking-tight",
        isExec
          ? "bg-[var(--color-flag-soft)] text-[var(--color-flag)] ring-1 ring-[var(--color-flag-line)]"
          : "bg-[var(--color-margin-deep)] text-[var(--color-ink-soft)]",
      ].join(" ")}
    >
      {meta.label}
    </span>
  );
}

/**
 * The intercept notice.
 *
 * When the Helsinki filter fires, the student is told plainly what happened and
 * why. Silently swapping their request for a question would be the same
 * paternalism the project is arguing against - the redirect has to be legible.
 */
function InterceptCard() {
  return (
    <div className="animate-rise rounded-lg border border-[var(--color-flag-line)] bg-[var(--color-flag-soft)] p-3">
      <div className="flex items-center gap-2">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" className="shrink-0"
             stroke="var(--color-flag)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M3 12a9 9 0 1 0 3-6.7" /><path d="M3 4v5h5" />
        </svg>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-flag)]">
          redirected
        </span>
      </div>
      <p className="mt-1.5 text-[12.5px] leading-relaxed text-[var(--color-flag)]">
        You asked for text to be written for you. That is the part worth
        struggling over, so it stays yours — here is a way in instead.
      </p>
    </div>
  );
}

function AiTurn({ turn }: { turn: Turn }) {
  return (
    <div className="animate-rise space-y-2">
      <div className="rounded-lg border border-[var(--color-accent-line)]/50 bg-white p-3.5 shadow-[0_1px_2px_rgba(28,25,23,0.04)]">
        <p className="text-[13.5px] leading-[1.65] text-[var(--color-ink)]">
          {turn.message_text}
        </p>
      </div>

      {turn.node_path?.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer list-none font-mono text-[10px] text-[var(--color-ink-faint)] transition-colors hover:text-[var(--color-ink-soft)]">
            <span className="group-open:hidden">▸ trace</span>
            <span className="hidden group-open:inline">▾ trace</span>
            {" · "}{turn.provider || "—"}
            {turn.latency_ms ? ` · ${turn.latency_ms}ms` : ""}
          </summary>
          <div className="mt-1.5 rounded border border-[var(--color-margin-edge)] bg-[var(--color-margin-deep)]/60 p-2">
            <div className="font-mono text-[10px] leading-relaxed text-[var(--color-ink-soft)]">
              {turn.node_path.join(" → ")}
            </div>
            <div className="mt-1 font-mono text-[10px] text-[var(--color-ink-faint)]">
              model: {turn.model_name || "—"}
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

export function Conversation({
  turns,
  probes,
  thinking,
  graph,
  nodeStatus,
  liveIntent,
  liveCognitive,
  liveIntercepted,
  onProbe,
  emptyHint,
}: {
  turns: Turn[];
  probes: string[];
  thinking: boolean;
  graph: GraphNode[];
  nodeStatus: Record<string, NodeStatus>;
  liveIntent: string;
  liveCognitive: string;
  liveIntercepted: boolean;
  onProbe: (q: string) => void;
  emptyHint: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, thinking, probes.length]);

  return (
    <div className="thin-scroll flex-1 space-y-4 overflow-y-auto px-4 py-4">
      {turns.length === 0 && !thinking && (
        <div className="mx-auto mt-8 max-w-[280px] text-center">
          <div className="mx-auto mb-3 flex h-9 w-9 items-center justify-center rounded-full bg-[var(--color-accent-soft)]">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--color-accent)"
                 strokeWidth="2" strokeLinecap="round">
              <path d="M9.1 9a3 3 0 1 1 4 2.8c-.8.3-1.1 1-1.1 1.7v.5" />
              <circle cx="12" cy="17.5" r="0.6" fill="var(--color-accent)" />
            </svg>
          </div>
          <p className="text-[13px] leading-relaxed text-[var(--color-ink-soft)]">{emptyHint}</p>
          <p className="mt-2 text-[11.5px] leading-relaxed text-[var(--color-ink-faint)]">
            This partner will not write your story. Ask it how, not what.
          </p>
        </div>
      )}

      {turns.map((t) =>
        t.speaker === "user" ? (
          <div key={t.turn_id} className="space-y-2">
            <div className="flex justify-end">
              <div className="max-w-[85%] space-y-1">
                <div className="rounded-lg bg-[var(--color-accent)] px-3 py-2">
                  <p className="text-[13px] leading-relaxed text-white">{t.message_text}</p>
                </div>
                <div className="flex flex-wrap justify-end gap-1">
                  <DeclaredChip
                    declared={t.declared_activity ?? ""}
                    detected={t.cognitive_activity}
                  />
                  <CognitiveChip activity={t.cognitive_activity} />
                  <IntentChip intent={t.intent_type} />
                </div>
              </div>
            </div>
            {/* The notice follows the request it responds to - cause, then effect. */}
            {t.intercepted && <InterceptCard />}
          </div>
        ) : (
          <AiTurn key={t.turn_id} turn={t} />
        ),
      )}

      {thinking && (
        <div className="animate-rise rounded-lg border border-[var(--color-margin-edge)] bg-white/70 p-3">
          <NodePipeline
            nodes={graph}
            status={nodeStatus}
            intent={liveIntent}
            cognitive={liveCognitive}
            intercepted={liveIntercepted}
          />
        </div>
      )}

      {!thinking && probes.length > 0 && (
        <div className="animate-rise space-y-1.5">
          <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-ink-faint)]">
            questions to sit with
          </div>
          {probes.map((p, i) => (
            <button
              key={i}
              onClick={() => onProbe(p)}
              className="group block w-full rounded-lg border border-[var(--color-margin-edge)] bg-white/60 px-3 py-2 text-left transition-all hover:border-[var(--color-accent-line)] hover:bg-[var(--color-accent-soft)]"
            >
              <span className="text-[12.5px] leading-snug text-[var(--color-ink-soft)] transition-colors group-hover:text-[var(--color-accent)]">
                {p}
              </span>
            </button>
          ))}
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
