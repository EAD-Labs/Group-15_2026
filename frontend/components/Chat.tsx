"use client";

import { useEffect, useRef, useState } from "react";
import type { Turn } from "@/lib/types";

/**
 * The student's conversation with the writing partner.
 *
 * Plain on purpose. The classification chips, graph trace, intercept card and
 * suggested-question chips that used to sit here are gone from the student's
 * view; all of it (probes included) is still computed and stored per turn,
 * and read on the researcher side. The student sees a conversation.
 *
 * A reply to a question about a highlighted passage is anchored to it, the
 * way a margin comment is: its quote links back to the passage in the story.
 */
export function Conversation({
  turns,
  thinking,
  status,
  freshId,
  onAnchor,
}: {
  turns: Turn[];
  thinking: boolean;
  /** Plain-language progress while a reply is being prepared. */
  status: string;
  /** The reply that just arrived - revealed word by word, once. */
  freshId: string;
  /** Highlight a passage in the story. Returns false if it no longer exists. */
  onAnchor: (passage: string) => boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const [missing, setMissing] = useState("");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length, thinking]);

  return (
    <div className="thin-scroll flex-1 space-y-5 overflow-y-auto px-5 pb-4 pt-6">
      {turns.length === 0 && !thinking && (
        <div className="mt-8 border-l-2 border-[var(--color-ink-blue)]/30 pl-4">
          <p className="font-serif text-[17px] italic leading-relaxed text-[var(--color-graphite)]">
            I’m your writing partner. Ask me when you’re stuck, unsure, or want a
            second opinion — I’ll help you think it through. The words stay yours.
          </p>
          <p className="mt-3 text-[12.5px] leading-relaxed text-[var(--color-graphite)]">
            Tip: highlight a passage in your story to ask about just that part.
          </p>
        </div>
      )}

      {turns.map((t, i) => {
        if (t.speaker === "user") {
          return (
            <div key={t.turn_id} className="flex justify-end">
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-[var(--color-ink-wash)] px-3.5 py-2 text-[14px] leading-relaxed text-[var(--color-ink-blue)]">
                {t.message_text}
              </p>
            </div>
          );
        }
        const prev = turns[i - 1];
        const asked = prev?.speaker === "user" ? prev.selection ?? "" : "";
        return (
          /* the partner's reply: a pencilled margin note, not a bubble */
          <div key={t.turn_id} className="animate-rise border-l-2 border-[var(--color-ink-blue)]/30 pl-4">
            {asked && (
              <button
                onClick={() => setMissing(onAnchor(asked) ? "" : t.turn_id)}
                title="Show this passage in your story"
                className="mb-1.5 flex max-w-full items-baseline gap-1.5 text-left text-[12.5px] text-[var(--color-ink-blue)] hover:underline"
              >
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                     strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden
                     className="shrink-0 translate-y-[1px]">
                  <path d="M9 10 4 15l5 5" /><path d="M20 4v7a4 4 0 0 1-4 4H4" />
                </svg>
                <span className="truncate font-serif italic">“{asked}”</span>
              </button>
            )}
            {missing === t.turn_id && (
              <p className="mb-1.5 text-[12px] text-[var(--color-graphite)]">
                That passage has changed since you asked, so it can’t be shown.
              </p>
            )}
            <p className="font-serif text-[16px] italic leading-[1.7] text-[var(--color-ink)]/85">
              {t.turn_id === freshId ? <Reveal text={t.message_text} /> : t.message_text}
            </p>
          </div>
        );
      })}

      {thinking && (
        <div className="flex items-center gap-2.5 border-l-2 border-[var(--color-ink-blue)]/30 py-1.5 pl-4"
             role="status">
          <span className="flex gap-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="animate-node h-1.5 w-1.5 rounded-full bg-[var(--color-graphite)]"
                style={{ animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
          <span className="font-serif text-[15px] italic text-[var(--color-graphite)]">{status}</span>
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}

/**
 * Word-by-word reveal of a reply that has already been checked in full.
 *
 * The reply is not streamed from the model: the Agency Enforcer has to see
 * the whole thing before the student does, or prose it would strip could
 * flash on screen first. Capped at ~1.6s; instant under reduced motion.
 */
function Reveal({ text }: { text: string }) {
  const words = text.split(/(\s+)/);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setShown(words.length);
      return;
    }
    const step = Math.max(8, Math.min(40, 1600 / words.length));
    const id = setInterval(() => {
      setShown((n) => {
        if (n >= words.length) { clearInterval(id); return n; }
        return n + 2; // a word and the space after it
      });
    }, step);
    return () => clearInterval(id);
  }, [words.length]);

  return (
    <>
      {words.slice(0, shown).join("")}
      <span className="sr-only">{words.slice(shown).join("")}</span>
    </>
  );
}
