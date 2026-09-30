"use client";

import { useEffect, useRef } from "react";
import type { Turn } from "@/lib/types";

/**
 * The student's conversation with the writing partner.
 *
 * Plain on purpose. The classification chips, graph trace, intercept card and
 * suggested-question chips that used to sit here are gone from the student's
 * view; all of it (probes included) is still computed and stored per turn,
 * and read on the researcher side. The student sees a conversation.
 */
export function Conversation({
  turns,
  thinking,
}: {
  turns: Turn[];
  thinking: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);

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
        </div>
      )}

      {turns.map((t) =>
        t.speaker === "user" ? (
          <div key={t.turn_id} className="flex justify-end">
            <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-[var(--color-ink-wash)] px-3.5 py-2 text-[14px] leading-relaxed text-[var(--color-ink-blue)]">
              {t.message_text}
            </p>
          </div>
        ) : (
          /* the partner's reply: a pencilled margin note, not a bubble */
          <div key={t.turn_id} className="animate-rise border-l-2 border-[var(--color-ink-blue)]/30 pl-4">
            <p className="font-serif text-[16px] italic leading-[1.7] text-[var(--color-ink)]/85">
              {t.message_text}
            </p>
          </div>
        ),
      )}

      {thinking && (
        <div className="flex gap-1.5 border-l-2 border-[var(--color-ink-blue)]/30 py-2 pl-4" aria-label="Your partner is thinking">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="animate-node h-1.5 w-1.5 rounded-full bg-[var(--color-graphite)]"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
      )}

      <div ref={endRef} />
    </div>
  );
}
