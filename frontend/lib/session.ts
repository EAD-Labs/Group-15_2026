"use client";

import type { SessionUser } from "./types";

const KEY = "storystudio.session";

/**
 * Portal identity, held in the browser.
 *
 * Prototype-grade by design: there is no password and no token. It exists to
 * separate the two portals and to attribute work to a named participant so the
 * researcher view has a real cohort. HLD 7.2 specifies JWT/OAuth2 for the real
 * system; this is the seam that would be replaced.
 */
export function loadSession(): SessionUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as SessionUser) : null;
  } catch {
    return null;
  }
}

export function saveSession(user: SessionUser) {
  try {
    window.localStorage.setItem(KEY, JSON.stringify(user));
  } catch {
    /* private browsing - the session simply will not persist */
  }
}

export function clearSession() {
  try {
    window.localStorage.removeItem(KEY);
  } catch {
    /* nothing to do */
  }
}

export function authHeaders(): Record<string, string> {
  const s = loadSession();
  return s ? { "X-User-Id": s.user_id } : {};
}
