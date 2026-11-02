import Link from "next/link";
import { ToneBadge } from "@/components/ToneBadge";
import type { TradePosture } from "@/lib/api";

/**
 * The team posture a trade verdict was graded under (modules/trade_posture.py),
 * as the shared ToneBadge pill plus a one-line "why". Neutral information tint
 * on purpose: a posture is context, not good or bad news. When the posture was
 * inferred (not declared) the line links to Team Situation, the existing
 * override.
 */
export function PostureChip({ posture, leagueId }: { posture: TradePosture; leagueId?: string }) {
  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="posture-chip">
      <ToneBadge
        label={posture.label}
        color="var(--color-information)"
        title={`Graded as ${posture.label} (${posture.confidence_label} confidence)`}
        srLabel={`Graded as a ${posture.label} team, ${posture.confidence_label} confidence`}
      />
      <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {posture.why}
        {posture.source !== "declared" && leagueId ? (
          <>
            {" "}
            <Link href={`/team-situation/${leagueId}`} className="underline" style={{ color: "var(--color-accent)" }}>
              Change
            </Link>
          </>
        ) : null}
      </span>
    </div>
  );
}
