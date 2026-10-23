"use client";

import { useEffect, useMemo, useState } from "react";

import {
  api,
  type PortfolioExposureResponse,
  type PortfolioExposurePlayer,
} from "@/lib/api";
import { trackUse } from "@/lib/analytics";
import { PillRow } from "@/components/PillRow";
import { PlayerRow } from "@/components/PlayerRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { StatStrip } from "@/components/StatStrip";
import { ValueStat } from "@/components/ValueStat";
import { SkeletonBlock } from "@/components/Skeleton";

type SortKey = "leagues" | "value";

const SORT_OPTIONS = [
  { label: "Most owned", value: "leagues" },
  { label: "Value", value: "value" },
];

export function sortExposurePlayers(
  players: PortfolioExposurePlayer[],
  sort: SortKey,
): PortfolioExposurePlayer[] {
  return [...players].sort((a, b) =>
    sort === "value"
      ? b.value - a.value || b.leagues_owned - a.leagues_owned
      : b.leagues_owned - a.leagues_owned || b.value - a.value,
  );
}

const percent = (share: number) => `${Math.round(share * 100)}%`;

function ExposureRow({
  player,
  leagueCount,
}: {
  player: PortfolioExposurePlayer;
  leagueCount: number;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <PlayerRow
        bordered={!open}
        identity={{
          player_id: player.player_id,
          name: player.name,
          position: player.position,
          team: player.team,
        }}
        playerId={player.player_id}
        name={player.name}
        position={player.position}
        trailing={
          <>
            <ValueStat value={Math.round(player.value).toLocaleString()} />
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-label={`${player.name} is in ${player.leagues_owned} of ${leagueCount} leagues`}
              className="px-2 py-1 text-xs font-bold whitespace-nowrap"
              style={{
                border: "var(--border-width-default) solid var(--color-border)",
                color: "var(--color-text-secondary)",
              }}
            >
              {player.leagues_owned}/{leagueCount} {open ? "▴" : "▾"}
            </button>
          </>
        }
      >
        {[player.team, percent(player.share_of_leagues) + " of leagues"]
          .filter(Boolean)
          .join(" · ")}
      </PlayerRow>
      {open ? (
        <ul
          className="flex flex-col gap-1 pb-2 pl-14 text-sm"
          style={{
            color: "var(--color-text-secondary)",
            borderBottom:
              "var(--border-width-default) solid var(--color-border)",
          }}
        >
          {player.league_names.map((name) => (
            <li key={name}>{name}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Portfolio's "Exposure" view: which players the user owns across their
 * leagues (GET /v1/portfolio/exposure, Pro). Rendered inside the existing
 * Portfolio page, no new route. The backend sums each player's value across
 * the leagues that own him; this view only sorts and presents it.
 */
export function PortfolioExposureView({ lens = "Dynasty" }: { lens?: string }) {
  const [data, setData] = useState<PortfolioExposureResponse | null>(null);
  const [error, setError] = useState(false);
  const [sort, setSort] = useState<SortKey>("leagues");

  useEffect(() => {
    let cancelled = false;
    api
      .getPortfolioExposure(lens)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
    };
  }, [lens]);

  const players = useMemo(
    () => sortExposurePlayers(data?.exposure?.players ?? [], sort),
    [data, sort],
  );

  const exposureTier = data ? (data.is_premium ? "pro" : "free") : null;
  useEffect(() => {
    if (exposureTier) trackUse("player_exposure", "viewed", { tier: exposureTier });
  }, [exposureTier]);

  if (error) {
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Could not load exposure. Try again in a moment.
      </p>
    );
  }
  if (!data) {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <span className="sr-only">Loading exposure…</span>
        <SkeletonBlock width="100%" height={56} />
        <SkeletonBlock width="85%" height={40} />
        <SkeletonBlock width="70%" height={40} />
      </div>
    );
  }
  if (!data.is_premium || !data.exposure) {
    if (!data.is_premium) {
      return (
        <PremiumUpsellCard
          bare
          kicker="Exposure"
          upsell={data.upsell}
          fallbackTitle="See your player exposure"
          fallbackBody="Exposure is a Pro feature: which players you own across every league and how concentrated your portfolio is."
        />
      );
    }
    return (
      <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
        Save a league to see your exposure.
      </p>
    );
  }

  const { exposure } = data;
  const positions = exposure.by_position
    .filter((p) => p.share_of_value >= 0.01)
    .map((p) => `${p.position} ${percent(p.share_of_value)}`)
    .join(" · ");

  return (
    <section className="flex flex-col gap-4">
      <StatStrip
        columns={3}
        items={[
          {
            glyph: "franchise",
            label: "Leagues",
            value: String(exposure.league_count),
          },
          {
            glyph: "starter",
            label: "Players",
            value: String(exposure.player_count),
          },
          {
            glyph: "power",
            label: `Top ${exposure.concentration.top_n} share`,
            value: percent(exposure.concentration.top_share_of_value),
          },
        ]}
      />
      {positions ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          By value: {positions}
        </p>
      ) : null}
      {data.skipped_leagues.length > 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Not included:{" "}
          {data.skipped_leagues.map((l) => l.league_name).join(", ")}
          {data.skipped_leagues.some((l) => l.reason === "espn_not_supported")
            ? " (ESPN leagues aren't supported yet)"
            : ""}
        </p>
      ) : null}
      <PillRow
        options={SORT_OPTIONS}
        active={sort}
        onSelect={(value) => setSort(value as SortKey)}
      />
      <div className="flex flex-col">
        {players.map((player) => (
          <ExposureRow
            key={player.player_id}
            player={player}
            leagueCount={exposure.league_count}
          />
        ))}
      </div>
    </section>
  );
}
