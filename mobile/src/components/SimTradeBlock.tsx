import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPickLine, useSimPicks } from './SimGameDynastyParts';
import { SimPlayerLine, SimSectionTitle, SimTeamLink, createSimStyles, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simListStats } from '../lib/simDraft';
import { simGradeCompare } from '../lib/simGrade';
import { simIsPick, simPicksOf, type SimBlockResponse, type SimGamePlayer, type SimPickAsset, type SimPos, type SimTradeAsset } from '../lib/simGame';

type Hint = SimPos | 'any';
const HINTS: { key: Hint; label: string }[] = [{ key: 'any', label: 'Any' }, ...(['QB', 'RB', 'WR', 'TE'] as const).map((p) => ({ key: p as Hint, label: p }))];

/**
 * Trades > My block: the players and picks you are shopping (each with an optional "looking for" position), how many of this
 * week's offers came from it, and the AI teams that are shopping this week with their stated needs. Twin of web's SimBlockView.
 */
export function SimBlockView({ ctx, onMakeOffer }: { ctx: SimCtx; onMakeOffer: (partner: string, get: string) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
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
    async (assetId: string, on: boolean, hint: Hint = 'any') => {
      setBusy(assetId);
      const res = await ctx.call(() => api.putSimBlock(ctx.gameId, { asset_id: assetId, on, looking_for: on && hint !== 'any' ? hint : null }));
      setBusy(null);
      if (res && !res.reason) {
        setBlock(res);
        ctx.bump();
      }
    },
    [ctx],
  );

  const onIds = useMemo(() => new Set((block?.mine ?? []).map((m) => m.asset.id)), [block]);
  const candidates = useMemo(() => roster.filter((p) => !onIds.has(p.id) && p.pos !== 'K' && p.pos !== 'DEF').sort((a, b) => simGradeCompare(a, b) || (b.ros_mean ?? 0) - (a.ros_mean ?? 0)), [roster, onIds]);
  const myPicks = simPicksOf(picks, teamId).filter((p) => !onIds.has(p.id));

  if (failed) {
    return (
      <ErrorState
        title="Your block did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!block) return <SkeletonCard rows={5} />;
  if (!block.enabled) return <EmptyState icon="swap-horizontal-outline" title="No trade block in this game" subtitle="This game was started before the trade block existed." />;
  const mine = block.mine ?? [];
  const full = mine.length >= (block.max_items ?? 8);
  return (
    <View style={common.stack} testID="sim-block">
      <View style={common.stack} accessibilityLabel="My block">
        <SimSectionTitle glyph="trade" title="My block" caption="AI managers read your block when they write offers. Add a position you are looking for and they will try to send it." />
        <AppText style={common.small} testID="sim-block-summary">
          {mine.length} of {block.max_items ?? 8} on your block · {block.offers_from_block ?? 0} offer{block.offers_from_block === 1 ? '' : 's'} from your block this week
        </AppText>
        {mine.length === 0 ? (
          <AppText style={common.muted}>Nothing on your block yet. Add a player or pick below.</AppText>
        ) : (
          mine.map((m) => (
            <AccentCard key={m.asset.id} accent={colors.accent} compact>
              {simIsPick(m.asset) ? (
                <SimPickLine pick={m.asset as SimPickAsset} trailing={<Button size="sm" variant="secondary" label="Remove" loading={busy === m.asset.id} onPress={() => toggle(m.asset.id, false)} />} />
              ) : (
                <SimPlayerLine
                  player={m.asset as SimGamePlayer}
                  onOpen={ctx.openPlayer}
                  stats={simListStats(m.asset as SimGamePlayer, { adp: false })}
                  trailing={<Button size="sm" variant="secondary" label="Remove" loading={busy === m.asset.id} onPress={() => toggle(m.asset.id, false)} />}
                />
              )}
              <View style={common.row}>
                <AppText style={common.muted}>Looking for</AppText>
                <View style={common.grow}>
                  <SegmentedTabBar<Hint> scrollable options={HINTS} active={m.looking_for ?? 'any'} onChange={(k) => toggle(m.asset.id, true, k)} />
                </View>
              </View>
            </AccentCard>
          ))
        )}
        <SimSectionTitle glyph="team" tone="muted" title="Add to your block" caption={full ? 'Your block is full. Remove one to add another.' : undefined} />
        {(showAll ? candidates : candidates.slice(0, 8)).map((p) => (
          <SimPlayerLine
            key={p.id}
            player={p}
            onOpen={ctx.openPlayer}
            stats={simListStats(p, { adp: false })}
            trailing={<Button size="sm" label="Block" disabled={full} loading={busy === p.id} onPress={() => toggle(p.id, true)} />}
          />
        ))}
        {myPicks.map((p: SimPickAsset) => (
          <SimPickLine key={p.id} pick={p} trailing={<Button size="sm" label="Block" disabled={full} loading={busy === p.id} onPress={() => toggle(p.id, true)} />} />
        ))}
        {candidates.length > 8 ? <Button size="sm" variant="secondary" label={showAll ? 'Show fewer' : `Show all ${candidates.length}`} onPress={() => setShowAll((v) => !v)} /> : null}
      </View>

      <View style={common.stack} accessibilityLabel="Around the league">
        <SimSectionTitle glyph="league" title="Around the league" caption="AI teams shop different assets each week: contenders sell depth and picks, rebuilders sell vets." />
        {(block.league ?? []).length === 0 ? (
          <AppText style={common.muted}>No AI team is shopping anyone this week.</AppText>
        ) : (
          (block.league ?? []).map((t) => (
            <AccentCard key={t.team_id} accent={colors.borderStrong} compact>
              <View style={common.rowBetween}>
                <SimTeamLink teamId={t.team_id} name={t.name} size={24} />
                <View style={common.row}>
                  <ToneBadge label={t.stance} color={colors.premium} size="xs" />
                  {t.looking_for ? <ToneBadge label={`Wants ${t.looking_for}`} color={colors.danger} size="xs" /> : null}
                </View>
              </View>
              {t.needs.length > 0 ? <AppText style={common.small}>Needs {t.needs.join(', ')}</AppText> : null}
              {t.items.map((i: { asset: SimTradeAsset; why: string }) => (
                <View key={i.asset.id}>
                  {simIsPick(i.asset) ? <SimPickLine pick={i.asset as SimPickAsset} /> : <SimPlayerLine player={i.asset as SimGamePlayer} onOpen={ctx.openPlayer} stats={simListStats(i.asset as SimGamePlayer, { adp: false })} />}
                  <AppText style={common.muted}>{i.why}</AppText>
                </View>
              ))}
              {ctx.game.can_trade ? <Button size="sm" variant="secondary" label={`Make an offer to ${t.name}`} onPress={() => onMakeOffer(t.team_id, t.items[0].asset.id)} /> : null}
            </AccentCard>
          ))
        )}
      </View>
    </View>
  );
}

/** The player sheet's block button for one of your own players (only in a game that has a trade block). Twin of web's SimBlockToggle. */
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
  if (!enabled || player.owner?.type !== 'you' || player.pos === 'K' || player.pos === 'DEF') return null;
  return (
    <Button
      size="sm"
      variant="secondary"
      label={on ? 'Take off the block' : 'Put on the block'}
      loading={busy}
      disabled={on === null}
      onPress={async () => {
        setBusy(true);
        const res = await ctx.call(() => api.putSimBlock(ctx.gameId, { asset_id: player.id, on: !on }));
        setBusy(false);
        if (res && !res.reason) {
          setOn(!on);
          ctx.bump();
          ctx.notify(!on ? `${player.name} is on your block.` : `${player.name} is off your block.`, 'success');
        }
      }}
    />
  );
}
