import type { Metadata } from "next";
import Link from "next/link";

import { AppCta, SeoPageShell } from "@/components/seo/SeoChrome";
import { itemListLd, webPageLd } from "@/lib/seo/jsonld";
import { fetchPlayoffSos, hasUsableSos, rankedAt, scheduleLine, SOS_POSITIONS, type PlayoffSos } from "@/lib/seo/playoffSos";
import { formatUpdated } from "@/lib/seo/publicValues";
import { absoluteUrl, OG_IMAGE, POSITION_NAMES, RANKINGS_PATH } from "@/lib/seo/site";
import { playoffSosInSeason, PLAYOFF_SOS_PATH, seasonMoment } from "@/lib/seasonalLanding";

// Season-gated: indexable only while fantasy playoffs are the live question (weeks 9-17) AND the API returned
// a rated schedule. Otherwise the page still renders (no 404 for linked visitors) but is noindex and says why.
// Rendered per request (fetchPlayoffSos caches for an hour): the build cannot reach the API and the gate follows the clock.
export const dynamic = "force-dynamic";

const ROWS = 10;

async function load() {
  const moment = seasonMoment();
  const sos = await fetchPlayoffSos();
  const live = playoffSosInSeason(moment) && hasUsableSos(sos);
  return { moment, sos: live ? sos : null, live };
}

function weeksLabel(sos: PlayoffSos | null): string {
  const w = sos?.weeks ?? [15, 16, 17];
  return `Weeks ${w[0]} to ${w[w.length - 1]}`;
}

export async function generateMetadata(): Promise<Metadata> {
  const { sos, live } = await load();
  const season = sos?.season ?? seasonMoment().season;
  const title = `Fantasy Football Playoff Strength of Schedule ${season}: Best and Worst Matchups by Position`;
  const description = `Which NFL teams have the easiest fantasy playoff schedules at QB, RB, WR and TE? ${weeksLabel(sos)} opponents ranked by points allowed to each position.`;
  const url = absoluteUrl(PLAYOFF_SOS_PATH);
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: live ? undefined : { index: false, follow: true },
    openGraph: { title, description, url, type: "website", siteName: "FantasyDesk", images: [OG_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [OG_IMAGE.url] },
  };
}

export default async function PlayoffSosPage() {
  const { sos, live, moment } = await load();
  const title = `Fantasy Football Playoff Strength of Schedule ${sos?.season ?? moment.season}`;
  const crumbs = [
    { name: "FantasyDesk", path: "/" },
    { name: "Dynasty tools", path: "/dynasty-tools" },
    { name: "Playoff strength of schedule", path: PLAYOFF_SOS_PATH },
  ];

  if (!live || !sos) {
    return (
      <SeoPageShell
        crumbs={crumbs}
        kicker="Strength of schedule"
        title={title}
        intro="Playoff schedule rankings appear here once the fantasy playoffs are close and enough games have been played to rate every defense."
        jsonLd={[]}
      >
        <section className="glass-surface p-4 flex flex-col gap-2">
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            There is nothing to rank right now. Until then, dynasty rankings and the free trade analyzer work year round.
          </p>
          <Link href={RANKINGS_PATH("qb")} className="text-sm font-bold underline" style={{ color: "var(--color-accent)" }}>
            Dynasty QB rankings
          </Link>
        </section>
        <AppCta title="See your own team's schedule" body="Connect a league to see your players' matchups week by week." campaign="playoff_sos_page" />
      </SeoPageShell>
    );
  }

  const updated = formatUpdated(sos.generated_at);
  const description = `${weeksLabel(sos)} opponents ranked by points allowed to each position.`;
  const lists = SOS_POSITIONS.map((pos) => ({ pos, ranked: rankedAt(sos, pos) })).filter((l) => l.ranked.length > 0);

  return (
    <SeoPageShell
      crumbs={crumbs}
      kicker="Strength of schedule"
      title={title}
      intro={`${weeksLabel(sos)} are the usual fantasy playoff weeks. Here is which offenses face the softest and toughest defenses at each position, ranked from the opponents' points allowed this season.`}
      updated={updated}
      jsonLd={[
        webPageLd({ name: title, description, path: PLAYOFF_SOS_PATH, dateModified: sos.generated_at }),
        ...lists.slice(0, 1).map((l) =>
          itemListLd({ name: `Easiest ${l.pos} playoff schedules`, path: PLAYOFF_SOS_PATH, items: l.ranked.slice(0, ROWS).map((r) => ({ name: r.team.team })) }),
        ),
      ]}
    >
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
      <AppCta
        title="See your own players' matchups"
        body="This page ranks every team. FantasyDesk reads your roster, weighs the opponent and the weather, and tells you who to start in the playoffs."
        campaign="playoff_sos_page"
      />
    </SeoPageShell>
  );
}
