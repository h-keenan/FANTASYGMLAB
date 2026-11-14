import type { CSSProperties } from "react";
import { splitMoney } from "@/lib/money";

/** The one money color (--color-money). Never use it for fantasy points or other numbers. */
export const MONEY_COLOR = "var(--color-money)";

/**
 * The ONE place dollar amounts get their color. Pass text; every "$81" /
 * "$12–$18" inside it renders in the semantic money green and everything
 * else keeps the surrounding color, so a sentence like "of $81 remaining"
 * only greens the amount. `all` paints the whole text (a bid line that is a
 * percent-of-pool range because the dollar budget is unknown is still a bid).
 * Amounts are built with `formatMoney` from lib/money.ts, never by hand.
 * App twin: mobile/src/components/Money.tsx. Banned elsewhere by
 * src/components/moneyShared.test.ts.
 */
export function Money({
  children,
  all = false,
  className,
  style,
  testId,
}: {
  children: string;
  all?: boolean;
  className?: string;
  style?: CSSProperties;
  testId?: string;
}) {
  const text = String(children ?? "");
  const wrapperStyle = all ? { ...style, color: MONEY_COLOR } : style;
  if (all) {
    return (
      <span className={className} style={wrapperStyle} data-money="true" data-testid={testId}>
        {text}
      </span>
    );
  }
  const segments = splitMoney(text);
  if (!segments.some((s) => s.money) && !className && !style && !testId) return <>{text}</>;
  return (
    <span className={className} style={style} data-testid={testId}>
      {segments.map((s, i) =>
        s.money ? (
          <span key={i} style={{ color: MONEY_COLOR }} data-money="true">
            {s.text}
          </span>
        ) : (
          s.text
        ),
      )}
    </span>
  );
}
