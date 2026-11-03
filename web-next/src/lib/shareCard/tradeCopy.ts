/**
 * Wording shared by the trade share card on web (tradeCard.tsx) and mobile
 * (mobile/src/lib/tradeShareCopy.ts). These are the same words the in-app
 * Trade Hub card uses (TradeIdeaCard.tsx: "You send" / "You get" /
 * "Balance"), so the shared image reads like the screen it came from.
 * tradeCopy.test.ts keeps the mobile copy byte-identical to this block.
 */
// BEGIN TRADE_SHARE_COPY
export const TRADE_SHARE_COPY = {
  send: "You send",
  get: "You get",
  pitchSend: "I send",
  pitchGet: "I get",
  balance: "Balance",
  value: "Value",
  even: "Even",
} as const;
/** Max characters of the card's "why" line (two short lines at card size). */
export const TRADE_WHY_MAX = 110;

/**
 * Plain-English "why" for the share card. The engine's rationale carries
 * internal roster-room jargon ("RB: active room covered; future asset
 * injured; Team - WR: ..."). This rewrites what can be said plainly from
 * the engine's own sentences, drops the rest, and caps by whole sentence
 * (max 2) so the text is never cut with an ellipsis. Invents nothing.
 */
export function plainTradeWhy(rationale: string | null | undefined, partnerTeam: string, max: number = TRADE_WHY_MAX): string {
  const partner = (partnerTeam || "").trim();
  const needsOf = (who: string, text: string): string[] => {
    const out: string[] = [];
    const verb = (base: string) => (who === "You" ? base : `${base}s`);
    const re = /\b(QB|RB|WR|TE)\s*:\s*([^:]*?)(?=\s*;?\s*\b(?:QB|RB|WR|TE)\s*:|$)/g;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
      const kind = m[2].toLowerCase();
      if (kind.includes("short-term starter")) out.push(`${who} ${verb("need")} ${m[1] === "RB" ? "an" : "a"} ${m[1]} starter.`);
      else if (kind.includes("short-term backup")) out.push(`${who} ${verb("need")} ${m[1]} depth.`);
      else if (kind.includes("long-term upside")) out.push(`${who} ${verb("want")} long-term ${m[1]} upside.`);
    }
    return out;
  };
  const sentences = (rationale || "")
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?])\s+(?=[A-Z])/)
    .map((part) => part.trim())
    .filter(Boolean);
  const plain: string[] = [];
  for (const sentence of sentences) {
    const body = sentence.replace(/[.!?]+$/, "");
    if (/\b(?:QB|RB|WR|TE)\s*:/.test(body)) {
      // "<my rooms>; <Partner> - <their rooms>"
      const marker = partner ? `; ${partner} - ` : "";
      const cut = marker ? body.indexOf(marker) : -1;
      plain.push(...needsOf("You", cut >= 0 ? body.slice(0, cut) : body), ...(cut >= 0 ? needsOf(partner, body.slice(cut + marker.length)) : []));
      continue;
    }
    // "You can move from TE surplus; Rival can move from RB surplus" is one
    // engine sentence about two different teams: read each clause on its own
    // (a lazy match across the ";" attributed the first team's words to the
    // second), and only when every clause is a surplus statement.
    const clauses = body.split(/\s*;\s*/).map((clause) => /^(you|[^;]+?) (?:can move|is moving) from ([A-Z /]+) surplus$/i.exec(clause));
    if (clauses.every(Boolean)) {
      for (const surplus of clauses) {
        const who = surplus![1];
        plain.push(`${who.toLowerCase() === "you" ? "You have" : `${who} has`} ${surplus![2].trim()} depth to spare.`);
      }
      continue;
    }
    if (/\bsurplus\b|\broom\b|\bcovered\b|;/.test(body)) continue;
    plain.push(/[.!?]$/.test(sentence) ? sentence : `${sentence}.`);
  }
  const seen = new Set<string>();
  let out = "";
  let count = 0;
  for (const sentence of plain) {
    const key = sentence.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    const next = out ? `${out} ${sentence}` : sentence;
    if (next.length > max) continue;
    out = next;
    if (++count === 2) break;
  }
  return out;
}
// END TRADE_SHARE_COPY
