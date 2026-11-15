/**
 * Money formatting + detection, the single source for how a dollar amount is
 * built and found. Pairs with the <Money> component (web + mobile), which
 * paints every amount in the semantic `money` color (--color-money /
 * theme.colors.money). Fantasy points and other non-money numbers never go
 * through this module, so they never turn green. Pure and import-free:
 * byte-identical twin of mobile/src/lib/money.ts.
 */

/** Whole dollars stay whole ("$81"); fractional amounts get cents ("$3.99"). */
export function formatMoney(amount: number): string {
  if (!Number.isFinite(amount)) return "";
  const whole = Number.isInteger(amount);
  const body = whole ? String(Math.abs(amount)) : Math.abs(amount).toFixed(2);
  return `${amount < 0 ? "-" : ""}$${body}`;
}

/** "$12–$18" (en dash), collapsing to one amount when low equals high. */
export function formatMoneyRange(low: number, high: number): string {
  return low === high ? formatMoney(low) : `${formatMoney(low)}–${formatMoney(high)}`;
}

export type MoneySegment = { text: string; money: boolean };

// "$81", "$1,200.50", and a whole range "$12-$18" / "$12–18" as one amount.
const AMOUNT = "\\$\\d[\\d,]*(?:\\.\\d+)?";
const MONEY_RE = new RegExp(`${AMOUNT}(?:\\s?[\\u2013-]\\s?\\$?\\d[\\d,]*(?:\\.\\d+)?)?`, "g");

/** Split free text into plain and dollar-amount runs ("of $81 remaining"). */
export function splitMoney(text: string): MoneySegment[] {
  const out: MoneySegment[] = [];
  let last = 0;
  for (const match of text.matchAll(MONEY_RE)) {
    const at = match.index ?? 0;
    if (at > last) out.push({ text: text.slice(last, at), money: false });
    out.push({ text: match[0], money: true });
    last = at + match[0].length;
  }
  if (last < text.length) out.push({ text: text.slice(last), money: false });
  return out;
}

export function hasMoney(text: string): boolean {
  return splitMoney(text).some((s) => s.money);
}
