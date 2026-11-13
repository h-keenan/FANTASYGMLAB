"use client";

import { useContext, useEffect, useMemo, useReducer, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { SectionHeading } from "@/components/SectionHeading";
import { ReviewGlyphChip } from "@/components/SeasonReviewSections";
import { SimCrest } from "@/components/SimCrest";
import { SimGlyph } from "@/components/SimGlyph";
import { SimPlayerChip, SimPlayerLine, SimSideLabel, SimStat, SimTeamOpenContext, SimToneBadge, simToneColor, type SimCtx } from "@/components/SimGameParts";
import { SimPickLine, useSimPicks } from "@/components/SimGameDynastyParts";
import { SkeletonCard, SkeletonRows } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { SIM_ASSET_ALL, simFilterGroups, simGroupByPosition, simSideSummary, simTradeFit, type SimAssetGroup } from "@/lib/simLayout";
import {
  SIM_TRADE_EMPTY,
  simFmtPts,
  simIsPick,
  simPickGroups,
  simPickLabelText,
  simPicksOf,
  simPositionsFor,
  simTradeMaxPerSide,
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
  type SimTradeAsset,
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

/** Players and picks in an offer, counter or verdict: a pick renders as a pick row, never as a player. */
function PlayerList({ players }: { players: SimTradeAsset[] }) {
  return (
    <ul className="flex flex-col">
      {players.map((p) => (
        <li key={p.id}>
          {simIsPick(p) ? (
            <SimPickLine pick={p} />
          ) : (
            <div className="flex items-center justify-between gap-2 py-1">
              <SimPlayerChip player={p} size={28} quick className="min-w-0 flex-1" />
              <SimStat label="Proj" value={simFmtPts(p.projection)} />
            </div>
          )}
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
  const names = (list: SimTradeAsset[]) => list.map((p) => (simIsPick(p) ? simPickLabelText(p) : p.name.split(" ").slice(-1)[0])).join(", ");
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
  const [side, setSide] = useState<"give" | "get">(seed ? "get" : "give");
  const closed = simTradeClosedReason(game);
  const teamId = game.you?.team_id;
  const maxPerSide = simTradeMaxPerSide(game.settings);
  const picks = useSimPicks(ctx);

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
    api.getSimGameTeam(gameId, teamId).then((b) => !cancelled && setMine([...(b.players ?? []), ...(b.ir ?? []), ...(b.taxi ?? [])])).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  useEffect(() => {
    const partnerId = draft.partner;
    if (!partnerId) return;
    let cancelled = false;
    api.getSimGameTeam(gameId, partnerId).then((b) => !cancelled && setPartnerLoaded({ partner: partnerId, players: [...(b.players ?? []), ...(b.ir ?? []), ...(b.taxi ?? [])] })).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, draft.partner, ctx.tick]);
  const partnerRoster = partnerLoaded && partnerLoaded.partner === draft.partner ? partnerLoaded.players : [];

  // "Trade for him" from the Players tab: preselect the partner and the player.
  useEffect(() => {
    if (!seed) return;
    dispatch({ type: "partner", teamId: seed.partner });
    if (seed.get) dispatch({ type: "toggle", side: "get", id: seed.get, max: maxPerSide });
    onSeedUsed();
  }, [seed, onSeedUsed, maxPerSide]);

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

  // Picks ride in the same id-based draft as players; they take no roster spot.
  const myPicks = simPicksOf(picks, teamId);
  const theirPicks = simPicksOf(picks, partner?.team_id);
  const giveSelected: SimTradeAsset[] = [...mine, ...myPicks].filter((p) => draft.give.includes(p.id));
  const getSelected: SimTradeAsset[] = [...partnerRoster, ...theirPicks].filter((p) => draft.get.includes(p.id));
  const fit = simTradeFit(mine.length, game.settings.roster_limit, giveSelected.filter((p) => !simIsPick(p)).length, getSelected.filter((p) => !simIsPick(p)).length);
  const pool = side === "give" ? mine : partnerRoster;
  const groups: SimAssetGroup<SimTradeAsset>[] = simGroupByPosition(pool.filter((p) => simTradable(p.pos)), simPositionsFor(game.settings.slots));
  const sidePicks = side === "give" ? myPicks : theirPicks;
  if (sidePicks.length > 0) groups.push({ key: "PICK", label: "Picks", kind: "pick", items: sidePicks });

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
            <SideSummary label="You send" tone="danger" active={side === "give"} onSelect={() => setSide("give")} assets={giveSelected} onRemove={(id) => dispatch({ type: "toggle", side: "give", id, max: maxPerSide })} />
            <SideSummary label="You receive" tone="success" active={side === "get"} onSelect={() => setSide("get")} assets={getSelected} onRemove={(id) => dispatch({ type: "toggle", side: "get", id, max: maxPerSide })} />
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

      {partner ? (
        <AssetPicker
          key={side}
          label={side === "give" ? "Your roster" : `${partner.name}'s roster`}
          groups={groups}
          selected={side === "give" ? draft.give : draft.get}
          verb={side === "give" ? "Give" : "Get"}
          doneVerb={side === "give" ? "Giving" : "Getting"}
          onToggle={(id) => dispatch({ type: "toggle", side, id, max: maxPerSide })}
          maxPerSide={maxPerSide}
          draftYear={picks?.draft_year}
          onOpen={ctx.openPlayer}
        />
      ) : null}
    </div>
  );
}

/** One side of the offer as a compact summary: count, total value and the chosen players (tap one to remove). */
function SideSummary({ label, tone, active, onSelect, assets, onRemove }: { label: string; tone: "danger" | "success"; active: boolean; onSelect: () => void; assets: SimTradeAsset[]; onRemove: (id: string) => void }) {
  const sum = simSideSummary(assets);
  const color = simToneColor(tone);
  return (
    <div className="glass-surface flex min-w-0 flex-col gap-1.5 p-2" style={active ? { borderColor: "var(--color-accent)" } : undefined} data-testid={`trade-side-${tone === "danger" ? "give" : "get"}`}>
      <button type="button" onClick={onSelect} className="tap-link flex flex-col items-start gap-0.5 text-left" aria-pressed={active} aria-label={`${label}: ${sum.count} selected. Choose players`}>
        <span className="flex items-center gap-1.5 text-xs font-extrabold uppercase" style={{ color: active ? "var(--color-accent)" : "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
          {label}
        </span>
        <span className="text-sm font-extrabold tabular-nums">{sum.count} <span className="text-xs font-normal" style={{ color: "var(--color-text-muted)" }}>· value {sum.value}</span></span>
      </button>
      {assets.length === 0 ? (
        <span className="text-xs italic" style={{ color: "var(--color-text-muted)" }}>Tap to add</span>
      ) : (
        <ul className="flex flex-col gap-1">
          {assets.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-1">
              {simIsPick(p) ? (
                <span className="flex min-w-0 flex-1 items-center gap-1.5 text-xs font-bold" data-testid="pick-chip">
                  <ToneBadge label={`R${p.round}`} color="var(--color-accent)" size="xs" />
                  <span className="min-w-0 truncate">{simPickLabelText(p)}</span>
                </span>
              ) : (
                <SimPlayerChip player={p} size={20} quick hidePosition className="min-w-0 flex-1" />
              )}
              <button type="button" className="shrink-0 px-1 text-sm font-bold" style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)", minWidth: 28 }} aria-label={`Remove ${simIsPick(p) ? simPickLabelText(p) : p.name}`} onClick={() => onRemove(p.id)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * The trade picker: position chips (plus any other group, e.g. a future
 * "Picks"), a search box and the roster in collapsible groups, not one flat
 * list. Groups are generic (`kind: "player" | "pick"`): dynasty games add a
 * Picks group per side, listed by year and round with each pick's value.
 * A side stops at `maxPerSide` assets (players and picks together).
 */
function AssetPicker({ label, groups, selected, verb, doneVerb, maxPerSide, draftYear, onToggle, onOpen }: { label: string; groups: SimAssetGroup<SimTradeAsset>[]; selected: string[]; verb: string; doneVerb: string; maxPerSide: number; draftYear?: number | null; onToggle: (id: string) => void; onOpen: (p: SimGamePlayer) => void }) {
  const [filter, setFilter] = useState(SIM_ASSET_ALL);
  const [search, setSearch] = useState("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const shown = simFilterGroups(groups, filter, search);
  const single = filter !== SIM_ASSET_ALL || search.trim() !== "";
  const full = selected.length >= maxPerSide;
  return (
    <section className="flex flex-col gap-2" aria-label={label}>
      <SectionHeading note={`Up to ${maxPerSide}. ${selected.length} selected.`}>{label}</SectionHeading>
      <PillRow
        ariaLabel="Position filter"
        variant="scroll"
        options={[{ label: "All", value: SIM_ASSET_ALL }, ...groups.map((g) => ({ label: g.label, value: g.key }))]}
        active={filter}
        onSelect={setFilter}
      />
      <Input type="search" inputMode="search" placeholder="Search your players" aria-label="Search players" value={search} onChange={(event) => setSearch(event.target.value)} className="w-full" />
      {shown.length === 0 ? (
        <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>{search ? "No matching players or picks." : "No tradable players here."}</p>
      ) : (
        shown.map((group, index) => {
          const open = toggled[group.key] ?? (single || index === 0);
          const chosen = group.items.filter((p) => selected.includes(p.id)).length;
          return (
            <section key={group.key} className="glass-surface" aria-label={`${group.label} group`}>
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setToggled((prev) => ({ ...prev, [group.key]: !open }))}
                className="flex w-full items-center gap-2 px-3 py-2 text-left"
                style={{ minHeight: "var(--touch-target-min)" }}
              >
                <span className="text-sm font-bold">{group.label}</span>
                <ToneBadge label={`${group.items.length}`} color="var(--color-information)" size="xs" />
                {chosen > 0 ? <ToneBadge label={`${chosen} selected`} color="var(--color-success)" size="xs" /> : null}
                <span aria-hidden="true" className="ml-auto text-xs" style={{ color: "var(--color-text-muted)" }}>{open ? "\u2212" : "+"}</span>
              </button>
              {open ? (
                <div className="px-2" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
                  {group.kind === "pick"
                    ? simPickGroups(group.items.filter(simIsPick)).map((year) => (
                        <div key={year.season} className="flex flex-col">
                          <p className="pt-1 text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>{year.season}</p>
                          {year.rounds.flatMap((r) => r.picks).map((pick) => {
                            const on = selected.includes(pick.id);
                            return (
                              <SimPickLine
                                key={pick.id}
                                pick={pick}
                                selected={on}
                                draftYear={draftYear}
                                trailing={
                                  <Button size="sm" variant={on ? "primary" : "secondary"} aria-pressed={on} disabled={!on && full} aria-label={`${verb} ${simPickLabelText(pick)}`} onClick={() => onToggle(pick.id)}>
                                    {on ? doneVerb : verb}
                                  </Button>
                                }
                              />
                            );
                          })}
                        </div>
                      ))
                    : group.items.map((p) => {
                    const on = selected.includes(p.id);
                    if (simIsPick(p)) return null;
                    return (
                      <SimPlayerLine
                        key={p.id}
                        player={p}
                        hidePosition
                        onOpen={onOpen}
                        selected={on}
                        trailing={
                          <>
                            <SimStat label="Value" value={Math.round(p.value)} />
                            <Button size="sm" variant={on ? "primary" : "secondary"} aria-pressed={on} disabled={!on && full} aria-label={`${verb} ${p.name}`} onClick={() => onToggle(p.id)}>
                              {on ? doneVerb : verb}
                            </Button>
                          </>
                        }
                      />
                    );
                  })}
                </div>
              ) : null}
            </section>
          );
        })
      )}
    </section>
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
