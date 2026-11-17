"use client";

import { AdpCredit, AdpInline } from "@/components/AdpInline";
import { CompactModule } from "@/components/ui/CompactModule";
import { deltaText, ROOKIE_BOARD_NO_ADP_NOTE, ROOKIE_BOARD_TITLE, rookieBoardSummaryParts } from "@/lib/adpPresentation";
import type { RookieAdpBoard as RookieAdpBoardData } from "@/lib/api";

const VERDICT_LABEL: Record<string, string> = {
  value: "Value",
  aligned: "Aligned",
  reach: "Reach",
};

/**
 * Draft Center rookie board: our rookie rank next to market rookie ADP (Fantasy Football
 * Calculator) with value-vs-ADP, sample size and trend in the read line. Rookie ADP only
 * exists in the rookie-draft season; with no feed rows it says so instead of inventing any.
 */
export function RookieAdpBoard({ board }: { board: RookieAdpBoardData | undefined }) {
  if (!board || board.rows.length === 0) return null;
  const withAdp = board.rows.filter((row) => row.adp != null);
  return (
    <CompactModule
      id="draft.rookie-adp-board"
      title={ROOKIE_BOARD_TITLE}
      persist={false}
      parts={rookieBoardSummaryParts(board.rows)}
    >
      {withAdp.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {ROOKIE_BOARD_NO_ADP_NOTE}
        </p>
      ) : null}
      <div className="flex flex-col" data-testid="rookie-adp-board">
        {board.rows.map((row) => (
          <div key={row.player_id} className="py-2 flex flex-col gap-0.5" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-bold truncate">
                #{row.our_rank} {row.name}
                <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>{` ${row.position} · ${row.team || "FA"}`}</span>
              </span>
              <span className="text-xs shrink-0" style={{ color: "var(--color-text-secondary)" }}>
                {row.adp != null ? (
                  <>
                    <AdpInline adp={{ adp: row.adp, adp_label: row.adp_label, adp_est_sf: row.adp_est_sf, adp_est_sf_label: row.adp_est_sf_label }} note={board.est_sf_note ?? undefined} />
                    {row.verdict ? ` · ${VERDICT_LABEL[row.verdict]} ${deltaText(row.delta)}` : ""}
                  </>
                ) : (
                  "No ADP yet"
                )}
              </span>
            </div>
            {row.read ? (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {row.read}
              </span>
            ) : null}
          </div>
        ))}
      </div>
      {board.source ? <AdpCredit asOf={board.source.as_of} /> : null}
      {board.est_sf_note ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Est. SF is modeled, not real ADP. {board.est_sf_note}
        </p>
      ) : null}
    </CompactModule>
  );
}
