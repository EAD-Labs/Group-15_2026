"use client";

import { useState } from "react";
import type { Turn, Workspace } from "@/lib/types";

/** Story + conversation export (UC-02). Everything is generated client-side. */
export function ExportDialog({
  workspace, turns, onClose,
}: { workspace: Workspace; turns: Turn[]; onClose: () => void }) {
  const [copied, setCopied] = useState("");

  const storyMd = `# ${workspace.title}\n\n${workspace.current_content}\n`;

  const conversationMd = [
    `# ${workspace.title} — Human–AI conversation`,
    ``,
    `Mode: ${workspace.mode} · Words: ${workspace.word_count} · Agency: ${Math.round(workspace.agency_ratio * 100)}%`,
    ``,
    ...turns.map((t) =>
      t.speaker === "user"
        ? `**Student** _(${t.intent_type}${t.intercepted ? ", intercepted" : ""})_\n\n${t.message_text}\n`
        : `**AI partner**\n\n${t.message_text}\n${t.suggestions?.length ? `\n${t.suggestions.map((s) => `- ${s}`).join("\n")}\n` : ""}`,
    ),
  ].join("\n");

  const download = (name: string, content: string, type = "text/markdown") => {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copy = async (label: string, text: string) => {
    await navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 1600);
  };

  const slug = workspace.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "story";

  const rows = [
    { label: "Story", desc: "Your narrative as Markdown.", file: `${slug}.md`, content: storyMd },
    { label: "Conversation", desc: "Every exchange, with intent labels.", file: `${slug}-conversation.md`, content: conversationMd },
    {
      label: "Research bundle", desc: "Structured JSON for analysis.",
      file: `${slug}-data.json`,
      content: JSON.stringify({ workspace, turns }, null, 2),
      type: "application/json",
    },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--color-ink)]/25 p-4"
      onClick={onClose}
    >
      <div
        className="animate-rise w-full max-w-md rounded-xl border border-[var(--color-margin-edge)] bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="border-b border-[var(--color-margin-edge)] px-5 py-3.5">
          <h2 className="text-[14px] font-semibold text-[var(--color-ink)]">Export</h2>
          <p className="mt-0.5 text-[11.5px] text-[var(--color-ink-faint)]">
            {workspace.word_count} words · {turns.filter((t) => t.speaker === "user").length} exchanges
          </p>
        </div>

        <div className="divide-y divide-[var(--color-margin-edge)]">
          {rows.map((r) => (
            <div key={r.label} className="flex items-center gap-3 px-5 py-3">
              <div className="min-w-0 flex-1">
                <div className="text-[12.5px] font-medium text-[var(--color-ink)]">{r.label}</div>
                <div className="text-[11px] text-[var(--color-ink-faint)]">{r.desc}</div>
              </div>
              <button
                onClick={() => copy(r.label, r.content)}
                className="rounded-md px-2 py-1 font-mono text-[10px] text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-margin-deep)]"
              >
                {copied === r.label ? "copied" : "copy"}
              </button>
              <button
                onClick={() => download(r.file, r.content, r.type)}
                className="rounded-md bg-[var(--color-accent)] px-2.5 py-1 font-mono text-[10px] text-white transition-opacity hover:opacity-90"
              >
                download
              </button>
            </div>
          ))}
        </div>

        <div className="flex items-center justify-between border-t border-[var(--color-margin-edge)] px-5 py-3">
          <a
            href="/api/research/export.json"
            className="font-mono text-[10.5px] text-[var(--color-ink-faint)] underline-offset-2 hover:text-[var(--color-accent)] hover:underline"
          >
            full study export →
          </a>
          <button
            onClick={onClose}
            className="rounded-md px-3 py-1.5 text-[12px] text-[var(--color-ink-soft)] transition-colors hover:bg-[var(--color-margin-deep)]"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
