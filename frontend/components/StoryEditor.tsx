"use client";

import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useRef, useState } from "react";

export type Range = { start: number; end: number };

export type StoryEditorHandle = {
  /** Scroll the highlighted passage into view. */
  revealAnchor: () => void;
  selectionRange: () => Range | null;
};

/**
 * The story text area, plus a transparent overlay laid exactly over it.
 *
 * A textarea cannot style parts of its own text, so the overlay repeats the
 * text invisibly with identical typography and wrapping, and paints on top:
 *
 *   - focus mode: every paragraph except the one holding the caret gets a
 *     wash of the page colour, so it fades (iA Writer's focus mode);
 *   - highlights: the passage the writer is asking about, and the passage a
 *     margin note refers to, get a tint (Google Docs' anchored comments).
 *
 * The textarea grows with its content so the page scrolls, not the field -
 * that keeps the overlay's box and the textarea's box identical.
 */
export const StoryEditor = forwardRef<StoryEditorHandle, {
  value: string;
  onChange: (value: string) => void;
  onSelectionChange: () => void;
  fontSize: number;
  focusMode: boolean;
  pending: Range | null;   // passage selected for the next question
  anchor: Range | null;    // passage a margin note refers to
}>(function StoryEditor(
  { value, onChange, onSelectionChange, fontSize, focusMode, pending, anchor },
  ref,
) {
  const areaRef = useRef<HTMLTextAreaElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const anchorRef = useRef<HTMLElement | null>(null);
  const [caret, setCaret] = useState(0);

  const fit = useCallback(() => {
    const el = areaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  useLayoutEffect(fit, [value, fontSize, fit]);

  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(fit);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [fit]);

  useImperativeHandle(ref, () => ({
    revealAnchor: () => anchorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }),
    selectionRange: () => {
      const el = areaRef.current;
      return el ? { start: el.selectionStart, end: el.selectionEnd } : null;
    },
  }), []);

  const track = () => {
    if (areaRef.current) setCaret(areaRef.current.selectionStart);
    onSelectionChange();
  };

  const typeStyle = { fontSize, lineHeight: 1.9 };
  const ranges = [
    pending && pending.end > pending.start ? { ...pending, kind: "pending" as const } : null,
    anchor && anchor.end > anchor.start ? { ...anchor, kind: "anchor" as const } : null,
  ].filter((r): r is Range & { kind: "pending" | "anchor" } => r !== null);

  const lines = value.split("\n");
  const activeLine = value.slice(0, caret).split("\n").length - 1;
  // Not gated on the field having focus: clicking the toggle itself moves focus
  // away, and the fade has to show the moment it is switched on. It stays
  // centred on the paragraph where the caret last was.
  const dim = focusMode;

  let offset = 0;
  return (
    <div ref={wrapRef} className="relative">
      <textarea
        ref={areaRef}
        value={value}
        onChange={(e) => { onChange(e.target.value); setCaret(e.target.selectionStart); }}
        onSelect={track}
        onKeyUp={track}
        onMouseUp={track}
        spellCheck
        rows={1}
        placeholder="Keep going…"
        aria-label="Your story"
        style={typeStyle}
        className="prose-editor block min-h-[55vh] w-full resize-none overflow-hidden bg-transparent"
      />

      {/* colour is set inline: .prose-editor is unlayered CSS and would
          otherwise beat Tailwind's text-transparent, painting a second, opaque
          copy of the text over the wash. */}
      <div
        aria-hidden
        style={{ ...typeStyle, color: "transparent" }}
        className="prose-editor pointer-events-none absolute inset-0 select-none whitespace-pre-wrap break-words"
      >
        {lines.map((line, i) => {
          const start = offset;
          offset += line.length + 1;
          return (
            <div
              key={i}
              style={{
                backgroundColor: dim && i !== activeLine
                  ? "color-mix(in srgb, var(--color-sheet) 68%, transparent)"
                  : "transparent",
                transition: "background-color 220ms ease",
              }}
            >
              {renderLine(line, start, ranges, anchorRef)}
            </div>
          );
        })}
      </div>
    </div>
  );
});

/** A line of text split into plain runs and highlighted runs. */
function renderLine(
  line: string,
  lineStart: number,
  ranges: (Range & { kind: "pending" | "anchor" })[],
  anchorRef: React.MutableRefObject<HTMLElement | null>,
) {
  if (!line) return "​";
  const lineEnd = lineStart + line.length;
  const cuts = new Set<number>([0, line.length]);
  for (const r of ranges) {
    if (r.end <= lineStart || r.start >= lineEnd) continue;
    cuts.add(Math.max(r.start, lineStart) - lineStart);
    cuts.add(Math.min(r.end, lineEnd) - lineStart);
  }
  const points = [...cuts].sort((a, b) => a - b);
  let anchorAttached = false;
  return points.slice(0, -1).map((from, k) => {
    const to = points[k + 1];
    const abs = lineStart + from;
    const hit = ranges.find((r) => abs >= r.start && abs < r.end);
    const text = line.slice(from, to);
    if (!hit) return <span key={k}>{text}</span>;
    const isAnchor = hit.kind === "anchor";
    const attach = isAnchor && !anchorAttached;
    if (attach) anchorAttached = true;
    return (
      <mark
        key={k}
        ref={attach ? (el) => { anchorRef.current = el; } : undefined}
        className="rounded-[2px] text-transparent"
        style={{
          backgroundColor: isAnchor
            ? "color-mix(in srgb, var(--color-ink-blue) 24%, transparent)"
            : "color-mix(in srgb, var(--color-ink-blue) 14%, transparent)",
          boxShadow: isAnchor ? "0 1.5px 0 var(--color-ink-blue)" : "none",
        }}
      >
        {text}
      </mark>
    );
  });
}
