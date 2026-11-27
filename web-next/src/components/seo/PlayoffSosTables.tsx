import Link from "next/link";

import { rankedAt, scheduleLine, SOS_POSITIONS, type PlayoffSos } from "@/lib/seo/playoffSos";
import { POSITION_NAMES } from "@/lib/seo/site";

const ROWS = 10;

/** The ranked per-position playoff schedule tables, shared by the public SEO page and the /try/playoffs ad landing. */
export function PlayoffSosTables({ sos }: { sos: PlayoffSos }) {
  const lists = SOS_POSITIONS.map((pos) => ({ pos, ranked: rankedAt(sos, pos) })).filter((l) => l.ranked.length > 0);
  return (
    <>
    {lists.map(({ pos, ranked }) => {
      const names = POSITION_NAMES[pos.toLowerCase() as keyof typeof POSITION_NAMES];
      const shown = [...ranked.slice(0, ROWS), ...ranked.slice(-5).filter((r) => !ranked.slice(0, ROWS).includes(r))];
      return (
        <section key={pos} className="flex flex-col gap-2" aria-label={`${names.upper} playoff schedules`}>
          <h2 style={{ font: "var(--type-section-title)" }}>{names.upper} playoff schedules</h2>
          <div className="glass-surface overflow-hidden">
            <table className="w-full text-sm border-collapse">
              <caption className="sr-only">{`${names.upper} fantasy playoff strength of schedule, easiest first`}</caption>
              <thead>
                <tr className="text-xs text-left" style={{ color: "var(--color-text-muted)" }}>
                  <th scope="col" className="px-3 py-2 w-10">
                    #
                  </th>
                  <th scope="col" className="px-2 py-2">
                    Team and opponents
                  </th>
                  <th scope="col" className="px-3 py-2 text-right">
                    Pts allowed
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map(({ team, row }) => (
                  <tr key={team.team} className="border-t" style={{ borderColor: "var(--color-border)" }}>
                    <td className="px-3 py-2 font-bold">{row.rank_easiest}</td>
                    <td className="px-2 py-2">
                      <span className="font-bold">{team.team}</span>
                      <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {scheduleLine(team)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      {row.avg_points_allowed.toFixed(1)}
                      <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {row.vs_league_avg_pct > 0 ? "+" : ""}
                        {row.vs_league_avg_pct.toFixed(1)}% vs avg
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      );
    })}

    <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
      Rank 1 is the easiest schedule (opponents allow the most PPR points per game to the position, recency weighted). It is a measure of opponent
      defenses, not a projection of your player. Byes and unrated opponents are skipped. Fantasy leagues set their own playoff weeks, so check yours.{" "}
      <Link href="/methodology" className="underline">
        How we evaluate
      </Link>
      .
    </p>
    </>
  );
}
