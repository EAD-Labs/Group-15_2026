"use client";

/**
 * Human Agency Retention Rate (HLD eval 10.2), rendered as a ring.
 *
 * This is the number the whole project argues about, so it is always on
 * screen and always explains itself on hover rather than hiding in a report.
 */
export function AgencyMeter({
  ratio,
  size = 34,
  showLabel = true,
}: {
  ratio: number;
  size?: number;
  showLabel?: boolean;
}) {
  const pct = Math.round(ratio * 100);
  const stroke = 3;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const dash = circumference * ratio;

  const tone =
    pct >= 80 ? "var(--color-agency)"
    : pct >= 55 ? "var(--color-agency-warn)"
    : "var(--color-agency-low)";

  return (
    <div
      className="group relative flex items-center gap-2"
      title="Share of your draft that is not lexically traceable to anything the AI put on screen."
    >
      <svg width={size} height={size} className="-rotate-90 shrink-0">
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke="var(--color-margin-edge)" strokeWidth={stroke}
        />
        <circle
          cx={size / 2} cy={size / 2} r={r}
          fill="none" stroke={tone} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          style={{ transition: "stroke-dasharray 600ms cubic-bezier(0.22,1,0.36,1), stroke 400ms" }}
        />
      </svg>
      {showLabel && (
        <div className="leading-none">
          <div className="font-mono text-[13px] font-medium tabular-nums" style={{ color: tone }}>
            {pct}%
          </div>
          <div className="mt-0.5 text-[10px] uppercase tracking-wider text-[var(--color-ink-faint)]">
            agency
          </div>
        </div>
      )}
    </div>
  );
}
