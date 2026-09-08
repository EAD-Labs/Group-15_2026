"use client";

import type { GraphNode } from "@/lib/types";

export type NodeStatus = "idle" | "running" | "done";

/**
 * The agentic graph, executing live.
 *
 * Streaming each node as it runs is what turns the architecture from a claim
 * in a document into something a viewer can watch happen. The Guardrail node
 * announces its verdict inline, which is the moment the demo exists for.
 */
export function NodePipeline({
  nodes,
  status,
  intent,
  cognitive,
  intercepted,
  compact = false,
}: {
  nodes: GraphNode[];
  status: Record<string, NodeStatus>;
  intent?: string;
  cognitive?: string;
  intercepted?: boolean;
  compact?: boolean;
}) {
  if (!nodes.length) return null;

  return (
    <div className={compact ? "flex flex-wrap items-center gap-1" : "space-y-1.5"}>
      {nodes.map((n, i) => {
        const s = status[n.id] ?? "idle";
        const isGuard = n.id === "role_arbiter";
        const flagged = isGuard && intercepted && s === "done";

        return (
          <div key={n.id} className={compact ? "flex items-center gap-1" : "flex items-start gap-2.5"}>
            {!compact && (
              <div className="relative flex flex-col items-center pt-[3px]">
                <span
                  className={[
                    "block h-2 w-2 rounded-full transition-colors duration-300",
                    s === "idle" ? "bg-[var(--color-margin-edge)]" : "",
                    s === "running" ? "animate-node bg-[var(--color-accent)]" : "",
                    s === "done" && !flagged ? "bg-[var(--color-agency)]" : "",
                    flagged ? "bg-[var(--color-flag)]" : "",
                  ].join(" ")}
                />
                {i < nodes.length - 1 && (
                  <span
                    className="mt-1 w-px flex-1 transition-colors duration-300"
                    style={{
                      height: 14,
                      background: s === "done" ? "var(--color-accent-line)" : "var(--color-margin-edge)",
                    }}
                  />
                )}
              </div>
            )}

            <div className={compact ? "" : "min-w-0 flex-1 pb-0.5"}>
              <div
                className={[
                  compact
                    ? "rounded px-1.5 py-0.5 font-mono text-[10px] transition-colors"
                    : "font-mono text-[11px] transition-colors",
                  s === "idle" ? "text-[var(--color-ink-faint)]" : "",
                  s === "running" ? "text-[var(--color-accent)]" : "",
                  s === "done" ? "text-[var(--color-ink-soft)]" : "",
                  compact && s === "done" ? "bg-[var(--color-margin-deep)]" : "",
                ].join(" ")}
              >
                {compact ? n.id.replace(/_/g, " ") : n.label}
              </div>

              {!compact && (
                <div className="mt-0.5 text-[11px] leading-snug text-[var(--color-ink-faint)]">
                  {n.id === "intent_classifier" && intent && status[n.id] === "done" ? (
                    <>
                      <span className="font-medium text-[var(--color-ink-soft)]">{intent}</span> help-seeking
                      {cognitive ? (
                        <> · <span className="font-medium text-[var(--color-ink-soft)]">{cognitive}</span></>
                      ) : null}
                    </>
                  ) : flagged ? (
                    <span className="font-medium text-[var(--color-flag)]">
                      executive request intercepted
                    </span>
                  ) : isGuard && s === "done" ? (
                    "request passed through"
                  ) : (
                    n.desc
                  )}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
