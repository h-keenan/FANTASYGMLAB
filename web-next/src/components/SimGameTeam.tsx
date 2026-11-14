"use client";

import { useCallback, useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Select } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PositionBadge } from "@/components/PositionBadge";
import { SimGlyph } from "@/components/SimGlyph";
import { SimPlayerBrowser } from "@/components/SimGamePlayers";
import { SimPickLine, useSimPicks } from "@/components/SimGameDynastyParts";
import { SimReserveButton, SimReserveGroups, SimReserveSheet } from "@/components/SimGameReserves";
import { SimFold, SimIconButton, SimPlayerChip, SimRosterLine, SimSectionTitle, SimSheet, SimTeamLink, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SkeletonCard } from "@/components/Skeleton";
import { api } from "@/lib/api";
import {
  simAssignSlot,
  simBenchOffersReserveMove,
  simBenchSwapTargets,
  simOptimisticClaim,
  simWithout,
  simFmtPts,
  simProjText,
  simClaimPayload,
  simLineupPayload,
  simMatchupLine,
  simMatchupTone,
  simNeedsDrop,
  simPicksOf,
  simPicksSummaryLine,
  simPickGroups,
  simFilterPositionsFor,
  simReservesOn,
  simSlotAccepts,
  simSlotCandidates,
  simSlotLabels,
  simWarningText,
  type SimGamePlayer,
  type SimLineupResponse,
  type SimPickAsset,
  type SimSlot,
  type SimWaiverClaim,
  simLimitBlocks,
  simOverLimitNote,
} from "@/lib/simGame";

/** Lineup, bench and this week's matchup. Every change saves at once (PUT /lineup). */
export function SimTeamTab({ ctx, onTrade }: { ctx: SimCtx; onTrade: () => void }) {
  const { gameId, game, call } = ctx;
  const [lineup, setLineup] = useState<SimLineupResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [pickSlot, setPickSlot] = useState<number | null>(null);
  const [swapIn, setSwapIn] = useState<SimGamePlayer | null>(null);
  const [cutting, setCutting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [moving, setMoving] = useState<SimGamePlayer | null>(null);
  const picks = useSimPicks(ctx);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLineup(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) {
          setState("error");
          return;
        }
        setLineup(body);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  const refreshGame = useCallback(async () => {
    await ctx.reloadGame();
  }, [ctx]);

  async function save(slots: NonNullable<SimLineupResponse["slots"]>, bench: SimGamePlayer[]) {
    const previous = lineup;
    setLineup((l) => (l ? { ...l, slots, bench } : l));
    setSaving(true);
    const body = await call(() => api.putSimLineup(gameId, simLineupPayload(slots)));
    setSaving(false);
    if (body) {
      setLineup(body);
      ctx.bump();
      await refreshGame();
    } else {
      setLineup(previous);
    }
  }

  async function auto() {
    setSaving(true);
    const body = await call(() => api.autoSimLineup(gameId));
    setSaving(false);
    if (body) {
      setLineup(body);
      ctx.bump();
      await refreshGame();
    }
  }

  async function cut(player: SimGamePlayer) {
    setCutting(null);
    const body = await call(() => api.cutSimPlayer(gameId, player.id));
    if (!body) {
      // The server may have finished the cut even though this call reported a failure (lost response, retry):
      // show what the server now holds instead of leaving a stale roster that needs a page refresh.
      ctx.bump();
      await refreshGame();
      return;
    }
    if (body) {
      ctx.notify(`Cut ${player.name}. He is back in the free-agent pool.`, "success");
      ctx.bump();
      await refreshGame();
    }
  }

  if (state === "loading") {
    return (
      <div className="flex flex-col gap-3" aria-busy="true">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={6} />
      </div>
    );
  }
  if (state === "error" || !lineup?.slots) {
    return <EmptyState title="Could not load your lineup" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setState("loading"); setAttempt((n) => n + 1); }} />;
  }

  const slots = lineup.slots;
  const bench = lineup.bench ?? [];
  const labels = simSlotLabels(slots);
  const week = game.this_week;
  const overLimit = (game.pending?.cuts_needed ?? 0) > 0;
  const limitBlocks = simLimitBlocks(game.pending);
  const warnings = lineup.warnings ?? [];
  const playerById = Object.fromEntries([...slots.map((s) => s.player), ...bench].filter(Boolean).map((p) => [p!.id, p!]));
  const candidates = pickSlot != null ? simSlotCandidates(slots[pickSlot].slot, slots, bench) : [];
  const reservesOn = simReservesOn(game.settings, lineup.reserves);
  const reserveState = { reserves: lineup.reserves, rosterSize: lineup.roster_size, rosterLimit: lineup.roster_limit };
  const myPicks = simPicksOf(picks, game.you?.team_id);

  return (
    <div className="flex flex-col gap-3">
      {week ? (
        <AccentCard accent={simToneColor(simMatchupTone(week))} compact as="section">
          <div className="flex flex-wrap items-center justify-between gap-x-2 gap-y-1">
            <span className="flex min-w-0 flex-1 basis-40 items-center gap-2">
              <ReviewGlyphChip glyph="game" tone={simMatchupTone(week)} size={24} />
              <span className="text-xs uppercase font-extrabold shrink-0" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>Week {week.week}</span>
              {week.opponent ? <SimTeamLink teamId={week.opponent.team_id} name={week.opponent.name} size={24} /> : <span className="text-sm font-bold">Bye week</span>}
            </span>
            <span className="flex shrink-0 items-baseline gap-2 text-sm font-extrabold tabular-nums">
              <span data-testid="your-projection" style={{ color: week.opponent && week.your_projection >= week.opponent_projection ? "var(--color-success)" : undefined }}>{simFmtPts(week.your_projection)}</span>
              {week.opponent ? <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>vs</span> : null}
              {week.opponent ? <span style={{ color: week.opponent_projection > week.your_projection ? "var(--color-danger)" : undefined }}>{simFmtPts(week.opponent_projection)}</span> : null}
            </span>
          </div>
          <p className="text-xs font-semibold" style={{ color: simToneColor(simMatchupTone(week)) }}>{simMatchupLine(week)} The full head-to-head is on Home.</p>
        </AccentCard>
      ) : null}

      {overLimit ? (
        <AccentCard accent={limitBlocks ? "var(--color-danger)" : "var(--color-warning)"} compact as="div">
          <div className="flex items-start gap-2">
            <ReviewGlyphChip glyph="injury" tone={limitBlocks ? "danger" : "warning"} size={24} />
            <p className={limitBlocks ? "text-sm font-bold flex-1 min-w-0" : "text-xs font-bold flex-1 min-w-0"} role={limitBlocks ? "alert" : "status"} data-testid="over-limit-note">
              {limitBlocks
                ? `Roster over the limit: cut ${game.pending?.cuts_needed} player${game.pending?.cuts_needed === 1 ? "" : "s"} from your bench before you advance.`
                : simOverLimitNote(game.pending?.cuts_needed ?? 0)}
            </p>
          </div>
        </AccentCard>
      ) : null}

      {warnings.length > 0 ? (
        <AccentCard accent="var(--color-warning)" compact as="div">
          <ul className="flex flex-col gap-1" aria-label="Lineup warnings">
            {warnings.map((w, i) => (
              <li key={i} className="flex flex-col gap-1">
                {w.player_id && playerById[w.player_id] ? <SimPlayerChip player={playerById[w.player_id]} /> : null}
                <span className="flex items-start gap-2 text-xs">
                  <ReviewGlyphChip glyph="lineup" tone="warning" size={20} />
                  <span className="flex-1 min-w-0" style={{ color: "var(--color-warning)" }}>{simWarningText(w, w.player_id ? playerById[w.player_id]?.name : undefined)}</span>
                </span>
              </li>
            ))}
          </ul>
        </AccentCard>
      ) : null}

      <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-2 lg:items-start">
      <section className="flex min-w-0 flex-col gap-1" aria-label="Starting lineup">
        <SimSectionTitle
          glyph="team"
          tone="accent"
          action={
            <Button size="sm" variant="secondary" loading={saving} disabled={lineup.locked} onClick={auto} className="rounded-full">
              <SimGlyph name="spark" size={14} />
              <span className="ml-1.5">Auto-set</span>
            </Button>
          }
          note={`Projected ${simFmtPts(lineup.projected_total)} points`}
        >
          Lineup
        </SimSectionTitle>
        {slots.map((slot, index) => (
          <LineupRow key={`${slot.slot}-${index}`} week={game.week} slotLabel={labels[index]} slot={slot.slot} player={slot.player} locked={lineup.locked} onOpen={ctx.openPlayer} onPick={() => setPickSlot(index)} onMove={reservesOn && slot.player?.status === "out" ? setMoving : undefined} />
        ))}
      </section>

      <section className="flex min-w-0 flex-col gap-1" aria-label="Bench">
        <SimSectionTitle glyph="bye" tone="muted" note={`${lineup.roster_size ?? 0} of ${lineup.roster_limit ?? 16} roster spots`}>Bench</SimSectionTitle>
        {bench.length === 0 ? (
          <EmptyState title="Empty bench" subtitle="Add free agents from the Players tab." />
        ) : (
          bench.map((player) => (
            <SimRosterLine
              key={player.id}
              player={player}
              week={game.week}
              onOpen={ctx.openPlayer}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" onClick={() => cut(player)}>Cut {player.name.split(" ").slice(-1)[0]}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setCutting(null)}>Keep</Button>
                  </>
                ) : (
                  <>
                    {reservesOn && simBenchOffersReserveMove(player, reserveState) ? <SimReserveButton player={player} onOpen={setMoving} /> : null}
                    <SimIconButton disabled={lineup.locked} label={`Swap ${player.name} into your lineup`} onClick={() => setSwapIn(player)}>
                      <SimGlyph name="trade" size={16} />
                    </SimIconButton>
                    <Button size="sm" variant={overLimit ? "dangerOutline" : "ghost"} aria-label={`Cut ${player.name}`} onClick={() => setCutting(player.id)}>
                      Cut
                    </Button>
                  </>
                )
              }
            />
          ))
        )}
        {game.can_trade ? (
          <Button size="sm" variant="ghost" onClick={onTrade}>Shop a trade</Button>
        ) : null}
        {reservesOn ? (
          <SimReserveGroups ir={lineup.ir ?? []} taxi={lineup.taxi ?? []} state={reserveState} onOpen={setMoving} openPlayer={ctx.openPlayer} cutting={cutting} onAskCut={setCutting} onCut={cut} />
        ) : null}
        {game.settings.mode === "dynasty" && picks ? <SimYourPicks picks={myPicks} draftYear={picks.draft_year} /> : null}
      </section>
      </div>

      {moving ? (
        <SimReserveSheet
          ctx={ctx}
          player={moving}
          state={reserveState}
          taxi={lineup.taxi ?? []}
          onClose={() => setMoving(null)}
          onMoved={(body, player, to) => {
            setMoving(null);
            setLineup(body);
            ctx.notify(`${player.name} ${to === "ir" ? "is on IR" : to === "taxi" ? "is on the taxi squad" : "is back on your roster"}.`, "success");
            ctx.bump();
            void refreshGame();
          }}
        />
      ) : null}

      {swapIn ? (
        <SimSheet title={`Swap ${swapIn.name} in`} onClose={() => setSwapIn(null)}>
          <p className="text-lg font-extrabold pr-10">Swap {swapIn.name} in</p>
          <div className="flex flex-col pt-2" data-testid="bench-swap-targets">
            {simBenchSwapTargets(swapIn, slots, labels).length === 0 ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No lineup slot fits this position.</p>
            ) : (
              simBenchSwapTargets(swapIn, slots, labels).map((target) => (
                <div key={target.index} className="flex items-center gap-2" style={{ minHeight: 52, borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
                  <span className="flex justify-center" style={{ width: "3.25rem" }}><PositionBadge position={slots[target.index].slot} label={target.label} /></span>
                  <span className="min-w-0 flex-1 truncate text-sm font-semibold">{target.current ? `Replaces ${target.current.name}` : "Empty slot"}</span>
                  <Button
                    size="sm"
                    onClick={() => {
                      const next = simAssignSlot({ slots, bench }, target.index, swapIn);
                      setSwapIn(null);
                      void save(next.slots, next.bench);
                    }}
                  >
                    Swap
                  </Button>
                </div>
              ))
            )}
          </div>
        </SimSheet>
      ) : null}

      {pickSlot != null ? (
        <SimSheet title={`Choose a ${labels[pickSlot]}`} onClose={() => setPickSlot(null)}>
          <p className="text-lg font-extrabold pr-10">Choose your {labels[pickSlot]}</p>
          <div className="flex flex-col pt-2">
            {candidates.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No one on your roster fits this slot.</p>
            ) : (
              candidates.map(({ player, from }) => (
                <SimRosterLine
                  key={player.id}
                  player={player}
                  week={game.week}
                  extra={from === "slot" ? <SimToneBadge label="Starting elsewhere: swaps" tone="muted" /> : undefined}
                  trailing={
                    <>
                      <Button
                        size="sm"
                        disabled={slots[pickSlot].player?.id === player.id}
                        onClick={() => {
                          const next = simAssignSlot({ slots, bench }, pickSlot, player);
                          setPickSlot(null);
                          void save(next.slots, next.bench);
                        }}
                      >
                        Start
                      </Button>
                    </>
                  }
                />
              ))
            )}
            {slots[pickSlot].player ? (
              <Button
                variant="secondary"
                className="mt-3"
                onClick={() => {
                  const next = simAssignSlot({ slots, bench }, pickSlot, null);
                  setPickSlot(null);
                  void save(next.slots, next.bench);
                }}
              >
                Move to bench
              </Button>
            ) : null}
          </div>
        </SimSheet>
      ) : null}
    </div>
  );
}

/** Add (with an optional drop and start slot) as a waiver claim. */
export function ClaimSheet({
  ctx,
  player,
  roster,
  onClose,
  onClaimed,
  onQueued,
  onFailed,
}: {
  ctx: SimCtx;
  player: SimGamePlayer;
  roster: SimGamePlayer[];
  onClose: () => void;
  onClaimed: (claims: SimWaiverClaim[]) => void;
  /** Optimistic: the claim is shown (and the sheet closes) before the server answers; `onFailed` takes it back. */
  onQueued?: (claim: SimWaiverClaim) => void;
  onFailed?: (addId: string) => void;
}) {
  const { game } = ctx;
  const [dropId, setDropId] = useState("");
  const [slot, setSlot] = useState<SimSlot | "">("");
  const [busy, setBusy] = useState(false);
  const mustDrop = simNeedsDrop(roster.length, game.settings.roster_limit);
  const eligibleSlots = Array.from(new Set(game.settings.slots)).filter((s) => simSlotAccepts(s, player.pos));
  const draft = { add: player, drop: roster.find((p) => p.id === dropId) ?? null, startSlot: (slot || null) as SimSlot | null };
  const payload = simClaimPayload(draft);

  async function submit() {
    if (!payload) return;
    setBusy(true);
    onQueued?.(simOptimisticClaim(draft.add, draft.drop, draft.startSlot));
    if (onQueued) onClose();
    const body = await ctx.call(() => api.claimSimWaiver(ctx.gameId, payload));
    setBusy(false);
    if (body) {
      ctx.notify(`Claim queued for ${player.name}. It resolves when you advance the week.`, "success");
      onClaimed(body.claims ?? []);
      void ctx.reloadGame();
      onClose();
    } else {
      onFailed?.(player.id);
    }
  }

  return (
    <SimSheet title={`Claim ${player.name}`} onClose={onClose}>
      <p className="text-lg font-extrabold pr-10">Claim {player.name}</p>
      <SimPlayerChip player={player} size={40} />
      <p className="text-xs pb-2" style={{ color: "var(--color-text-muted)" }}>
        Claims resolve when you advance, before games are scored, worst record first. A claimed player can start that same week. Another team may get him first.
      </p>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {mustDrop ? "Drop (your roster is full)" : "Drop (optional)"}
          <Select aria-label="Player to drop" value={dropId} onChange={(event) => setDropId(event.target.value)}>
            <option value="">{mustDrop ? "Choose a player to drop" : "No drop"}</option>
            {roster.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.pos}) {simProjText(p)}
              </option>
            ))}
          </Select>
          {roster.find((p) => p.id === dropId) ? (
            <span className="flex items-center gap-2 pt-1" data-testid="claim-drop-preview">
              <span className="shrink-0 text-xs font-bold" style={{ color: "var(--color-danger)" }}>Dropping</span>
              <SimPlayerChip player={roster.find((p) => p.id === dropId)!} size={32} />
            </span>
          ) : null}
        </label>
        {eligibleSlots.length > 0 ? (
          <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
            Start him if the claim wins (optional)
            <Select aria-label="Start slot" value={slot} onChange={(event) => setSlot(event.target.value as SimSlot | "")}>
              <option value="">Bench</option>
              {eligibleSlots.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
          </label>
        ) : null}
        <Button loading={busy} disabled={mustDrop && !dropId} onClick={submit}>
          Queue claim
        </Button>
      </div>
    </SimSheet>
  );
}

/** Search every player, or work the waiver wire. */
export function SimPlayersTab({
  ctx,
  claims,
  setClaims,
  onTradeFor,
}: {
  ctx: SimCtx;
  claims: SimWaiverClaim[];
  setClaims: (claims: SimWaiverClaim[]) => void;
  onTradeFor: (player: SimGamePlayer) => void;
}) {
  const { gameId, game, call } = ctx;
  const [mode, setMode] = useState<"all" | "waivers">("all");
  const [roster, setRoster] = useState<SimGamePlayer[]>([]);
  const [claiming, setClaiming] = useState<SimGamePlayer | null>(null);
  const teamId = game.you?.team_id;

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((body) => {
        if (!cancelled) setRoster(body.players ?? []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  async function cancel(claim: SimWaiverClaim) {
    const before = claims;
    setClaims(simWithout(claims, claim.id));
    const body = await call(() => api.cancelSimWaiver(gameId, claim.id));
    if (body) {
      setClaims(body.claims ?? []);
      void ctx.reloadGame();
    } else {
      setClaims(before);
    }
  }

  const queuedIds = new Set(claims.map((c) => c.add.id));
  const actions = (player: SimGamePlayer) => {
    if (player.owner?.type === "free_agent") {
      return queuedIds.has(player.id) ? (
        <SimToneBadge label="Claim queued" tone="accent" />
      ) : (
        <Button size="sm" onClick={() => setClaiming(player)} aria-label={`Add ${player.name}`}>
          Add
        </Button>
      );
    }
    if (player.owner?.type === "ai" && game.can_trade) {
      return (
        <Button size="sm" variant="secondary" onClick={() => onTradeFor(player)} aria-label={`Trade for ${player.name}`}>
          Trade
        </Button>
      );
    }
    return null;
  };

  return (
    <div className="flex flex-col gap-3">
      <PillRow
        ariaLabel="Players view"
        variant="fill"
        options={[
          { label: "All players", value: "all", glyph: "team" },
          { label: `Waivers${claims.length ? ` ${claims.length}` : ""}`, value: "waivers", glyph: "addDrop" },
        ]}
        active={mode}
        onSelect={(value) => setMode(value as "all" | "waivers")}
      />
      {mode === "waivers" && claims.length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Queued claims">
          <SimSectionTitle glyph="waiver" tone="accent" note="Resolve at Advance, worst record first.">Queued claims</SimSectionTitle>
          {claims.map((claim) => (
            <AccentCard key={claim.id} accent="var(--color-success)" compact as="div">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <ReviewGlyphChip glyph="waiver" tone="success" size={24} />
                    <SimPlayerChip player={claim.add} />
                  </div>
                  {claim.drop ? <span className="text-xs font-semibold" style={{ color: "var(--color-danger)" }}>Drops {claim.drop.name} ({claim.drop.pos})</span> : null}
                  {claim.start_slot ? <span className="text-xs font-semibold" style={{ color: "var(--color-success)" }}>Starts at {claim.start_slot}</span> : null}
                </div>
                <Button size="sm" variant="ghost" onClick={() => cancel(claim)}>Cancel</Button>
              </div>
            </AccentCard>
          ))}
        </section>
      ) : null}
      {mode === "waivers" && claims.length === 0 && (game.pending?.claims ?? 0) > 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {game.pending?.claims} claim{game.pending?.claims === 1 ? " is" : "s are"} already queued for this week.
        </p>
      ) : null}
      <SimPlayerBrowser
        key={mode}
        gameId={gameId}
        fixedStatus={mode === "waivers" ? "available" : undefined}
        positions={simFilterPositionsFor(game.settings.slots)}
        week={game.week}
        blockEnabled={(game.settings.block_v ?? 0) >= 1}
        onOpen={ctx.openPlayer}
        actions={actions}
        refreshKey={ctx.tick}
      />
      {claiming ? (
        <ClaimSheet
          ctx={ctx}
          player={claiming}
          roster={roster}
          onClose={() => setClaiming(null)}
          onClaimed={setClaims}
          onQueued={(c) => setClaims([...claims.filter((x) => x.add.id !== c.add.id), c])}
          onFailed={(addId) => setClaims(claims.filter((x) => x.add.id !== addId))}
        />
      ) : null}
    </div>
  );
}

/**
 * One lineup row, one fixed grid for every row: slot badge (fixed width),
 * photo, name + one-line subline (truncated, never wraps), projection (fixed)
 * and a 40px Change / Fill control. The player's own position shows only
 * where the slot does not already say it (FLEX, SUPERFLEX), as a small dot
 * inside the subline, so rows keep identical height at 390px.
 */
function LineupRow({ slotLabel, slot, player, locked, week, onOpen, onPick, onMove }: { slotLabel: string; slot: SimSlot; player: SimGamePlayer | null; locked?: boolean; week?: number | null; onOpen: (p: SimGamePlayer) => void; onPick: () => void; onMove?: (p: SimGamePlayer) => void }) {
  const swap = (
    <SimIconButton disabled={locked} label={player ? `Change ${slotLabel}` : `Fill ${slotLabel}`} primary={!player} onClick={onPick}>
      <SimGlyph name={player ? "trade" : "check"} size={16} />
    </SimIconButton>
  );
  if (player) {
    return (
      <SimRosterLine
        player={player}
        slot={{ slot, label: slotLabel }}
        week={week}
        onOpen={onOpen}
        trailing={
          <>
            {onMove ? <SimReserveButton player={player} onOpen={onMove} /> : null}
            {swap}
          </>
        }
      />
    );
  }
  return (
    <div className="flex items-center gap-2" style={{ minHeight: 52, borderBottom: "var(--border-width-default) solid var(--color-border)" }} data-testid="lineup-row">
      <span className="flex justify-center" style={{ width: "3.25rem" }}><PositionBadge position={slot} label={slotLabel} /></span>
      <span className="min-w-0 flex-1 text-sm" style={{ color: "var(--color-warning)" }}>Empty slot</span>
      {swap}
    </div>
  );
}

/** "Your picks": the shared fold (closed on phones), one summary line, then your picks by year and round. */
export function SimYourPicks({ picks, draftYear }: { picks: SimPickAsset[]; draftYear?: number | null }) {
  const groups = simPickGroups(picks);
  return (
    <SimFold id="team.picks" glyph="league" title="Your picks" summary={<span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simPicksSummaryLine(picks)}</span>} testId="your-picks">
      {groups.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>You hold no draft picks. Trade for some on the Trades tab.</p>
      ) : (
        groups.map((group) => (
          <div key={group.season} className="flex flex-col">
            <p className="pt-1 text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>{group.label}</p>
            {group.rounds.flatMap((r) => r.picks).map((pick) => (
              <SimPickLine key={pick.id} pick={pick} draftYear={draftYear} />
            ))}
          </div>
        ))
      )}
    </SimFold>
  );
}
