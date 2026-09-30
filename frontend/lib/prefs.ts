"use client";

import { useCallback, useEffect, useState } from "react";

/**
 * The student's reading/writing comforts: night mode, text size, focus mode.
 *
 * Per-browser conveniences, not research state, so they live in localStorage.
 * Changes are still logged as telemetry by the pages that expose them.
 */
export type StudentPrefs = {
  theme: "day" | "night";
  textSize: number; // index into TEXT_SIZES
  focus: boolean;
};

export const TEXT_SIZES = [16, 18, 20, 22] as const;

const KEY = "storystudio.prefs";
const DEFAULTS: StudentPrefs = { theme: "day", textSize: 1, focus: false };

function read(): StudentPrefs {
  try {
    const raw = window.localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...JSON.parse(raw) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export function useStudentPrefs() {
  const [prefs, setPrefs] = useState<StudentPrefs>(DEFAULTS);

  useEffect(() => setPrefs(read()), []);

  const update = useCallback(<K extends keyof StudentPrefs>(key: K, value: StudentPrefs[K]) => {
    setPrefs((prev) => {
      const next = { ...prev, [key]: value };
      try {
        window.localStorage.setItem(KEY, JSON.stringify(next));
      } catch {
        /* private browsing - the preference just won't persist */
      }
      return next;
    });
  }, []);

  return { prefs, update };
}
