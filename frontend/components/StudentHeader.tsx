"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearSession } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

/** The student's top bar: the product, who is signed in, and a way out. */
export function StudentHeader({ user }: { user: SessionUser }) {
  const router = useRouter();
  return (
    <header className="mx-auto flex w-full max-w-3xl items-center gap-3 px-5 py-5">
      <Link href="/student" className="flex items-center gap-2 text-[var(--color-ink)]">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden
             stroke="var(--color-ink-blue)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          {/* a pen nib */}
          <path d="M12 3 5 13l7 8 7-8-7-10z" />
          <path d="M12 3v10" />
          <circle cx="12" cy="13" r="1.3" fill="var(--color-ink-blue)" stroke="none" />
        </svg>
        <span className="font-serif text-[17px] font-medium tracking-tight">Story Studio</span>
      </Link>
      <span className="ml-auto text-[13px] text-[var(--color-graphite)]">{user.display_name}</span>
      <button
        onClick={() => { clearSession(); router.push("/"); }}
        className="rounded-md px-2 py-1 text-[13px] text-[var(--color-graphite)] transition-colors hover:bg-[var(--color-desk-edge)]/60 hover:text-[var(--color-ink)]"
      >
        Sign out
      </button>
    </header>
  );
}
