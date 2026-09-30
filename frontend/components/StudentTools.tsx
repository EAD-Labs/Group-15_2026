"use client";

/** Small icon buttons for the student's comfort controls. */
export function ToolButton({ label, pressed, disabled, onClick, children }: {
  label: string;
  pressed?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      aria-pressed={pressed}
      className={[
        "flex h-8 min-w-8 items-center justify-center rounded-md px-1.5 transition-colors disabled:opacity-30",
        pressed
          ? "bg-[var(--color-ink-wash)] text-[var(--color-ink-blue)]"
          : "text-[var(--color-graphite)] hover:bg-[var(--color-desk-edge)]/60 hover:text-[var(--color-ink)]",
      ].join(" ")}
    >
      {children}
    </button>
  );
}

export function ThemeButton({ theme, onToggle }: { theme: "day" | "night"; onToggle: () => void }) {
  return (
    <ToolButton label={theme === "night" ? "Switch to day mode" : "Switch to night mode"} onClick={onToggle}>
      {theme === "night" ? (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.9" strokeLinecap="round" aria-hidden>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
        </svg>
      ) : (
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z" />
        </svg>
      )}
    </ToolButton>
  );
}
