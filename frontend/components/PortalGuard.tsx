"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { loadSession } from "@/lib/session";
import type { SessionUser } from "@/lib/types";

/**
 * Keeps each portal to its own audience.
 *
 * This is navigation, not security - the API does not enforce it, and the
 * README says so plainly. It exists so the two portals stay conceptually
 * separate for the people using them.
 */
export function usePortal(required: "student" | "researcher") {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const s = loadSession();
    if (!s) {
      router.replace("/");
      return;
    }
    if (s.role !== required) {
      router.replace(s.role === "researcher" ? "/researcher" : "/student");
      return;
    }
    setUser(s);
    setChecked(true);
  }, [required, router]);

  return { user, checked };
}

export function PortalLoading() {
  return (
    <div className="flex h-screen items-center justify-center bg-[var(--color-margin)]">
      <div className="h-1 w-32 overflow-hidden rounded-full bg-[var(--color-margin-deep)]">
        <div className="animate-sweep h-full w-1/3 rounded-full bg-[var(--color-accent)]" />
      </div>
    </div>
  );
}
