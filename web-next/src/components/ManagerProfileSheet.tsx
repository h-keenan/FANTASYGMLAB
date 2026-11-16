"use client";

import { ButtonLink } from "@/components/Button";
import { useEffect, useState } from "react";

import { api, type ManagerRecentTradeAsset, type ManagerTendenciesDetailResponse, type TeamSheetPlayer, type TeamSheetResponse } from "@/lib/api";
import { AccentCard } from "@/components/AccentCard";
import { TeamAvatar } from "@/components/TeamAvatar";
import { SectionHeading } from "@/components/SectionHeading";
import { TeamSheetFrame, TeamSheetOverview } from "@/components/TeamSheet";
import { ToneBadge } from "@/components/ToneBadge";
import { gradeToneColor, sampleFill, TENDENCY_SIGNALS, tendencyBadgeText, tendencyTone, tradeDateLabel } from "@/lib/managerTendencies";
import { PopupShell } from "@/components/PopupShell";

import { PickPlate } from "@/components/PickRow";
import { OpponentProfileCard } from "@/components/OpponentProfileCard";
import type { OpponentProfileResponse } from "@/lib/opponentProfile";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import { SkeletonText } from "@/components/Skeleton";
import { teamSheetNextGameLine, teamSheetPoints, teamSheetSeasonLine, tradeStyleFromSignals, type TeamSheetChip } from "@/lib/teamSheet";

function TradeAssetLine({ asset }: { asset: ManagerRecentTradeAsset }) {
  if (asset.kind === "pick") {
    return (
      <div className="flex items-center gap-2 min-w-0">
        <PickPlate round={asset.round} />
        <span className="text-sm font-bold break-words">{asset.label || "Draft pick"}</span>
      </div>
    );
  }
  return (
    <CompactPlayerCard
      player={{ id: asset.player_id ?? null, name: asset.name ?? "Player", position: asset.position ?? null, team: asset.team ?? null }}
      detail={asset.team}
      testId="manager-trade-player"
    />
  );
}

function RecentTrades({ trades }: { trades: NonNullable<ManagerTendenciesDetailResponse["recent_trades"]> }) {
  return (
    <>
      <SectionHeading>Recent trades</SectionHeading>
      <ul className="flex flex-col gap-2">
        {trades.map((trade) => (
          <li key={trade.transaction_id}>
            <AccentCard accent="var(--color-border)" compact as="div">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {tradeDateLabel(trade.date, trade.week)}
                  {trade.partners.length ? ` · with ${trade.partners.join(", ")}` : ""}
                </span>
                {trade.grade ? (
                  <ToneBadge label={trade.grade.letter} color={gradeToneColor(trade.grade.tone)} />
                ) : null}
              </div>
              {(
                [
                  ["Got", trade.received],
                  ["Sent", trade.sent],
                ] as Array<[string, ManagerRecentTradeAsset[]]>
              ).map(([label, assets]) =>
                assets.length ? (
                  <div key={label} className="flex flex-col gap-1">
                    <span
                      className="text-xs uppercase font-extrabold"
                      style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
                    >
                      {label}
                    </span>
                    {assets.map((asset, i) => (
                      <TradeAssetLine key={`${asset.player_id ?? asset.label}-${i}`} asset={asset} />
                    ))}
                  </div>
                ) : null,
              )}
            </AccentCard>
          </li>
        ))}
      </ul>
    </>
  );
}

function PlayerRows({ players }: { players: TeamSheetPlayer[] }) {
  return (
    <ul className="flex flex-col gap-1">
      {players.map((p) => (
        <li key={p.player_id}>
          <CompactPlayerCard
            player={{ id: p.player_id, name: p.name, position: p.position, team: p.team }}
            detail={[p.team, p.age != null ? `${p.age} yrs` : ""].filter(Boolean).join(" · ")}
            trailing={p.injury_status ? <ToneBadge label={p.injury_status} color="var(--color-danger)" size="xs" /> : undefined}
            testId="team-sheet-player"
          />
        </li>
      ))}
    </ul>
  );
}

function Note({ children }: { children: string }) {
  return <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>{children}</p>;
}

/**
 * The Desk team sheet: tapping any team (League Rankings, Matchup opponent, Trade Hub partners, recaps) opens
 * this with REAL Sleeper data. It renders through the shared TeamSheet (the same component the Fantasy Sim
 * team sheet uses). Record, power rank, strengths/needs, injuries, roster and past seasons are free
 * (GET .../teams/{id}/sheet); the trade-style tag, tendencies and recent trades are Pro
 * (GET .../managers/{id}/tendencies) and show the existing upsell for Free. Loaded only when opened.
 */
export function ManagerProfileSheet({
  leagueId,
  leagueName = "",
  rosterId,
  teamName,
  ownerName,
  avatarUrl,
  onClose,
}: {
  leagueId: string;
  /** For the "Offer this" Trade Analyzer link. */
  leagueName?: string;
  rosterId: string | number;
  teamName: string;
  ownerName?: string | null;
  avatarUrl?: string | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<ManagerTendenciesDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [profile, setProfile] = useState<OpponentProfileResponse | null>(null);
  const [sheet, setSheet] = useState<TeamSheetResponse | null>(null);
  const [sheetFailed, setSheetFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getTeamSheet(leagueId, rosterId)
      .then((result) => {
        if (cancelled) return;
        if (!result.ok || result.reason || !result.record) setSheetFailed(true);
        else setSheet(result);
      })
      .catch(() => {
        if (!cancelled) setSheetFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, rosterId]);

  // The roster profile (trade angle) is free and independent of the Pro tendencies; a failure just hides the card.
  useEffect(() => {
    let cancelled = false;
    api
      .getTeamProfile(leagueId, rosterId)
      .then((result) => {
        if (!cancelled) setProfile(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [leagueId, rosterId]);

  useEffect(() => {
    let cancelled = false;
    api
      .getManagerTendencyDetail(leagueId, rosterId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, rosterId]);

  const signals = data?.manager?.signals ?? {};
  const rows = TENDENCY_SIGNALS.filter(([key]) => signals[key]?.status === "ok");
  const style = data?.is_premium ? tradeStyleFromSignals(signals) : null;
  const upsell =
    data && !data.is_premium ? (
      <span className="flex flex-col items-start gap-2">
        <span className="font-bold">{data.upsell?.title ?? "Manager Tendencies"}</span>
        <ButtonLink href="/premium" variant="premium" size="sm">
          Upgrade →
        </ButtonLink>
      </span>
    ) : null;

  const record = sheet?.record;
  const chips: TeamSheetChip[] = [];
  if (sheet?.power_rank) chips.push({ label: `Power #${sheet.power_rank}`, tone: "premium" });
  if (record?.playoff_status) {
    chips.push({ label: record.playoff_status.toUpperCase(), tone: record.playoff_status === "out" || record.playoff_status === "eliminated" ? "muted" : "success" });
  }
  const tag = style ? (
    <ToneBadge label={style.tag} color="var(--color-accent)" size="xs" />
  ) : data && !data.is_premium ? (
    <ToneBadge label="TRADE STYLE · PRO" color="var(--color-premium)" size="xs" />
  ) : null;
  const tiles = [
    { label: "Record", value: record?.label || "-" },
    { label: "Rank", value: record?.standing_rank ? `#${record.standing_rank}` : "-" },
    { label: "PF", value: teamSheetPoints(record?.points_for) },
    { label: "Proj", value: teamSheetPoints(sheet?.projected_total) },
  ];
  const roster = sheet?.roster ?? [];
  const by = (slot: TeamSheetPlayer["slot"]) => roster.filter((p) => p.slot === slot);
  const nameShown = sheet?.team?.team_name || teamName || "Manager profile";
  const owner = sheet?.team?.owner_name || ownerName || null;
  const needLine = [
    (sheet?.strengths ?? []).length ? `Strong at ${sheet!.strengths!.join(", ")}.` : "",
    (sheet?.needs ?? []).length ? `Needs ${sheet!.needs!.join(", ")}.` : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <PopupShell title={teamName || "Manager profile"} onClose={onClose} labelledBy="mgr-profile-name" closeLabel="Close manager profile" portal={false}>
      <div className="pqv-scroll">
        <TeamSheetFrame
          id="manager-profile"
          logo={<TeamAvatar avatarUrl={sheet?.team?.avatar_url || avatarUrl} name={owner || nameShown} size={48} />}
          name={nameShown}
          nameId="mgr-profile-name"
          nameTestId="team-sheet-name"
          tag={tag}
          chips={chips}
          managedBy={owner}
          tabs={[
            {
              key: "overview",
              label: "Overview",
              render: () =>
                sheetFailed ? (
                  <Note>Couldn&apos;t load this team.</Note>
                ) : !sheet ? (
                  <SkeletonText label="team sheet" lines={4} />
                ) : (
                  <TeamSheetOverview
                    blurb={style?.blurb || upsell}
                    tiles={tiles}
                    streak={sheet.streak}
                    nextGame={teamSheetNextGameLine(sheet.next_game ? { week: sheet.next_game.week, opponent: sheet.next_game.opponent.name } : null)}
                    positions={sheet.positions ?? []}
                    strengthsTitle={<SectionHeading note={needLine || undefined}>Strengths and needs</SectionHeading>}
                    injuries={
                      (sheet.injuries ?? []).length > 0 ? (
                        <section className="flex flex-col gap-1" aria-label="Injuries">
                          <SectionHeading>Injuries</SectionHeading>
                          <PlayerRows players={sheet.injuries!} />
                        </section>
                      ) : null
                    }
                  />
                ),
            },
            {
              key: "roster",
              label: "Roster",
              render: () =>
                !sheet ? (
                  sheetFailed ? <Note>Couldn&apos;t load this roster.</Note> : <SkeletonText label="roster" lines={4} />
                ) : roster.length === 0 ? (
                  <Note>No players on this roster yet.</Note>
                ) : (
                  <div className="flex flex-col gap-3">
                    {(
                      [
                        ["starter", "Starters"],
                        ["bench", "Bench"],
                        ["ir", "Injured reserve"],
                        ["taxi", "Taxi squad"],
                      ] as const
                    ).map(([slot, label]) =>
                      by(slot).length ? (
                        <section key={slot} className="flex flex-col gap-1" aria-label={label}>
                          <SectionHeading>{label}</SectionHeading>
                          <PlayerRows players={by(slot)} />
                        </section>
                      ) : null,
                    )}
                  </div>
                ),
            },
            {
              key: "trades",
              label: "Trades",
              render: () => (
                <div className="flex flex-col gap-3">
                  <OpponentProfileCard profile={profile} leagueId={leagueId} leagueName={leagueName} />
                  {failed ? (
                    <Note>Couldn&apos;t load trade history.</Note>
                  ) : !data ? (
                    <SkeletonText label="manager trades" lines={3} />
                  ) : !data.is_premium ? (
                    upsell
                  ) : rows.length === 0 ? (
                    <Note>Not enough trade history yet.</Note>
                  ) : (
                    <>
                      <SectionHeading>Tendencies</SectionHeading>
                      <ul className="flex flex-col gap-2">
                        {rows.map(([key, title]) => {
                          const signal = signals[key];
                          const tone = `var(--color-${tendencyTone(signal.label)})`;
                          const badge = tendencyBadgeText(signal.label);
                          return (
                            <li key={key}>
                              <AccentCard accent={tone} compact as="div">
                                <div className="flex items-center justify-between gap-2">
                                  <span className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
                                    {title}
                                  </span>
                                  {badge ? <ToneBadge label={badge} color={tone} /> : null}
                                </div>
                                <span className="text-sm font-semibold">{signal.summary}</span>
                                <div className="flex items-center gap-2">
                                  <div className="flex-1 h-1 overflow-hidden" style={{ background: "var(--color-surface-muted)", borderRadius: "var(--radius-pill)" }} role="presentation">
                                    <div className="h-full" style={{ width: `${Math.round(sampleFill(signal.sample_size, signal.min_sample) * 100)}%`, background: tone, borderRadius: "var(--radius-pill)" }} />
                                  </div>
                                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                                    {signal.sample_size} trade{signal.sample_size === 1 ? "" : "s"}
                                  </span>
                                </div>
                              </AccentCard>
                            </li>
                          );
                        })}
                      </ul>
                      {data.recent_trades && data.recent_trades.length > 0 ? <RecentTrades trades={data.recent_trades} /> : null}
                    </>
                  )}
                </div>
              ),
            },
            {
              key: "history",
              label: "History",
              render: () =>
                !sheet ? (
                  sheetFailed ? <Note>Couldn&apos;t load season history.</Note> : <SkeletonText label="history" lines={3} />
                ) : (sheet.history ?? []).length === 0 ? (
                  <Note>No past seasons in this league yet.</Note>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {sheet.history!.map((h) => (
                      <li key={h.league_id}>
                        <AccentCard accent="var(--color-border)" compact as="div">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-sm font-extrabold">{h.season}</span>
                            <span className="text-sm font-bold tabular-nums">{teamSheetSeasonLine(h)}</span>
                          </div>
                          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{teamSheetPoints(h.points_for)} points for</span>
                        </AccentCard>
                      </li>
                    ))}
                  </ul>
                ),
            },
          ]}
        />
      </div>
    </PopupShell>
  );
}
