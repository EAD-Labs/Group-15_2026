"use client";

import { useEffect, useState } from "react";
import { api, report } from "@/lib/api";
import type { DraftVersion, Workspace } from "@/lib/types";

const REASON: Record<DraftVersion["reason"], string> = {
  autosave: "Saved while writing",
  before_ask: "When you asked your partner",
  before_restore: "Before you restored a version",
};

function when(iso: string) {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  return d.toLocaleString(undefined, {
    day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
  });
}

/**
 * The story's earlier versions, newest first, with a way back to any of them.
 *
 * Restoring saves the current text first (server side), so a restore shows up
 * in this same list and can itself be undone - there is no dead end.
 */
export function VersionHistory({ workspaceId, current, onRestored, onClose }: {
  workspaceId: string;
  current: string;
  onRestored: (w: Workspace) => void;
  onClose: () => void;
}) {
  const [versions, setVersions] = useState<DraftVersion[] | null>(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api.versions(workspaceId)
      .then(setVersions)
      .catch((err) => { report(err); setError("Earlier versions could not be loaded."); });
  }, [workspaceId]);

  const restore = async (v: DraftVersion) => {
    setBusy(v.snapshot_id);
    setError("");
    try {
      onRestored(await api.restoreVersion(workspaceId, v.snapshot_id));
    } catch (err) {
      report(err);
      setError("That version could not be restored. Your current text is unchanged.");
      setBusy("");
    }
  };

  // The newest snapshot often equals what is on the page; restoring it does nothing.
  const listed = (versions ?? []).filter((v) => v.content !== current);

  return (
    <div className="mx-auto mt-2 w-full max-w-[46rem] px-3 md:px-0">
      <div className="sheet px-6 py-5">
        <div className="flex items-baseline justify-between">
          <h2 className="font-serif text-[18px] text-[var(--color-ink)]">Earlier versions</h2>
          <button onClick={onClose}
                  className="text-[12.5px] text-[var(--color-graphite)] hover:text-[var(--color-ink)]">
            Close
          </button>
        </div>
        <p className="mt-1 text-[12.5px] text-[var(--color-graphite)]">
          Restoring a version keeps a copy of your current text here, so you can always come back.
        </p>

        {error && <p role="alert" className="mt-3 text-[12.5px] text-[var(--color-flag)]">{error}</p>}

        {versions === null && !error ? (
          <p className="mt-4 text-[13px] text-[var(--color-graphite)]">Loading…</p>
        ) : listed.length === 0 && !error ? (
          <p className="mt-4 text-[13px] text-[var(--color-graphite)]">
            No earlier versions yet. They are kept as you write.
          </p>
        ) : (
          <ol className="thin-scroll mt-3 max-h-[40vh] overflow-y-auto">
            {listed.map((v) => (
              <li key={v.snapshot_id} className="border-t border-[var(--color-desk)] py-2.5 first:border-t-0">
                <div className="flex items-baseline gap-3">
                  <button
                    onClick={() => setOpen(open === v.snapshot_id ? "" : v.snapshot_id)}
                    aria-expanded={open === v.snapshot_id}
                    className="min-w-0 flex-1 text-left"
                  >
                    <span className="text-[13.5px] text-[var(--color-ink)]">{when(v.created_at)}</span>
                    <span className="ml-2 text-[12px] text-[var(--color-graphite)]">
                      {REASON[v.reason] ?? v.reason} · {v.words} words
                    </span>
                  </button>
                  <button
                    onClick={() => restore(v)}
                    disabled={!!busy}
                    className="shrink-0 rounded-md px-2 py-1 text-[12.5px] text-[var(--color-ink-blue)] hover:bg-[var(--color-ink-wash)] disabled:opacity-40"
                  >
                    {busy === v.snapshot_id ? "Restoring…" : "Restore"}
                  </button>
                </div>
                {open === v.snapshot_id && (
                  <p className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap rounded-sm bg-[var(--color-desk)]/50 px-3 py-2 font-serif text-[14px] leading-relaxed text-[var(--color-ink)]">
                    {v.content || "(empty)"}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}
