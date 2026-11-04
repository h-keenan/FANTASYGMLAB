"use client";

import { useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PillRow } from "@/components/PillRow";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { TradeAssetRow } from "@/components/TradeAssetExchange";
import { api, type DraftPickAsset, type RankedPlayer, type TeamProfile } from "@/lib/api";
import {
  buildVetoRequest,
  formatSigned,
  vetoBandTone,
  vetoHasResult,
  vetoPointsLine,
  vetoSideDirection,
  vetoStatusMessage,
  vetoWorstPositionLine,
  VETO_BAND_LABEL,
  type VetoBand,
  type VetoCheckResponse,
  type VetoSide,
} from "@/lib/commissionerIntegrity";
import { pickToTradeAsset, playerToTradeAsset } from "@/lib/tradeAnalyzerPresentation";

/**
 * Commissioner: Trade veto calculator. The commissioner enters a proposed
 * two-team trade (Sleeper does not publish pending trades) and the server
 * (modules/trade_veto.py) grades it for BOTH whole rosters at each team's own
 * posture, so a rebuilding team that sells a vet for youth or picks can lose
 * market value and still read fine. Nothing is computed here. A decision aid:
 * the league's rules decide. Mirrors mobile's CommissionerScreen section.
 */

const TONE_COLOR = {
  success: "var(--color-success)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
  muted: "var(--color-text-muted)",
} as const;

function bandColor(band: VetoBand): string {
  return TONE_COLOR[vetoBandTone(band)];
}

interface TeamOption {
  rosterId: string;
  label: string;
  playerIds: Set<string>;
}

interface PoolData {
  teams: TeamOption[];
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
}

const MAX_RESULTS = 40;

function Caption({ children }: { children: string }) {
  return (
    <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
      {children}
    </span>
  );
}

function VetoSideCard({ side, hurt }: { side: VetoSide; hurt: boolean }) {
  const posture = vetoSideDirection(side);
  const worst = vetoWorstPositionLine(side);
  return (
    <AccentCard accent={hurt ? "var(--color-warning)" : "var(--color-border)"} as="article">
      <div className="flex items-start justify-between gap-2">
        <span className="text-base font-extrabold" style={{ color: "var(--color-text-primary)" }}>
          {side.team_name}
        </span>
        {posture ? <ToneBadge label={posture} color="var(--color-text-muted)" /> : null}
      </div>
      <div className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        <span>Sends: {side.sends.length ? side.sends.join(", ") : "nothing"}</span>
        <span>Receives: {side.receives.length ? side.receives.join(", ") : "nothing"}</span>
        <span>Market value {formatSigned(side.market_delta)}</span>
        <span>{vetoPointsLine(side)}</span>
        {worst ? <span>{worst}</span> : null}
      </div>
    </AccentCard>
  );
}

export function VetoResult({ result }: { result: VetoCheckResponse }) {
  if (!vetoHasResult(result)) return null;
  const band = result.band as VetoBand;
  const color = bandColor(band);
  return (
    <section className="flex flex-col gap-3" aria-label="Veto check result" data-testid="veto-result">
      <AccentCard accent={color} as="section">
        <div className="flex items-center justify-between gap-3">
          <div className="flex flex-col">
            <span className="font-black" style={{ fontSize: "2.5rem", lineHeight: 1, color }} data-testid="veto-outrage">
              {Math.round(result.outrage ?? 0)}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              out of 100
            </span>
          </div>
          <ToneBadge label={VETO_BAND_LABEL[band] ?? result.label ?? band} color={color} wrap />
        </div>
        {result.advice ? (
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {result.advice}
          </p>
        ) : null}
      </AccentCard>
      {(result.sides ?? []).map((side) => (
        <VetoSideCard key={side.roster_id} side={side} hurt={String(side.roster_id) === String(result.hurt_roster_id)} />
      ))}
      {result.reasons?.length ? (
        <div className="flex flex-col gap-1">
          <Caption>Why</Caption>
          <ul className="flex flex-col gap-1 list-disc pl-4">
            {result.reasons.map((reason) => (
              <li key={reason} className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {result.limits?.length ? (
        <ul className="flex flex-col gap-1" data-testid="veto-limits">
          {result.limits.map((limit) => (
            <li key={limit} className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {limit}
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function VetoBuilder({ leagueId, lens, pool }: { leagueId: string; lens: string; pool: PoolData }) {
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [side, setSide] = useState<"a" | "b">("a");
  const [assetType, setAssetType] = useState<"players" | "picks">("players");
  const [search, setSearch] = useState("");
  const [aPlayers, setAPlayers] = useState<RankedPlayer[]>([]);
  const [bPlayers, setBPlayers] = useState<RankedPlayer[]>([]);
  const [aPicks, setAPicks] = useState<DraftPickAsset[]>([]);
  const [bPicks, setBPicks] = useState<DraftPickAsset[]>([]);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<VetoCheckResponse | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const activeId = side === "a" ? teamA : teamB;
  const activeTeam = pool.teams.find((t) => t.rosterId === activeId);

  function clearResult() {
    setResult(null);
    setFailure(null);
  }

  function chooseTeam(which: "a" | "b", id: string) {
    if (which === "a") {
      setTeamA(id);
      setAPlayers([]);
      setAPicks([]);
      if (teamB === id) setTeamB("");
    } else {
      setTeamB(id);
      setBPlayers([]);
      setBPicks([]);
      if (teamA === id) setTeamA("");
    }
    clearResult();
  }

  const selectedPlayerIds = useMemo(() => new Set([...aPlayers, ...bPlayers].map((p) => p.player_id)), [aPlayers, bPlayers]);
  const selectedPickIds = useMemo(() => new Set([...aPicks, ...bPicks].map((p) => p.pick_id)), [aPicks, bPicks]);

  const playerResults = useMemo(() => {
    if (!activeTeam) return [];
    const q = search.trim().toLowerCase();
    return pool.rankings
      .filter((p) => activeTeam.playerIds.has(p.player_id) && !selectedPlayerIds.has(p.player_id))
      .filter((p) => !q || (p.name ?? "").toLowerCase().includes(q))
      .slice(0, MAX_RESULTS);
  }, [pool.rankings, activeTeam, search, selectedPlayerIds]);

  const pickResults = useMemo(() => {
    if (!activeTeam) return [];
    const q = search.trim().toLowerCase();
    return pool.picks
      .filter((p) => String(p.owner_roster_id) === activeTeam.rosterId && !selectedPickIds.has(p.pick_id))
      .filter((p) => !q || (p.label ?? "").toLowerCase().includes(q))
      .slice(0, MAX_RESULTS);
  }, [pool.picks, activeTeam, search, selectedPickIds]);

  const request = buildVetoRequest({
    rosterA: teamA,
    rosterB: teamB,
    aPlayers: aPlayers.map((p) => p.player_id),
    bPlayers: bPlayers.map((p) => p.player_id),
    aPicks: aPicks.map((p) => p.pick_id),
    bPicks: bPicks.map((p) => p.pick_id),
    lens,
  });

  async function check() {
    if (!request) return;
    setChecking(true);
    clearResult();
    try {
      setResult(await api.postCommissionerVetoCheck(leagueId, request));
    } catch (err) {
      setFailure(err instanceof Error ? err.message : "Could not check this trade.");
    } finally {
      setChecking(false);
    }
  }

  const teamOptions = pool.teams.map((t) => ({ label: t.label, value: t.rosterId }));
  const nameOf = (id: string) => pool.teams.find((t) => t.rosterId === id)?.label ?? "";

  function sendList(which: "a" | "b") {
    const players = which === "a" ? aPlayers : bPlayers;
    const picks = which === "a" ? aPicks : bPicks;
    const setPlayers = which === "a" ? setAPlayers : setBPlayers;
    const setPicks = which === "a" ? setAPicks : setBPicks;
    return (
      <div className="flex flex-col gap-1 min-w-0">
        <Caption>{`${nameOf(which === "a" ? teamA : teamB) || (which === "a" ? "Team A" : "Team B")} sends`}</Caption>
        {players.length + picks.length === 0 ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            None selected
          </span>
        ) : (
          <div className="flex flex-col divide-y" style={{ borderColor: "var(--color-border)" }}>
            {players.map((p) => (
              <button
                key={p.player_id}
                type="button"
                className="w-full text-left"
                aria-label={`Remove ${p.name ?? "player"}`}
                onClick={() => {
                  setPlayers((prev) => prev.filter((x) => x.player_id !== p.player_id));
                  clearResult();
                }}
              >
                <TradeAssetRow asset={playerToTradeAsset(p)} disableQuickView />
              </button>
            ))}
            {picks.map((p) => (
              <button
                key={p.pick_id}
                type="button"
                className="w-full text-left"
                aria-label={`Remove ${p.label ?? "pick"}`}
                onClick={() => {
                  setPicks((prev) => prev.filter((x) => x.pick_id !== p.pick_id));
                  clearResult();
                }}
              >
                <TradeAssetRow asset={pickToTradeAsset(p)} />
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <Caption>Team A</Caption>
        <PillRow options={teamOptions} active={teamA} onSelect={(v) => chooseTeam("a", v)} variant="scroll" ariaLabel="Team A" />
      </div>
      <div className="flex flex-col gap-1">
        <Caption>Team B</Caption>
        <PillRow
          options={teamOptions.filter((o) => o.value !== teamA)}
          active={teamB}
          onSelect={(v) => chooseTeam("b", v)}
          variant="scroll"
          ariaLabel="Team B"
        />
      </div>

      {teamA && teamB ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            {sendList("a")}
            {sendList("b")}
          </div>
          <div className="flex flex-col gap-2">
            <PillRow
              options={[
                { label: `${nameOf(teamA)} sends`, value: "a" },
                { label: `${nameOf(teamB)} sends`, value: "b" },
              ]}
              active={side}
              onSelect={(v) => {
                setSide(v === "b" ? "b" : "a");
                setSearch("");
              }}
              variant="scroll"
              ariaLabel="Whose assets to add"
            />
            <PillRow
              options={[
                { label: "Players", value: "players" },
                { label: "Picks", value: "picks" },
              ]}
              active={assetType}
              onSelect={(v) => setAssetType(v === "picks" ? "picks" : "players")}
            />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={assetType === "picks" ? "Search picks" : "Search players"}
              aria-label="Search assets"
              className="glass-input w-full px-3 py-2 text-sm"
              style={{ color: "var(--color-text-primary)" }}
            />
            <div className="flex flex-col divide-y max-h-72 overflow-y-auto" style={{ borderColor: "var(--color-border)" }}>
              {assetType === "picks" ? (
                pickResults.length ? (
                  pickResults.map((pick) => (
                    <button
                      key={pick.pick_id}
                      type="button"
                      className="w-full text-left"
                      onClick={() => {
                        (side === "a" ? setAPicks : setBPicks)((prev) => [...prev, pick]);
                        clearResult();
                      }}
                    >
                      <TradeAssetRow asset={pickToTradeAsset(pick)} />
                    </button>
                  ))
                ) : (
                  <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>
                    No picks to add.
                  </p>
                )
              ) : playerResults.length ? (
                playerResults.map((player) => (
                  <button
                    key={player.player_id}
                    type="button"
                    className="w-full text-left"
                    onClick={() => {
                      (side === "a" ? setAPlayers : setBPlayers)((prev) => [...prev, player]);
                      clearResult();
                    }}
                  >
                    <TradeAssetRow asset={playerToTradeAsset(player)} disableQuickView />
                  </button>
                ))
              ) : (
                <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>
                  No players to add.
                </p>
              )}
            </div>
          </div>
          <Button variant="primary" fullWidth loading={checking} disabled={!request} onClick={check}>
            Check this trade
          </Button>
        </>
      ) : (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Pick the two teams in the trade, then add what each one sends.
        </p>
      )}

      {checking ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }} role="status">
          Checking both rosters…
        </p>
      ) : failure ? (
        <ErrorState message={failure} onRetry={check} />
      ) : result ? (
        result.status === "locked" ? (
          <PremiumUpsellCard
            kicker="Trade veto calculator"
            leagueName=""
            upsell={result.upsell ?? null}
            fallbackTitle="Check a trade before it processes"
            fallbackBody="The trade veto calculator is a Pro feature: it grades a proposed trade for both whole rosters."
            bare
          />
        ) : result.status === "ok" && vetoHasResult(result) ? (
          <VetoResult result={result} />
        ) : result.status === "error" || result.status === "unavailable" ? (
          <ErrorState message={vetoStatusMessage(result)} onRetry={check} />
        ) : (
          <EmptyState title="Can't check this trade" subtitle={vetoStatusMessage(result)} />
        )
      ) : null}
    </div>
  );
}

export function VetoCalculator({ leagueId, lens = "Dynasty" }: { leagueId: string; lens?: string }) {
  const [open, setOpen] = useState(false);
  const [pool, setPool] = useState<PoolData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [rankings, picks, rosters, profiles] = await Promise.all([
        api.getLeagueRankings(leagueId, lens),
        api.getLeagueDraftPicks(leagueId, lens).catch(() => ({ picks: [] as DraftPickAsset[] })),
        api.getLeagueRosters(leagueId),
        api.getLeagueTeamProfiles(leagueId).catch(() => ({ profiles: {} as Record<string, TeamProfile> })),
      ]);
      const teams = rosters.rosters
        .map((roster) => {
          const rosterId = String((roster.roster_id as string | number | undefined) ?? "");
          const players = Array.isArray(roster.players) ? (roster.players as unknown[]) : [];
          const profile = profiles.profiles[rosterId];
          const label = [profile?.team_name, profile?.owner_name].filter(Boolean).join(" · ") || `Team ${rosterId}`;
          return { rosterId, label, playerIds: new Set(players.map(String)) };
        })
        .filter((t) => t.rosterId)
        .sort((a, b) => a.label.localeCompare(b.label));
      setPool({ teams, rankings: rankings.players, picks: picks.picks });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the league's teams.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 pt-4 border-t" style={{ borderColor: "var(--color-border)" }} aria-label="Trade veto calculator" data-testid="veto-calculator">
      <SectionHeading note="Enter a proposed trade and see how lopsided it reads for each team's whole roster, at that team's own direction. A decision aid: the league's rules decide.">
        Trade veto calculator
      </SectionHeading>
      {!open ? (
        <Button
          variant="secondary"
          onClick={() => {
            setOpen(true);
            if (!pool) void load();
          }}
        >
          Check a proposed trade
        </Button>
      ) : loading || (!pool && !error) ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }} role="status">
          Loading the league&rsquo;s teams…
        </p>
      ) : error || !pool ? (
        <ErrorState message={error || "Could not load the league's teams."} onRetry={() => void load()} />
      ) : pool.teams.length < 2 ? (
        <EmptyState title="Not enough teams" subtitle="This league needs at least two teams with rosters." />
      ) : (
        <VetoBuilder leagueId={leagueId} lens={lens} pool={pool} />
      )}
    </section>
  );
}
