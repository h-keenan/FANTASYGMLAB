import { leanBar } from "@/lib/tradeHubPresentation";

/**
 * Center-anchored "who has the edge" value lean bar — extracted (Revision
 * 15 CSS-cleanup pass) from TradeHubContent.tsx's own local `LeanBarMeter`
 * so Trade Analyzer's verdict card (same shape-reinforcement of its own
 * value-change number, modules/trade_visual_language.py's
 * value_edge_lean_bar_html) doesn't redefine the identical markup+math a
 * second time. Uses the existing `.lean-bar-*` CSS this app already ships
 * (globals.css) — no new tokens.
 */
export function LeanBarMeter({ sendScore, receiveScore }: { sendScore: number; receiveScore: number }) {
  const { polarity, halfTrackPercent } = leanBar(sendScore, receiveScore);
  const conclusion =
    polarity === "pos"
      ? "You have the edge in this trade"
      : polarity === "neg"
        ? "Your opponent has the edge in this trade"
        : "Neither side has a clear value edge";
  const label = `Value lean: you send ${Math.round(sendScore).toLocaleString()}, you receive ${Math.round(
    receiveScore,
  ).toLocaleString()}. ${conclusion}.`;
  return (
    <div className="lean-bar-track" role="img" aria-label={label}>
      <span className="lean-bar-tick" aria-hidden="true" />
      {halfTrackPercent > 0 ? (
        <span
          className={`lean-bar-fill lean-bar-fill--${polarity}`}
          style={{ width: `${halfTrackPercent}%` }}
          aria-hidden="true"
        />
      ) : null}
    </div>
  );
}
