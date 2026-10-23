import type { TradeHubHold } from "@/lib/api";
import { BeginnerHelp } from "@/components/BeginnerHelp";

const FACTOR_LABELS: Record<string, string> = {
  context: "Context",
  ideas: "Ideas",
  competition: "Competition",
  posture: "Posture",
};

/**
 * The explicit "hold" answer (no trade) with a short multi-factor why. Every
 * line comes from the server's build_hold_verdict (real engine inputs); this
 * component only renders it. Mirrors mobile's TradeHubHoldCard.
 */
export function TradeHubHoldCard({ hold }: { hold: TradeHubHold }) {
  return (
    <section
      data-testid="trade-hub-hold"
      className="p-4 flex flex-col gap-2"
      style={{ background: "var(--color-surface-primary)", border: "var(--border-width-default) solid var(--color-border-strong)" }}
    >
      <h2 className="text-base font-bold">{hold.headline}</h2>
      <ul className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {hold.why.map((line, index) => (
          <li key={`${line.factor}-${index}`}>
            <span className="font-semibold" style={{ color: "var(--color-text-muted)" }}>
              {FACTOR_LABELS[line.factor] ?? line.factor}:
            </span>{" "}
            {line.text}
          </li>
        ))}
      </ul>
      <BeginnerHelp term="tradeHubHold" />
      {hold.ideas_optional ? (
        <p className="text-xs font-semibold" style={{ color: "var(--color-text-muted)" }}>
          Ideas below are optional.
        </p>
      ) : null}
    </section>
  );
}
