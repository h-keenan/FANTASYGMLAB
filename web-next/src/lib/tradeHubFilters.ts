import type { TradeIdea } from "@/lib/api";
import { categoryColor, impactTagConfig } from "@/lib/tradeHubPresentation";

/** Positions involved in an idea (both sides, players only), deduped. */
export function ideaPositions(idea: TradeIdea): string[] {
  const seen = new Set<string>();
  for (const asset of [...idea.package.send, ...idea.package.receive]) {
    if (asset.asset_type === "player" && asset.position) seen.add(asset.position);
  }
  return [...seen];
}

const POSITION_ORDER = ["QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB"];

/** Every position present on a board, in a stable fantasy-friendly order. */
export function boardPositions(ideas: TradeIdea[]): string[] {
  const all = new Set<string>();
  for (const idea of ideas) for (const pos of ideaPositions(idea)) all.add(pos);
  const rank = (pos: string) => {
    const index = POSITION_ORDER.indexOf(pos);
    return index === -1 ? 99 : index;
  };
  return [...all].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));
}

export interface TradeIdeaFilter {
  /** An engine impact_tag (buy_low / sell_high / high_impact), or null for all. */
  impact: string | null;
  /** One position code, or null for all. */
  position: string | null;
}

export function filterTradeIdeas(ideas: TradeIdea[], filter: TradeIdeaFilter): TradeIdea[] {
  return ideas.filter(
    (idea) =>
      (!filter.impact || idea.impact_tag === filter.impact) &&
      (!filter.position || ideaPositions(idea).includes(filter.position)),
  );
}

/** Count of ideas per engine impact tag actually present on the board. */
export function impactTagCounts(ideas: TradeIdea[]): { tag: string; label: string; count: number }[] {
  const out: { tag: string; label: string; count: number }[] = [];
  for (const tag of ["buy_low", "sell_high", "high_impact"]) {
    const config = impactTagConfig(tag);
    const count = ideas.filter((idea) => idea.impact_tag === tag).length;
    if (config && count > 0) out.push({ tag, label: config.label, count });
  }
  return out;
}

export interface IdeaTag {
  label: string;
  color: string;
  kind: "category" | "impact";
}

/** The tags shown on an idea card. Only signals the engine already computes:
 * the server category (Headline Recommendation, Age Optimization, Health
 * Relief, ...) and the impact tag (Buy Low / Sell High / High Impact). */
export function ideaTags(idea: TradeIdea): IdeaTag[] {
  const tags: IdeaTag[] = [];
  if (idea.category) tags.push({ label: idea.category, color: categoryColor(idea.category), kind: "category" });
  const impact = impactTagConfig(idea.impact_tag);
  if (impact) tags.push({ label: impact.label, color: impact.color, kind: "impact" });
  return tags;
}

/** One short reason line: the rationale's first sentence. */
export function shortReason(rationale: string | null | undefined): string {
  const text = (rationale || "").trim();
  if (!text) return "";
  const match = text.match(/^.*?[.!?](?=\s|$)/);
  return (match ? match[0] : text).trim();
}
