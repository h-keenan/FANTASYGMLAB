/**
 * Small "Values informed by FantasyCalc" credit for surfaces that show player
 * values. Our dynasty values blend in FantasyCalc's market values
 * (modules/fantasycalc.py, GET /values/current), and FantasyCalc's Terms of
 * Usage (https://fantasycalc.com/terms-of-usage, effective 2026-10-10) require
 * a visible "FantasyCalc" credit that links to fantasycalc.com on every page
 * showing their data or derivatives, near the displayed data.
 *
 * Plain markup with no client hooks, so it also renders in server-rendered HTML
 * (the public /methodology page uses it as the required no-JS attribution
 * link). Keep the wording neutral: the terms also forbid implying a
 * partnership or endorsement.
 */
export const FANTASYCALC_URL = "https://fantasycalc.com";

export function ValuesCredit({ className = "" }: { className?: string }) {
  return (
    <p
      className={`text-xs ${className}`.trim()}
      style={{ color: "var(--color-text-muted)" }}
      data-testid="values-credit"
    >
      Values informed by{" "}
      <a
        href={FANTASYCALC_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="underline"
        style={{ color: "var(--color-text-secondary)" }}
      >
        FantasyCalc
      </a>
    </p>
  );
}
