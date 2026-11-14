import Link from "next/link";

import { trendLabel } from "@/lib/seo/content";
import type { PublicPlayer } from "@/lib/seo/publicValues";
import { PLAYER_PATH } from "@/lib/seo/site";

export interface ValueRow {
  rank: number;
  player: PublicPlayer;
  /** Slug when the player has a page; otherwise rendered as plain text. */
  slug: string | null;
  /** Optional second value column (e.g. Superflex). */
  extra?: { value: number; rank: number } | null;
}

/** One glyph per trend so the meta line stays on one row at phone width; the words live in the accessible name. */
const TREND_GLYPH: Record<string, string> = { rising: "↑", stable: "→", cooling: "↓", fragile: "!", blocked: "×" };
const TREND_COLOR: Record<string, string> = {
  rising: "var(--color-success)",
  cooling: "var(--color-warning)",
  fragile: "var(--color-danger)",
  blocked: "var(--color-danger)",
};

export function ValueTable({
  rows,
  valueHeader,
  extraHeader,
  caption,
}: {
  rows: readonly ValueRow[];
  valueHeader: string;
  extraHeader?: string;
  caption: string;
}) {
  return (
    <div className="glass-surface overflow-hidden">
      <table className="w-full text-sm border-collapse">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="text-xs text-left" style={{ color: "var(--color-text-muted)" }}>
            <th scope="col" className="px-3 py-2 w-10">
              #
            </th>
            <th scope="col" className="px-2 py-2">
              Player
            </th>
            <th scope="col" className="px-2 py-2 text-right">
              {valueHeader}
            </th>
            {extraHeader ? (
              <th scope="col" className="px-3 py-2 text-right">
                {extraHeader}
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {rows.map(({ rank, player, slug, extra }) => {
            const trend = trendLabel(player.trend);
            const meta = [player.team, player.age !== null ? `age ${player.age}` : null]
              .filter(Boolean)
              .join(" · ");
            return (
              <tr key={player.player_id} style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
                <td className="px-3 py-2 align-top font-bold">{rank}</td>
                <td className="px-2 py-2">
                  {slug ? (
                    <Link href={PLAYER_PATH(slug)} className="font-bold underline" style={{ color: "var(--color-text-primary)" }}>
                      {player.name}
                    </Link>
                  ) : (
                    <span className="font-bold">{player.name}</span>
                  )}
                  <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {player.position} · {meta}
                    {trend ? (
                      <>
                        {" · "}
                        <span role="img" aria-label={`Workload trend: ${trend}`} title={`Trend: ${trend}`} data-trend={trend} style={{ color: TREND_COLOR[trend] ?? "inherit" }}>
                          {TREND_GLYPH[trend] ?? "•"}
                        </span>
                      </>
                    ) : null}
                  </span>
                </td>
                <td className="px-2 py-2 text-right align-top font-bold">{player.score.toLocaleString("en-US")}</td>
                {extraHeader ? (
                  <td className="px-3 py-2 text-right align-top">
                    {extra ? (
                      <>
                        <span className="font-bold">{extra.value.toLocaleString("en-US")}</span>
                        <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                          #{extra.rank}
                        </span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                ) : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
