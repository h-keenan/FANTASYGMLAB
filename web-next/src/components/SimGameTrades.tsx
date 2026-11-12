"use client";

import { useEffect, useMemo, useReducer, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimPlayerLine, SimSideLabel, SimStat, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard, SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  SIM_TRADE_EMPTY,
  SIM_TRADE_MAX_PER_SIDE,
  simFmtPts,
  simTradable,
  simTradeClosedReason,
  simTradeDecisionLabel,
  simTradeDecisionTone,
  simTradeKey,
  simTradePayload,
  simTradeReady,
  simTradeReducer,
  type SimGamePlayer,
  type SimInboxItem,
  type SimLeagueTeam,
  type SimTradeDraft,
  type SimTradeVerdict,
} from "@/lib/simGame";

function PlayerList({ players }: { players: SimGamePlayer[] }) {
  return (
    <ul className="flex flex-col">
      {players.map((p) => (
        <li key={p.id}>
          <SimPlayerLine player={p} trailing={<SimStat label="Proj" value={simFmtPts(p.projection)} />} />
        </li>
      ))}
    </ul>
  );
}

/** AI-proposed offers: accept or decline. They expire when the week advances. */
function Inbox({ ctx }: { ctx: SimCtx }) {
  const { gameId, call } = ctx;
  const [items, setItems] = useState<SimInboxItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimInbox(gameId)
      .then((body) => {
        if (!cancelled) setItems(body.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick]);

  async function respond(item: SimInboxItem, action: "accept" | "decline") {
    setBusyId(item.id);
    const body = await call(() => api.respondSimInbox(gameId, item.id, action));
    setBusyId(null);
    if (body) {
      setItems(body.items ?? []);
      ctx.notify(action === "accept" && body.executed ? `Trade done with ${item.from.name}.` : `Declined ${item.from.name}'s offer.`, action === "accept" ? "success" : "muted");
      ctx.bump();
      await ctx.reloadGame();
    } else {
      // offer_invalid and friends: refresh the list so the stale card goes away.
      api.getSimInbox(gameId).then((b) => setItems(b.items ?? [])).catch(() => {});
    }
  }

  if (failed) return <EmptyState title="Could not load your inbox" subtitle="Check your connection and try again." />;
  if (!items) return <SkeletonCard lines={4} />;
  if (items.length === 0) {
    return <EmptyState title="No offers right now" subtitle="AI managers send at most a few offers a week. They show up here and expire when you advance." />;
  }
  return (
    <ul className="flex flex-col gap-3" aria-label="Trade offers">
      {items.map((item) => (
        <li key={item.id} className="enter-rise">
          <AccentCard accent="var(--color-premium)" as="div">
            <div className="flex items-center justify-between gap-2">
              <span className="flex min-w-0 items-center gap-2">
                <ReviewGlyphChip glyph="trade" tone="accent" size={28} />
                <span className="text-sm font-bold break-words min-w-0">{item.from.name}</span>
              </span>
              <ToneBadge label={`Expires week ${item.expires_week}`} color="var(--color-warning)" size="xs" />
            </div>
            {item.message ? <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{item.message}</p> : null}
            <div className="grid gap-2 md:grid-cols-2">
              <div>
                <SimSideLabel side="give" />
                <PlayerList players={item.you_give} />
              </div>
              <div>
                <SimSideLabel side="get" />
                <PlayerList players={item.you_get} />
              </div>
            </div>
            <div className="flex gap-2">
              <Button size="sm" loading={busyId === item.id} disabled={!ctx.game.can_trade} onClick={() => respond(item, "accept")}>Accept</Button>
              <Button size="sm" variant="secondary" disabled={busyId === item.id} onClick={() => respond(item, "decline")}>Decline</Button>
            </div>
          </AccentCard>
        </li>
      ))}
    </ul>
  );
}

function VerdictCard({ verdict, onSendCounter, busy }: { verdict: SimTradeVerdict; onSendCounter: () => void; busy: boolean }) {
  const tone = simTradeDecisionTone(verdict.decision);
  return (
    <AccentCard accent={simToneColor(tone)} as="div" className="enter-pop" data-highlighted="">
      <div data-testid="trade-verdict" className="flex flex-col gap-2">
        <div className="flex items-center justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <ReviewGlyphChip glyph="trade" tone={tone} size={28} />
            <p className="text-base font-extrabold">{simTradeDecisionLabel(verdict.decision)}</p>
          </span>
          <SimToneBadge tone={tone} size="sm" label={verdict.decision} />
        </div>
        <p className="text-sm">{verdict.reason}</p>
        {(verdict.chips ?? []).length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {verdict.chips!.map((chip) => (
              <ToneBadge key={chip} label={chip} color="var(--color-text-secondary)" size="xs" />
            ))}
          </div>
        ) : null}
        {verdict.decision === "counter" && verdict.counter ? (
          <div className="flex flex-col gap-1">
            <p className="text-xs font-bold" style={{ color: "var(--color-accent)" }}>Their counter</p>
            <div className="grid gap-2 md:grid-cols-2">
              <div><SimSideLabel side="give" /><PlayerList players={verdict.counter.give} /></div>
              <div><SimSideLabel side="get" /><PlayerList players={verdict.counter.get} /></div>
            </div>
            <Button size="sm" loading={busy} onClick={onSendCounter}>Take their counter</Button>
          </div>
        ) : null}
      </div>
    </AccentCard>
  );
}

/** Build an offer to any AI team, preview the (deterministic) verdict, then send it. */
function Builder({ ctx, seed, onSeedUsed }: { ctx: SimCtx; seed: { partner: string; get: string } | null; onSeedUsed: () => void }) {
  const { gameId, game, call } = ctx;
  const [draft, dispatch] = useReducer(simTradeReducer, SIM_TRADE_EMPTY);
  const [teams, setTeams] = useState<SimLeagueTeam[] | null>(null);
  const [partnerLoaded, setPartnerLoaded] = useState<{ partner: string; players: SimGamePlayer[] } | null>(null);
  const [mine, setMine] = useState<SimGamePlayer[]>([]);
  // The verdict is stored with the offer it answers, so a changed offer
  // never shows the old verdict (no reset effect needed).
  const [verdictFor, setVerdictFor] = useState<{ key: string; verdict: SimTradeVerdict | null } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [changingPartner, setChangingPartner] = useState(false);
  const closed = simTradeClosedReason(game);
  const teamId = game.you?.team_id;

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLeague(gameId)
      .then((body) => {
        if (!cancelled) setTeams((body.teams ?? []).filter((t) => !t.is_you));
      })
      .catch(() => {
        if (!cancelled) setTeams([]);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId]);

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api.getSimGameTeam(gameId, teamId).then((b) => !cancelled && setMine(b.players ?? [])).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  useEffect(() => {
    const partnerId = draft.partner;
    if (!partnerId) return;
    let cancelled = false;
    api.getSimGameTeam(gameId, partnerId).then((b) => !cancelled && setPartnerLoaded({ partner: partnerId, players: b.players ?? [] })).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, draft.partner, ctx.tick]);
  const partnerRoster = partnerLoaded && partnerLoaded.partner === draft.partner ? partnerLoaded.players : [];

  // "Trade for him" from the Players tab: preselect the partner and the player.
  useEffect(() => {
    if (!seed) return;
    dispatch({ type: "partner", teamId: seed.partner });
    dispatch({ type: "toggle", side: "get", id: seed.get });
    onSeedUsed();
  }, [seed, onSeedUsed]);

  const key = simTradeKey(draft);
  const verdict = verdictFor && verdictFor.key === key ? verdictFor.verdict : null;
  // Preview the (deterministic) verdict for the current offer.
  useEffect(() => {
    const payload = simTradePayload(draft);
    if (!payload || closed) return;
    let cancelled = false;
    const id = setTimeout(async () => {
      setPreviewing(true);
      const body = await call(() => api.previewSimTrade(gameId, payload));
      if (!cancelled) {
        setPreviewing(false);
        setVerdictFor({ key, verdict: body?.verdict ?? null });
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(id);
    };
    // The key stands in for the draft contents.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, closed, gameId]);

  async function send(offer: { partner: string; give: string[]; get: string[] }) {
    setSending(true);
    const body = await call(() => api.sendSimTrade(gameId, offer));
    setSending(false);
    if (!body) return;
    if (body.executed) {
      ctx.notify("Trade done. The players are on their new rosters.", "success");
      dispatch({ type: "clear" });
      ctx.bump();
      await ctx.reloadGame();
    } else if (body.verdict) {
      setVerdictFor({ key, verdict: body.verdict });
    }
  }

  const partner = teams?.find((t) => t.team_id === draft.partner) ?? null;
  const ready = simTradeReady(draft);
  const teamOptions = useMemo(() => [...(teams ?? [])].sort((a, b) => a.power_rank - b.power_rank), [teams]);
  // Once a partner is chosen the list collapses to that team, so the offer and verdict stay in reach.
  const visibleTeams = partner && !changingPartner ? teamOptions.filter((t) => t.team_id === partner.team_id) : teamOptions;

  if (closed) {
    return <EmptyState title="Trades are closed" subtitle={closed} />;
  }
  if (!teams) return <SkeletonRows count={4} />;

  return (
    <div className="flex flex-col gap-3">
      <section className="flex flex-col gap-2" aria-label="Trade partner">
        <SectionHeading note="Tap a team to see its roster and how it likes to trade.">Partner</SectionHeading>
        <ul className="flex flex-col gap-2">
          {visibleTeams.map((team) => (
            <li key={team.team_id}>
              <button
                type="button"
                className="w-full text-left"
                aria-pressed={draft.partner === team.team_id}
                onClick={() => {
                  dispatch({ type: "partner", teamId: team.team_id });
                  setChangingPartner(false);
                }}
              >
                <AccentCard accent={draft.partner === team.team_id ? "var(--color-accent)" : "var(--color-border-strong)"} compact as="div">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-bold break-words min-w-0">{team.name}</span>
                    <ToneBadge label={team.persona.label} color="var(--color-accent)" size="xs" />
                  </div>
                  {draft.partner === team.team_id ? (
                    <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{team.persona.blurb}</p>
                  ) : null}
                </AccentCard>
              </button>
            </li>
          ))}
        </ul>
        {partner && !changingPartner ? (
          <Button size="sm" variant="ghost" onClick={() => setChangingPartner(true)}>Change partner</Button>
        ) : null}
      </section>

      {partner ? (
        <>
          <section className="flex flex-col gap-1" aria-label="You give">
            <SectionHeading note={`Up to ${SIM_TRADE_MAX_PER_SIDE}. ${draft.give.length} selected.`}>You give</SectionHeading>
            {mine.filter((p) => simTradable(p.pos)).map((p) => (
              <SimPlayerLine
                key={p.id}
                player={p}
                selected={draft.give.includes(p.id)}
                trailing={
                  <>
                    <SimStat label="Value" value={Math.round(p.value)} />
                    <Button size="sm" variant={draft.give.includes(p.id) ? "primary" : "secondary"} aria-pressed={draft.give.includes(p.id)} aria-label={`Give ${p.name}`} onClick={() => dispatch({ type: "toggle", side: "give", id: p.id })}>
                      {draft.give.includes(p.id) ? "Giving" : "Give"}
                    </Button>
                  </>
                }
              />
            ))}
          </section>
          <section className="flex flex-col gap-1" aria-label="You get">
            <SectionHeading note={`${partner.name}'s roster. ${draft.get.length} selected.`}>You get</SectionHeading>
            {partnerRoster.filter((p) => simTradable(p.pos)).map((p) => (
              <SimPlayerLine
                key={p.id}
                player={p}
                selected={draft.get.includes(p.id)}
                trailing={
                  <>
                    <SimStat label="Value" value={Math.round(p.value)} />
                    <Button size="sm" variant={draft.get.includes(p.id) ? "primary" : "secondary"} aria-pressed={draft.get.includes(p.id)} aria-label={`Get ${p.name}`} onClick={() => dispatch({ type: "toggle", side: "get", id: p.id })}>
                      {draft.get.includes(p.id) ? "Getting" : "Get"}
                    </Button>
                  </>
                }
              />
            ))}
          </section>
        </>
      ) : null}

      {ready ? (
        <section className="flex flex-col gap-2" aria-label="Verdict" aria-live="polite">
          {previewing && !verdict ? <SkeletonCard lines={3} /> : null}
          {verdict ? (
            <>
              <VerdictCard
                key={`${key}-${verdict.decision}`}
                verdict={verdict}
                busy={sending}
                onSendCounter={() => {
                  if (!verdict.counter || !draft.partner) return;
                  void send({ partner: draft.partner, give: verdict.counter.give.map((p) => p.id), get: verdict.counter.get.map((p) => p.id) });
                }}
              />
              {verdict.decision === "accept" ? (
                <Button loading={sending} onClick={() => { const payload = simTradePayload(draft); if (payload) void send(payload); }}>
                  Send offer
                </Button>
              ) : null}
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  );
}

/** Trades tab: your inbox of AI offers and the offer builder. */
export function SimTradesTab({
  ctx,
  seed,
  onSeedUsed,
}: {
  ctx: SimCtx;
  seed: { partner: string; get: string } | null;
  onSeedUsed: () => void;
}) {
  const [mode, setMode] = useState<"inbox" | "build">(seed ? "build" : "inbox");
  const offers = ctx.game.pending?.inbox ?? 0;
  const [prevSeed, setPrevSeed] = useState(seed);
  if (seed && seed !== prevSeed) {
    setPrevSeed(seed);
    setMode("build");
  }
  return (
    <div className="flex flex-col gap-3">
      <PillRow
        ariaLabel="Trades view"
        variant="fill"
        options={[
          { label: `Inbox${offers ? ` ${offers}` : ""}`, value: "inbox" },
          { label: "Make an offer", value: "build" },
        ]}
        active={mode}
        onSelect={(value) => setMode(value as "inbox" | "build")}
      />
      {!ctx.game.can_trade && mode === "inbox" ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{simTradeClosedReason(ctx.game)}</p> : null}
      {mode === "inbox" ? <Inbox ctx={ctx} /> : <Builder ctx={ctx} seed={seed} onSeedUsed={onSeedUsed} />}
    </div>
  );
}

export type { SimTradeDraft };
