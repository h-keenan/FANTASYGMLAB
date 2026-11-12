"use client";

import { useCallback, useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Select } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { SimPlayerBrowser } from "@/components/SimGamePlayers";
import { SimPlayerLine, SimSheet, SimStat, SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { api } from "@/lib/api";
import {
  simAssignSlot,
  simClaimPayload,
  simFmtPts,
  simLineupPayload,
  simMatchupLine,
  simNeedsDrop,
  simPositionsFor,
  simSlotAccepts,
  simSlotCandidates,
  simSlotLabels,
  simWarningText,
  type SimGamePlayer,
  type SimLineupResponse,
  type SimSlot,
  type SimWaiverClaim,
} from "@/lib/simGame";

/** Lineup, bench and this week's matchup. Every change saves at once (PUT /lineup). */
export function SimTeamTab({ ctx, onTrade }: { ctx: SimCtx; onTrade: () => void }) {
  const { gameId, game, call } = ctx;
  const [lineup, setLineup] = useState<SimLineupResponse | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [pickSlot, setPickSlot] = useState<number | null>(null);
  const [cutting, setCutting] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);

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
      await refreshGame();
    }
  }

  async function cut(player: SimGamePlayer) {
    setCutting(null);
    const body = await call(() => api.cutSimPlayer(gameId, player.id));
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
  const warnings = lineup.warnings ?? [];
  const nameById = Object.fromEntries([...slots.map((s) => s.player), ...bench].filter(Boolean).map((p) => [p!.id, p!.name]));
  const candidates = pickSlot != null ? simSlotCandidates(slots[pickSlot].slot, slots, bench) : [];

  return (
    <div className="flex flex-col gap-3">
      {week ? (
        <AccentCard accent={week.bye ? "var(--color-warning)" : "var(--color-danger)"} as="section">
          <p className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            Week {week.week} matchup
          </p>
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 flex-col">
              <span className="text-sm font-bold break-words">You</span>
              <span className="text-lg font-extrabold" data-testid="your-projection">{simFmtPts(week.your_projection)}</span>
            </div>
            <span className="text-xs font-bold" style={{ color: "var(--color-text-muted)" }}>vs</span>
            <div className="flex min-w-0 flex-col items-end text-right">
              <span className="text-sm font-bold break-words">{week.opponent?.name ?? "Bye week"}</span>
              <span className="text-lg font-extrabold">{week.opponent ? simFmtPts(week.opponent_projection) : "-"}</span>
            </div>
          </div>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{simMatchupLine(week)}</p>
        </AccentCard>
      ) : null}

      {overLimit ? (
        <AccentCard accent="var(--color-danger)" compact as="div">
          <p className="text-sm font-bold" role="alert">
            Roster over the limit: cut {game.pending?.cuts_needed} player{game.pending?.cuts_needed === 1 ? "" : "s"} from your bench before you advance.
          </p>
        </AccentCard>
      ) : null}

      {warnings.length > 0 ? (
        <AccentCard accent="var(--color-warning)" compact as="div">
          <ul className="flex flex-col gap-1" aria-label="Lineup warnings">
            {warnings.map((w, i) => (
              <li key={i} className="text-xs">{simWarningText(w, w.player_id ? nameById[w.player_id] : undefined)}</li>
            ))}
          </ul>
        </AccentCard>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
      <section className="flex flex-col gap-1" aria-label="Starting lineup">
        <SectionHeading
          action={
            <Button size="sm" variant="secondary" loading={saving} onClick={auto}>
              Auto-set
            </Button>
          }
          note={`Projected ${simFmtPts(lineup.projected_total)} points`}
        >
          Lineup
        </SectionHeading>
        {slots.map((slot, index) => (
          <div key={`${slot.slot}-${index}`} className="flex items-center gap-2" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
            <span className="w-12 shrink-0">
              <PositionBadge position={slot.slot} label={labels[index]} />
            </span>
            {slot.player ? (
              <div className="flex-1 min-w-0">
                <SimPlayerLine
                  player={slot.player}
                  onOpen={ctx.openPlayer}
                  trailing={
                    <>
                      <SimStat label="Proj" value={simFmtPts(slot.player.projection)} />
                      <Button size="sm" variant="secondary" aria-label={`Change ${labels[index]}`} onClick={() => setPickSlot(index)}>
                        Change
                      </Button>
                    </>
                  }
                />
              </div>
            ) : (
              <div className="flex flex-1 items-center justify-between gap-2 py-2">
                <span className="text-sm" style={{ color: "var(--color-warning)" }}>Empty slot</span>
                <Button size="sm" onClick={() => setPickSlot(index)} aria-label={`Fill ${labels[index]}`}>
                  Fill
                </Button>
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="flex flex-col gap-1" aria-label="Bench">
        <SectionHeading note={`${lineup.roster_size ?? 0} of ${lineup.roster_limit ?? 16} roster spots`}>Bench</SectionHeading>
        {bench.length === 0 ? (
          <EmptyState title="Empty bench" subtitle="Add free agents from the Players tab." />
        ) : (
          bench.map((player) => (
            <SimPlayerLine
              key={player.id}
              player={player}
              muted
              onOpen={ctx.openPlayer}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" onClick={() => cut(player)}>Cut {player.name.split(" ").slice(-1)[0]}</Button>
                    <Button size="sm" variant="ghost" onClick={() => setCutting(null)}>Keep</Button>
                  </>
                ) : (
                  <>
                    <SimStat label="Proj" value={simFmtPts(player.projection)} />
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
      </section>
      </div>

      {pickSlot != null ? (
        <SimSheet title={`Choose a ${labels[pickSlot]}`} onClose={() => setPickSlot(null)}>
          <p className="text-lg font-extrabold pr-10">Choose your {labels[pickSlot]}</p>
          <div className="flex flex-col pt-2">
            {candidates.length === 0 ? (
              <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No one on your roster fits this slot.</p>
            ) : (
              candidates.map(({ player, from }) => (
                <SimPlayerLine
                  key={player.id}
                  player={player}
                  selected={slots[pickSlot].player?.id === player.id}
                  extra={from === "slot" ? <SimToneBadge label="Starting elsewhere: swaps" tone="muted" /> : undefined}
                  trailing={
                    <>
                      <SimStat label="Proj" value={simFmtPts(player.projection)} />
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
function ClaimSheet({
  ctx,
  player,
  roster,
  onClose,
  onClaimed,
}: {
  ctx: SimCtx;
  player: SimGamePlayer;
  roster: SimGamePlayer[];
  onClose: () => void;
  onClaimed: (claims: SimWaiverClaim[]) => void;
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
    const body = await ctx.call(() => api.claimSimWaiver(ctx.gameId, payload));
    setBusy(false);
    if (body) {
      ctx.notify(`Claim queued for ${player.name}. It resolves when you advance the week.`, "success");
      onClaimed(body.claims ?? []);
      await ctx.reloadGame();
      onClose();
    }
  }

  return (
    <SimSheet title={`Claim ${player.name}`} onClose={onClose}>
      <p className="text-lg font-extrabold pr-10">Claim {player.name}</p>
      <p className="text-xs pb-2" style={{ color: "var(--color-text-muted)" }}>
        Claims resolve when you advance, worst record first. Another team may get him first.
      </p>
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {mustDrop ? "Drop (your roster is full)" : "Drop (optional)"}
          <Select aria-label="Player to drop" value={dropId} onChange={(event) => setDropId(event.target.value)}>
            <option value="">{mustDrop ? "Choose a player to drop" : "No drop"}</option>
            {roster.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} ({p.pos}) {simFmtPts(p.projection)}
              </option>
            ))}
          </Select>
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
    const body = await call(() => api.cancelSimWaiver(gameId, claim.id));
    if (body) {
      setClaims(body.claims ?? []);
      await ctx.reloadGame();
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
          { label: "All players", value: "all" },
          { label: `Waivers${claims.length ? ` ${claims.length}` : ""}`, value: "waivers" },
        ]}
        active={mode}
        onSelect={(value) => setMode(value as "all" | "waivers")}
      />
      {mode === "waivers" && claims.length > 0 ? (
        <section className="flex flex-col gap-2" aria-label="Queued claims">
          <SectionHeading note="Resolve at Advance, worst record first.">Queued claims</SectionHeading>
          {claims.map((claim) => (
            <AccentCard key={claim.id} accent="var(--color-accent)" compact as="div">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0 text-sm">
                  <strong>{claim.add.name}</strong>
                  {claim.drop ? <span style={{ color: "var(--color-text-muted)" }}> for {claim.drop.name}</span> : null}
                  {claim.start_slot ? <span style={{ color: "var(--color-text-muted)" }}> · starts at {claim.start_slot}</span> : null}
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
        positions={simPositionsFor(game.settings.slots)}
        onOpen={ctx.openPlayer}
        actions={actions}
        refreshKey={ctx.tick}
      />
      {claiming ? (
        <ClaimSheet ctx={ctx} player={claiming} roster={roster} onClose={() => setClaiming(null)} onClaimed={setClaims} />
      ) : null}
    </div>
  );
}
