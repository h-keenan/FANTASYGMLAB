import type { ReactNode } from "react";

import type { TradeHubHold } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { BeginnerHelp } from "@/components/BeginnerHelp";
import { ToneBadge } from "@/components/ToneBadge";

const FACTOR_LABELS: Record<string, string> = {
  context: "Context",
  ideas: "Ideas",
  competition: "Competition",
  posture: "Posture",
};

/** One semantic color + glyph per factor so each reason scans on its own. */
const FACTOR_STYLE: Record<string, { color: string; icon: ReactNode }> = {
  context: {
    color: "var(--color-information)",
    icon: <path d="M3 12h4l3-8 4 16 3-8h4" />,
  },
  ideas: {
    color: "var(--color-accent)",
    icon: (
      <>
        <path d="M9 18h6M10 21h4" />
        <path d="M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z" />
      </>
    ),
  },
  competition: {
    color: "var(--color-warning)",
    icon: (
      <>
        <circle cx="9" cy="8" r="3" />
        <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
        <path d="M16 11a3 3 0 1 0 0-6M18 14c1.7.7 3 2.5 3 5" />
      </>
    ),
  },
  posture: {
    color: "var(--color-premium)",
    icon: <path d="M12 3l8 3v6c0 4.5-3.4 8-8 9-4.6-1-8-4.5-8-9V6l8-3z" />,
  },
};
const FALLBACK_STYLE = { color: "var(--color-text-muted)", icon: <circle cx="12" cy="12" r="8" /> };

function FactorGlyph({ color, children }: { color: string; children: ReactNode }) {
  return (
    <span
      className="inline-flex items-center justify-center shrink-0"
      style={{
        width: 32,
        height: 32,
        borderRadius: "var(--radius-pill)",
        background: `color-mix(in srgb, ${color} 15%, transparent)`,
        color,
      }}
      aria-hidden="true"
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </span>
  );
}

/**
 * The explicit "hold" answer (no trade) with a short multi-factor why. Every
 * line comes from the server's build_hold_verdict (real engine inputs); this
 * component only renders it. Mirrors mobile's TradeHubHoldCard.
 */
export function TradeHubHoldCard({ hold }: { hold: TradeHubHold }) {
  return (
    <AccentCard as="section" accent="var(--color-information)" data-testid="trade-hub-hold">
      <div className="flex items-center gap-3">
        <FactorGlyph color="var(--color-information)">
          <rect x="6" y="5" width="4" height="14" rx="1" />
          <rect x="14" y="5" width="4" height="14" rx="1" />
        </FactorGlyph>
        <div className="flex flex-col gap-1 items-start min-w-0">
          <ToneBadge label="Hold" color="var(--color-information)" />
          <h2 className="text-base font-bold">{hold.headline}</h2>
        </div>
      </div>
      <ul className="flex flex-col gap-3">
        {hold.why.map((line, index) => {
          const style = FACTOR_STYLE[line.factor] ?? FALLBACK_STYLE;
          return (
            <li key={`${line.factor}-${index}`} className="flex items-start gap-3">
              <FactorGlyph color={style.color}>{style.icon}</FactorGlyph>
              <div className="flex flex-col gap-1 items-start min-w-0">
                <ToneBadge label={FACTOR_LABELS[line.factor] ?? line.factor} color={style.color} />
                <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {line.text}
                </span>
              </div>
            </li>
          );
        })}
      </ul>
      <BeginnerHelp term="tradeHubHold" />
      {hold.ideas_optional ? (
        <p className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          Ideas below are optional.
        </p>
      ) : null}
    </AccentCard>
  );
}
