"use client";

import { useContext, useEffect, useMemo, useReducer, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimCrest } from "@/components/SimCrest";
import { SimGlyph } from "@/components/SimGlyph";
import { SimPlayerChip, SimSideLabel, SimStat, SimTeamOpenContext, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard, SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simGroupByPosition, simSideSummary, simTradeFit } from "@/lib/simLayout";
import { simGroupsToSheetItems } from "@/lib/simTradeSheet";
import { selectedItems } from "@/lib/tradeSheetPicker";
import { TradePickerSheet, TradeSideSummary } from "@/components/TradePickerSheet";
import {
  SIM_TRADE_EMPTY,
  SIM_TRADE_MAX_PER_SIDE,
  simFmtPts,
  simHeadshotId,
  simPositionsFor,
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

/** "Scout" button for the partner list: opens the team's scouting sheet without picking it as the partner. */
function SimTeamScout({ teamId, name }: { teamId: string; name: string }) {
  const open = useContext(SimTeamOpenContext);
  if (!open) return null;
  return (
    <button
      type="button"
      className="tap-link inline-flex shrink-0 items-center gap-1 text-xs font-bold"
      style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
      aria-label={`Scout ${name}`}
      onClick={() => open(teamId)}
    >
      <SimGlyph name="team" size={13} />
      Scout
    </button>
  );
}

function PlayerList({ players }: { players: SimGamePlayer[] }) {
  return (
    <ul className="flex flex-col">
      {players.map((p) => (
        <li key={p.id}>
          <div className="flex items-center justify-between gap-2 py-1">
            <SimPlayerChip player={p} size={28} quick className="min-w-0 flex-1" />
            <SimStat label="Proj" value={simFmtPts(p.projection)} />
          </div>
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
    <ul className="flex flex-col gap-2" aria-label="Trade offers">
      {items.map((item, index) => (
        <OfferCard key={item.id} item={item} defaultOpen={index === 0} busy={busyId === item.id} canTrade={Boolean(ctx.game.can_trade)} onRespond={respond} />
      ))}
    </ul>
  );
}

/** One AI offer as a compact card: who, what moves and when it expires; tap to expand the players and the Accept / Decline buttons. */
function OfferCard({ item, defaultOpen, busy, canTrade, onRespond }: { item: SimInboxItem; defaultOpen: boolean; busy: boolean; canTrade: boolean; onRespond: (item: SimInboxItem, action: "accept" | "decline") => void }) {
  const [open, setOpen] = useState(defaultOpen);
  const give = simSideSummary(item.you_give);
  const get = simSideSummary(item.you_get);
  const names = (list: SimGamePlayer[]) => list.map((p) => p.name.split(" ").slice(-1)[0]).join(", ");
  return (
    <li className="enter-rise">
      <AccentCard accent="var(--color-premium)" compact as="div">
        <button
          type="button"
          className="flex w-full flex-col gap-1 text-left"
          style={{ minHeight: "var(--touch-target-min)" }}
          aria-expanded={open}
          aria-label={`Offer from ${item.from.name}`}
          onClick={() => setOpen((v) => !v)}
        >
          <span className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2">
              <SimCrest name={item.from.name} size={24} />
              <span className="min-w-0 truncate text-sm font-bold">{item.from.name}</span>
            </span>
            <span className="flex shrink-0 items-center gap-2">
              <ToneBadge label={`Wk ${item.expires_week}`} color="var(--color-warning)" size="xs" />
              <span aria-hidden="true" className="text-xs" style={{ color: "var(--color-text-muted)" }}>{open ? "\u2212" : "+"}</span>
            </span>
          </span>
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            <span className="font-bold" style={{ color: "var(--color-danger)" }}>Give</span> {names(item.you_give)} ({give.value})
            {" · "}
            <span className="font-bold" style={{ color: "var(--color-success)" }}>Get</span> {names(item.you_get)} ({get.value})
          </span>
        </button>
        {open ? (
          <div className="flex flex-col gap-2">
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
              <Button size="sm" loading={busy} disabled={!canTrade} onClick={() => onRespond(item, "accept")}>Accept</Button>
              <Button size="sm" variant="secondary" disabled={busy} onClick={() => onRespond(item, "decline")}>Decline</Button>
            </div>
          </div>
        ) : null}
      </AccentCard>
    </li>
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
  const [sheetSide, setSheetSide] = useState<"give" | "get" | null>(null);
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
    if (seed.get) dispatch({ type: "toggle", side: "get", id: seed.get });
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

  if (closed) {
    return <EmptyState title="Trades are closed" subtitle={closed} />;
  }
  if (!teams) return <SkeletonRows count={4} />;

  const giveSelected = mine.filter((p) => draft.give.includes(p.id));
  const getSelected = partnerRoster.filter((p) => draft.get.includes(p.id));
  const fit = simTradeFit(mine.length, game.settings.roster_limit, giveSelected.length, getSelected.length);
  const sheetPool = sheetSide === "give" ? mine : partnerRoster;
  const sheetItems = sheetSide ? simGroupsToSheetItems(simGroupByPosition(sheetPool.filter((p) => simTradable(p.pos)), simPositionsFor(game.settings.slots)), simHeadshotId) : [];

  return (
    <div className="flex flex-col gap-3">
      <section className="flex flex-col gap-2" aria-label="Trade partner">
        <SectionHeading note={partner ? undefined : "Pick a team to trade with."}>Partner</SectionHeading>
        <ul className="-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1" aria-label="Teams">
          {teamOptions.map((team) => {
            const active = draft.partner === team.team_id;
            return (
              <li key={team.team_id} className="shrink-0 snap-start">
                <button
                  type="button"
                  className="flex w-20 flex-col items-center gap-1 p-1.5 text-center"
                  style={{
                    borderRadius: "var(--radius-card, 12px)",
                    border: `var(--border-width-default) solid ${active ? "var(--color-accent)" : "var(--color-border)"}`,
                    background: active ? "var(--color-accent-soft)" : undefined,
                  }}
                  aria-pressed={active}
                  aria-label={`Trade with ${team.name}`}
                  onClick={() => dispatch({ type: "partner", teamId: team.team_id })}
                >
                  <SimCrest name={team.name} size={32} />
                  <span className="line-clamp-2 text-[0.6875rem] font-bold leading-tight">{team.name}</span>
                </button>
              </li>
            );
          })}
        </ul>
        {partner ? (
          <div className="flex items-center justify-between gap-2">
            <span className="flex min-w-0 items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
              <ToneBadge label={partner.persona.label} color="var(--color-accent)" size="xs" />
              <span className="min-w-0 truncate">{partner.persona.blurb}</span>
            </span>
            <SimTeamScout teamId={partner.team_id} name={partner.name} />
          </div>
        ) : null}
      </section>

      {partner ? (
        <>
          <section className="grid grid-cols-2 gap-2" aria-label="Offer">
            <TradeSideSummary testId="trade-side-give" label="You send" tone="danger" items={simGroupsToSheetItems(simGroupByPosition(giveSelected, simPositionsFor(game.settings.slots)), simHeadshotId)} onOpen={() => setSheetSide("give")} onRemove={(key) => dispatch({ type: "toggle", side: "give", id: key.slice(key.indexOf(":") + 1) })} hint="Add from your roster" />
            <TradeSideSummary testId="trade-side-get" label="You receive" tone="success" items={simGroupsToSheetItems(simGroupByPosition(getSelected, simPositionsFor(game.settings.slots)), simHeadshotId)} onOpen={() => setSheetSide("get")} onRemove={(key) => dispatch({ type: "toggle", side: "get", id: key.slice(key.indexOf(":") + 1) })} hint={`Add from ${partner.name}`} />
          </section>
          <p className="text-xs" style={{ color: fit.over ? "var(--color-danger)" : "var(--color-text-muted)" }} data-testid="trade-fit">
            Your roster after: {fit.after}/{game.settings.roster_limit}
            {fit.over ? ` (cut ${fit.over} after the trade)` : fit.room ? ` (${fit.room} open)` : ""}
          </p>
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

      {partner && sheetSide ? (
        <TradePickerSheet
          key={sheetSide}
          title={sheetSide === "give" ? "You send" : "You receive"}
          subtitle={sheetSide === "give" ? "From your roster" : `From ${partner.name}`}
          tone={sheetSide === "give" ? "danger" : "success"}
          items={sheetItems}
          initialSelected={(sheetSide === "give" ? draft.give : draft.get).map((id) => `player:${id}`)}
          max={SIM_TRADE_MAX_PER_SIDE}
          onApply={(keys) => {
            dispatch({ type: "set", side: sheetSide, ids: selectedItems(sheetItems, keys).map((i) => i.id) });
            setSheetSide(null);
          }}
          onClose={() => setSheetSide(null)}
          onInfo={(item) => ctx.openPlayer(item.ref as SimGamePlayer)}
        />
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
          { label: `Inbox${offers ? ` ${offers}` : ""}`, value: "inbox", glyph: "inbox" },
          { label: "Make an offer", value: "build", glyph: "build" },
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
