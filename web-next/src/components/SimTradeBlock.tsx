"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SimPickLine, useSimPicks } from "@/components/SimGameDynastyParts";
import { SimPlayerLine, SimSectionTitle, SimTeamLink, type SimCtx } from "@/components/SimGameParts";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import { simListStats } from "@/lib/simDraft";
import { simIsPick, simPicksOf, type SimBlockResponse, type SimGamePlayer, type SimPickAsset, type SimPos, type SimTradeAsset } from "@/lib/simGame";

type Hint = SimPos | "any";
const HINTS: { label: string; value: Hint }[] = [{ label: "Any", value: "any" }, ...(["QB", "RB", "WR", "TE"] as const).map((p) => ({ label: p, value: p as Hint }))];

/**
 * Trades > My block: the players and picks you are shopping (each with an optional "looking for" position), how many of this
 * week's offers came from it, and the AI teams that are shopping this week with their stated needs. AI managers read your
 * block when they write offers; a blocked asset that leaves your team comes off by itself.
 */
export function SimBlockView({ ctx, onMakeOffer }: { ctx: SimCtx; onMakeOffer: (partner: string, get: string) => void }) {
  const [block, setBlock] = useState<SimBlockResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [roster, setRoster] = useState<SimGamePlayer[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const picks = useSimPicks(ctx);
  const teamId = ctx.game.you?.team_id;

  useEffect(() => {
    let cancelled = false;
    api
      .getSimBlock(ctx.gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else {
          setFailed(false);
          setBlock(body);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId, ctx.tick, attempt]);

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(ctx.gameId, teamId)
      .then((b) => !cancelled && setRoster([...(b.players ?? []), ...(b.ir ?? []), ...(b.taxi ?? [])]))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId, teamId, ctx.tick]);

  const toggle = useCallback(
    async (assetId: string, on: boolean, hint: Hint = "any") => {
      setBusy(assetId);
      const res = await ctx.call(() => api.putSimBlock(ctx.gameId, { asset_id: assetId, on, looking_for: on && hint !== "any" ? hint : null }));
      setBusy(null);
      if (res && !res.reason) {
        setBlock(res);
        ctx.bump();
      }
    },
    [ctx],
  );

  const onIds = useMemo(() => new Set((block?.mine ?? []).map((m) => m.asset.id)), [block]);
  const candidates = useMemo(() => roster.filter((p) => !onIds.has(p.id) && p.pos !== "K" && p.pos !== "DEF").sort((a, b) => b.value - a.value), [roster, onIds]);
  const myPicks = simPicksOf(picks, teamId).filter((p) => !onIds.has(p.id));

  if (failed) return <EmptyState title="Could not load your block" subtitle="Check your connection and try again." actionLabel="Try again" onAction={() => { setFailed(false); setAttempt((n) => n + 1); }} />;
  if (!block) return <SkeletonCard lines={5} />;
  if (!block.enabled) return <EmptyState title="No trade block in this game" subtitle="This game was started before the trade block existed." />;
  const full = (block.mine?.length ?? 0) >= (block.max_items ?? 8);
  const mine = block.mine ?? [];
  return (
    <div className="flex flex-col gap-4" data-testid="sim-block">
      <section className="flex flex-col gap-2" aria-label="My block">
        <SimSectionTitle glyph="trade" tone="accent" note="AI managers read your block when they write offers. Add a position you are looking for and they will try to send it.">My block</SimSectionTitle>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="sim-block-summary">
          {mine.length} of {block.max_items ?? 8} on your block · {block.offers_from_block ?? 0} offer{block.offers_from_block === 1 ? "" : "s"} from your block this week
        </p>
        {mine.length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Nothing on your block yet. Add a player or pick below.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {mine.map((m) => (
              <li key={m.asset.id}>
                <AccentCard accent="var(--color-accent)" compact as="div">
                  {simIsPick(m.asset) ? (
                    <SimPickLine pick={m.asset as SimPickAsset} trailing={<Button size="sm" variant="secondary" loading={busy === m.asset.id} onClick={() => toggle(m.asset.id, false)}>Remove</Button>} />
                  ) : (
                    <SimPlayerLine player={m.asset as SimGamePlayer} onOpen={ctx.openPlayer} stats={simListStats(m.asset as SimGamePlayer, { adp: false })} trailing={<Button size="sm" variant="secondary" loading={busy === m.asset.id} onClick={() => toggle(m.asset.id, false)}>Remove</Button>} />
                  )}
                  <div className="flex items-center gap-2">
                    <span className="shrink-0 text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>Looking for</span>
                    <PillRow ariaLabel={`Looking for, ${simIsPick(m.asset) ? "pick" : (m.asset as SimGamePlayer).name}`} variant="compact" options={HINTS} active={m.looking_for ?? "any"} onSelect={(v) => toggle(m.asset.id, true, v as Hint)} />
                  </div>
                </AccentCard>
              </li>
            ))}
          </ul>
        )}
        <SimSectionTitle glyph="team" tone="muted" note={full ? "Your block is full. Remove one to add another." : undefined}>Add to your block</SimSectionTitle>
        <ul className="flex flex-col" aria-label="Add to your block">
          {(showAll ? candidates : candidates.slice(0, 8)).map((p) => (
            <li key={p.id}>
              <SimPlayerLine player={p} onOpen={ctx.openPlayer} stats={simListStats(p, { adp: false })} trailing={<Button size="sm" disabled={full} loading={busy === p.id} onClick={() => toggle(p.id, true)} aria-label={`Put ${p.name} on the block`}>Block</Button>} />
            </li>
          ))}
          {myPicks.map((p: SimPickAsset) => (
            <li key={p.id}>
              <SimPickLine pick={p} trailing={<Button size="sm" disabled={full} loading={busy === p.id} onClick={() => toggle(p.id, true)} aria-label="Put this pick on the block">Block</Button>} />
            </li>
          ))}
        </ul>
        {candidates.length > 8 ? <Button size="sm" variant="secondary" onClick={() => setShowAll((v) => !v)}>{showAll ? "Show fewer" : `Show all ${candidates.length}`}</Button> : null}
      </section>

      <section className="flex flex-col gap-2" aria-label="Around the league">
        <SimSectionTitle glyph="league" tone="accent" note="AI teams shop different assets each week: contenders sell depth and picks, rebuilders sell vets.">Around the league</SimSectionTitle>
        {(block.league ?? []).length === 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No AI team is shopping anyone this week.</p>
        ) : (
          (block.league ?? []).map((t) => (
            <AccentCard key={t.team_id} accent="var(--color-border-strong)" compact as="div">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <SimTeamLink teamId={t.team_id} name={t.name} size={24} />
                <span className="flex items-center gap-1">
                  <ToneBadge label={t.stance} color="var(--color-premium)" size="xs" />
                  {t.looking_for ? <ToneBadge label={`Wants ${t.looking_for}`} color="var(--color-danger)" size="xs" /> : null}
                </span>
              </div>
              {t.needs.length > 0 ? <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>Needs {t.needs.join(", ")}</p> : null}
              <ul className="flex flex-col">
                {t.items.map((i: { asset: SimTradeAsset; why: string }) => (
                  <li key={i.asset.id}>
                    {simIsPick(i.asset) ? <SimPickLine pick={i.asset as SimPickAsset} /> : <SimPlayerLine player={i.asset as SimGamePlayer} onOpen={ctx.openPlayer} stats={simListStats(i.asset as SimGamePlayer, { adp: false })} />}
                    <p className="pb-1 text-xs" style={{ color: "var(--color-text-muted)" }}>{i.why}</p>
                  </li>
                ))}
              </ul>
              {ctx.game.can_trade ? <Button size="sm" variant="secondary" onClick={() => onMakeOffer(t.team_id, t.items[0].asset.id)}>Make an offer to {t.name}</Button> : null}
            </AccentCard>
          ))
        )}
      </section>
    </div>
  );
}

/**
 * The player sheet's block button: put one of your players on the block (or take him off). It reads the game's block once so
 * it shows the right state, and only appears in a game that has a trade block.
 */
export function SimBlockToggle({ ctx, player }: { ctx: SimCtx; player: SimGamePlayer }) {
  const [on, setOn] = useState<boolean | null>(player.block?.mine ? true : null);
  const [busy, setBusy] = useState(false);
  const enabled = (ctx.game.settings.block_v ?? 0) >= 1;
  useEffect(() => {
    if (!enabled || player.block?.mine) return;
    let cancelled = false;
    api
      .getSimBlock(ctx.gameId)
      .then((b) => !cancelled && setOn((b.mine ?? []).some((m) => m.asset.id === player.id)))
      .catch(() => !cancelled && setOn(false));
    return () => {
      cancelled = true;
    };
  }, [enabled, ctx.gameId, player.id, player.block?.mine]);
  if (!enabled || player.owner?.type !== "you" || player.pos === "K" || player.pos === "DEF") return null;
  return (
    <Button
      size="sm"
      variant="secondary"
      loading={busy}
      disabled={on === null}
      onClick={async () => {
        setBusy(true);
        const res = await ctx.call(() => api.putSimBlock(ctx.gameId, { asset_id: player.id, on: !on }));
        setBusy(false);
        if (res && !res.reason) {
          setOn(!on);
          ctx.bump();
          ctx.notify(!on ? `${player.name} is on your block.` : `${player.name} is off your block.`, "success");
        }
      }}
    >
      {on ? "Take off the block" : "Put on the block"}
    </Button>
  );
}
