import { PostureChip } from "@/components/PostureChip";
import { ToneBadge } from "@/components/ToneBadge";
import type { TradePosture } from "@/lib/api";

export interface IdeaPostureFields {
  posture?: TradePosture | null;
  posture_label?: string;
  posture_note?: string;
  posture_alignment?: "aligned" | "neutral" | "costly" | "";
}

/**
 * The team posture a trade idea was graded and ranked under: the shared
 * PostureChip, the Analyzer's honest label when the idea is a trade-off, and the
 * one-line note (modules/trade_posture.py). Used by Trade Hub / Finder cards and
 * the Dashboard trade tile so they all read like the Trade Analyzer.
 */
export function IdeaPosture({ idea, leagueId }: { idea: IdeaPostureFields; leagueId?: string }) {
  if (!idea.posture) return null;
  return (
    <div className="flex flex-col gap-1" data-testid="idea-posture">
      <PostureChip posture={idea.posture} leagueId={leagueId} />
      {idea.posture_label ? (
        <ToneBadge label={idea.posture_label} color="var(--color-warning)" />
      ) : idea.posture_alignment === "aligned" ? (
        <ToneBadge label="Fits your plan" color="var(--color-success)" />
      ) : null}
      {idea.posture_note ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {idea.posture_note}
        </p>
      ) : null}
    </div>
  );
}
