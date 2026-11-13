import React, { useContext, useEffect, useMemo, useReducer, useState } from 'react';
import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import FadeInView from './FadeInView';
import { ReviewGlyphChip } from './SeasonReviewSections';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { MotionIn } from './Motion';
import SimCrest from './SimCrest';
import SimGlyph from './SimGlyph';
import { SimBlockView } from './SimTradeBlock';
import SimTeamCard from './SimTeamCard';
import { SimPickLine, useSimPicks } from './SimGameDynastyParts';
import { SimPlayerChip, SimPlayerLine, SimPopIn, SimSideLabel, SimStat, SimTeamOpenContext, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simGroupByPosition, simSideSummary, simTradeFit, type SimAssetGroup } from '../lib/simLayout';
import { simListStats } from '../lib/simDraft';
import { simTeamsByPower } from '../lib/simLeagueRosters';
import { simGroupsToSheetItems } from '../lib/simTradeSheet';
import { useSimLeagueRosters } from '../lib/useSimLeagueRosters';
import { SimPlayerSheet } from './SimGamePlayers';
import { selectedItems } from '../lib/tradeSheetPicker';
import TradePickerSheet, { TradeSideSummary } from './TradePickerSheet';
import {
  SIM_TRADE_EMPTY,
  simFmtPts,
  simIsPick,
  simIsPickId,
  simPickLabelText,
  simPicksOf,
  simHeadshotId,
  simPositionsFor,
  simGameReasonMessage,
  type SimTradeSeed,
  simTradeMaxPerSide,
  simTradable,
  simTradeClosedReason,
  simCounterDeltaLine,
  simTradeDecisionLabel,
  simTradeDecisionTone,
  simTradeKey,
  simTradePayload,
  simTradeReady,
  simTradeReducer,
  type SimGamePlayer,
  type SimInboxItem,
  type SimPickAsset,
  type SimTradeAsset,
  type SimTradeVerdict,
  simWithout,
} from '../lib/simGame';
import type { ThemeColors } from '../theme';

/** "Scout" button for the partner list: opens the team's scouting sheet without picking it as the partner. */
function ScoutButton({ teamId, name }: { teamId: string; name: string }) {
  const { colors } = useThemeMode();
  const open = useContext(SimTeamOpenContext);
  if (!open) return null;
  return (
    <Pressable onPress={() => open(teamId)} accessibilityRole="button" accessibilityLabel={`Scout ${name}`} style={{ minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <SimGlyph name="team" color={colors.accent} size={13} />
      <AppText style={{ fontSize: 13, fontWeight: '800', color: colors.accent }}>Scout</AppText>
    </Pressable>
  );
}

/** Players and picks in an offer, counter or verdict: a pick renders as a pick row, never as a player. */
function PlayerList({ players }: { players: SimTradeAsset[] }) {
  return (
    <View>
      {players.map((p) =>
        simIsPick(p) ? (
          <SimPickLine key={p.id} pick={p} />
        ) : (
          <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingVertical: 4 }}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <SimPlayerChip player={p} size={28} quick />
            </View>
            <SimStat label="Proj" value={simFmtPts(p.projection)} />
          </View>
        ),
      )}
    </View>
  );
}

/** AI-proposed offers: accept or decline. They expire when the week advances. */
function Inbox({ ctx }: { ctx: SimCtx }) {
  const { gameId, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [items, setItems] = useState<SimInboxItem[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

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
  }, [gameId, ctx.tick, attempt]);

  async function respond(item: SimInboxItem, action: 'accept' | 'decline') {
    setBusyId(item.id);
    if (action === 'decline') setItems((prev) => (prev ? simWithout(prev, item.id) : prev)); // optimistic: a decline cannot fail the rules
    const body = await call(() => api.respondSimInbox(gameId, item.id, action));
    setBusyId(null);
    if (body) {
      setItems(body.items ?? []);
      ctx.notify(action === 'accept' && body.executed ? `Trade done with ${item.from.name}.` : `Declined ${item.from.name}'s offer.`, action === 'accept' ? 'success' : 'muted');
      ctx.bump();
      void ctx.reloadGame();
    } else {
      // offer_invalid and friends: refresh the list so the stale card goes away.
      api
        .getSimInbox(gameId)
        .then((b) => setItems(b.items ?? []))
        .catch(() => {});
    }
  }

  if (failed) {
    return (
      <ErrorState
        title="Your inbox did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!items) return <SkeletonCard rows={4} />;
  if (items.length === 0) {
    return <EmptyState icon="mail-outline" title="No offers right now" subtitle="AI managers send at most a few offers a week. They show up here and expire when you advance." />;
  }
  return (
    <View style={common.stack} accessibilityLabel="Trade offers">
      {items.map((item, index) => (
        <MotionIn key={item.id} index={index} count={items.length}><OfferCard item={item} defaultOpen={index === 0} busy={busyId === item.id} canTrade={Boolean(ctx.game.can_trade)} onRespond={respond} /></MotionIn>
      ))}
    </View>
  );
}

/** One AI offer as a compact card: who, what moves and when it expires; tap to expand the players and the Accept / Decline buttons. */
function OfferCard({ item, defaultOpen, busy, canTrade, onRespond }: { item: SimInboxItem; defaultOpen: boolean; busy: boolean; canTrade: boolean; onRespond: (item: SimInboxItem, action: 'accept' | 'decline') => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  const give = simSideSummary(item.you_give);
  const get = simSideSummary(item.you_get);
  const names = (list: SimTradeAsset[]) => list.map((p) => (simIsPick(p) ? simPickLabelText(p) : p.name.split(' ').slice(-1)[0])).join(', ');
  return (
    <FadeInView>
      <AccentCard accent={colors.premium} compact>
        <Pressable
          onPress={() => setOpen((v) => !v)}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`Offer from ${item.from.name}`}
          style={{ minHeight: 44, gap: 4, justifyContent: 'center' }}
        >
          <View style={common.rowBetween}>
            <View style={[common.row, { flex: 1, minWidth: 0 }]}>
              <SimCrest name={item.from.name} size={24} />
              <AppText style={[common.bodyStrong, { flexShrink: 1 }]} numberOfLines={1}>
                {item.from.name}
              </AppText>
            </View>
            <View style={common.row}>
              {item.via_block ? <ToneBadge label="Your block" color={colors.accent} size="xs" /> : null}
              <ToneBadge label={`Wk ${item.expires_week}`} color={colors.warning} size="xs" />
              <AppText style={common.muted} accessibilityElementsHidden>
                {open ? '\u2212' : '+'}
              </AppText>
            </View>
          </View>
          <AppText style={common.small}>
            <AppText style={{ fontWeight: '800', color: colors.danger, fontSize: 13 }}>Give</AppText> {names(item.you_give)} (trade value {give.value}){' \u00b7 '}
            <AppText style={{ fontWeight: '800', color: colors.success, fontSize: 13 }}>Get</AppText> {names(item.you_get)} (trade value {get.value})
          </AppText>
        </Pressable>
        {open ? (
          <View style={common.stack}>
            {item.message ? <AppText style={common.small}>{item.message}</AppText> : null}
            <View>
              <SimSideLabel side="give" />
              <PlayerList players={item.you_give} />
            </View>
            <View>
              <SimSideLabel side="get" />
              <PlayerList players={item.you_get} />
            </View>
            <View style={common.row}>
              <Button size="sm" label="Accept" loading={busy} disabled={!canTrade} onPress={() => onRespond(item, 'accept')} />
              <Button size="sm" variant="secondary" label="Decline" disabled={busy} onPress={() => onRespond(item, 'decline')} />
            </View>
          </View>
        ) : null}
      </AccentCard>
    </FadeInView>
  );
}

function VerdictCard({ verdict, onSendCounter, busy }: { verdict: SimTradeVerdict; onSendCounter: () => void; busy: boolean }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tone = simTradeDecisionTone(verdict.decision);
  return (
    <SimPopIn>
      <AccentCard accent={simToneColor(tone, colors)} glow>
        <View testID="trade-verdict" style={common.stack} accessibilityLiveRegion="polite">
          <View style={common.rowBetween}>
            <View style={[common.row, common.grow]}>
              <ReviewGlyphChip glyph="trade" tone={tone} size={28} />
              <AppText style={common.title}>{simTradeDecisionLabel(verdict.decision)}</AppText>
            </View>
            <SimToneBadge tone={tone} label={verdict.decision} />
          </View>
          <AppText style={common.body}>{verdict.reason}</AppText>
          {(verdict.chips ?? []).length > 0 ? (
            <View style={common.wrapRow}>
              {verdict.chips!.map((chip) => (
                <ToneBadge key={chip} label={chip} color={colors.textSecondary} size="xs" />
              ))}
            </View>
          ) : null}
          {verdict.decision === 'counter' && verdict.counter ? (
            <View style={common.stack}>
              <AppText style={[common.bodyStrong, { color: colors.accent }]}>Their counter</AppText>
              {verdict.counter_note ? <AppText style={common.body} testID="counter-note">{verdict.counter_note}</AppText> : null}
              {simCounterDeltaLine(verdict.counter_delta) ? <AppText style={common.muted} testID="counter-delta">{simCounterDeltaLine(verdict.counter_delta)}</AppText> : null}
              <SimSideLabel side="give" />
              <PlayerList players={verdict.counter.give} />
              <SimSideLabel side="get" />
              <PlayerList players={verdict.counter.get} />
              <Button size="sm" label="Take their counter" loading={busy} onPress={onSendCounter} />
            </View>
          ) : null}
        </View>
      </AccentCard>
    </SimPopIn>
  );
}

/** Build an offer to any AI team, preview the (deterministic) verdict, then send it. */
function Builder({ ctx, seed, onSeedUsed }: { ctx: SimCtx; seed: SimTradeSeed | null; onSeedUsed: () => void }) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [draft, dispatch] = useReducer(simTradeReducer, SIM_TRADE_EMPTY);
  const [teamsAttempt, setTeamsAttempt] = useState(0);
  const [partnerLoaded, setPartnerLoaded] = useState<{ partner: string; players: SimGamePlayer[] } | null>(null);
  const [mine, setMine] = useState<SimGamePlayer[]>([]);
  // The verdict is stored with the offer it answers, so a changed offer
  // never shows the old verdict.
  const [verdictFor, setVerdictFor] = useState<{ key: string; verdict: SimTradeVerdict | null } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [sheetSide, setSheetSide] = useState<'give' | 'get' | null>(null);
  const [viewing, setViewing] = useState<SimGamePlayer | null>(null);
  const closed = simTradeClosedReason(game);
  const teamId = game.you?.team_id;
  const maxPerSide = simTradeMaxPerSide(game.settings);
  const picks = useSimPicks(ctx);

  // Every partner's record, top assets, needs and depth from one request (the shared team card's data).
  const rosters = useSimLeagueRosters(gameId, ctx.tick, teamsAttempt);
  const teams = useMemo(() => (rosters.status === 'ready' ? rosters.teams.filter((t) => !t.is_you) : null), [rosters]);
  const teamsFailed = rosters.status === 'error' ? (rosters.message ?? 'Check your connection and try again.') : null;

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((b) => !cancelled && setMine([...(b.players ?? []), ...(b.ir ?? []), ...(b.taxi ?? [])]))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  useEffect(() => {
    const partnerId = draft.partner;
    if (!partnerId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, partnerId)
      .then((b) => !cancelled && setPartnerLoaded({ partner: partnerId, players: [...(b.players ?? []), ...(b.ir ?? []), ...(b.taxi ?? [])] }))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, draft.partner, ctx.tick]);
  const partnerRoster = partnerLoaded && partnerLoaded.partner === draft.partner ? partnerLoaded.players : [];

  // "Trade for him" from the Players tab: preselect the partner and the player.
  useEffect(() => {
    if (!seed) return;
    dispatch({ type: 'seed', seed, max: maxPerSide });
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
      ctx.notify('Trade done. The players are on their new rosters.', 'success');
      dispatch({ type: 'clear' });
      ctx.bump();
      void ctx.reloadGame();
    } else if (body.verdict) {
      setVerdictFor({ key, verdict: body.verdict });
    }
  }

  const partner = teams?.find((t) => t.team_id === draft.partner) ?? null;
  const ready = simTradeReady(draft);
  const teamOptions = useMemo(() => simTeamsByPower(teams ?? []), [teams]);

  if (closed) {
    return <EmptyState icon="lock-closed-outline" title="Trades are closed" subtitle={closed} />;
  }
  if (teamsFailed) {
    return <ErrorState title="Teams did not load" message={teamsFailed} onRetry={() => {
          setTeamsAttempt((n) => n + 1);
        }} />;
  }
  if (!teams) return <SkeletonCard rows={4} />;
  if (teams.length === 0) return <EmptyState icon="people-outline" title="No teams to trade with" subtitle="This league has no other teams to trade with right now." />;

  // Picks ride in the same id-based draft as players; they take no roster spot.
  const myPicks = simPicksOf(picks, teamId);
  const theirPicks = simPicksOf(picks, partner?.team_id);
  const giveSelected: SimTradeAsset[] = [...mine, ...myPicks].filter((p) => draft.give.includes(p.id));
  const getSelected: SimTradeAsset[] = [...partnerRoster, ...theirPicks].filter((p) => draft.get.includes(p.id));
  const fit = simTradeFit(mine.length, game.settings.roster_limit, giveSelected.filter((p) => !simIsPick(p)).length, getSelected.filter((p) => !simIsPick(p)).length);
  // The picker's groups: players by position, then a Picks group; the same shape feeds the page summaries.
  const groupsFor = (players: SimGamePlayer[], pickList: SimPickAsset[]): SimAssetGroup<SimTradeAsset>[] => {
    const groups: SimAssetGroup<SimTradeAsset>[] = simGroupByPosition(players.filter((p) => simTradable(p.pos)), simPositionsFor(game.settings.slots));
    if (pickList.length > 0) groups.push({ key: 'PICK', label: 'Picks', kind: 'pick', items: pickList });
    return groups;
  };
  const describePick = (p: SimTradeAsset) => {
    const pick = p as SimPickAsset;
    return { label: `${simPickLabelText(pick)}${pick.own === false ? ` via ${pick.orig_team_name}` : ""}`, detail: null, round: pick.round, group: `${pick.season} picks` };
  };
  const toItems = (groups: SimAssetGroup<SimTradeAsset>[]) => simGroupsToSheetItems(groups, simHeadshotId, describePick);
  const sheetItems = sheetSide ? toItems(groupsFor(sheetSide === 'give' ? mine : partnerRoster, sheetSide === 'give' ? myPicks : theirPicks)) : [];
  const sideItems = (assets: SimTradeAsset[]) =>
    toItems([
      ...simGroupByPosition(assets.filter((a): a is SimGamePlayer => !simIsPick(a)), simPositionsFor(game.settings.slots)),
      ...(assets.some(simIsPick) ? [{ key: 'PICK', label: 'Picks', kind: 'pick' as const, items: assets.filter(simIsPick) }] : []),
    ]);

  return (
    <View style={common.stack}>
      <View style={common.tight} accessibilityLabel="Trade partner">
        <SectionHeading title="Partner" caption={partner ? undefined : 'Pick a team to trade with.'} />
        {partner ? (
          <>
            <SimTeamCard team={partner} selected valueMode="trade" />
            <View style={common.rowBetween}>
              <Button label="Change partner" variant="secondary" onPress={() => dispatch({ type: 'partner', teamId: '' })} />
              <ScoutButton teamId={partner.team_id} name={partner.name} />
            </View>
          </>
        ) : (
          <View style={common.stack} accessibilityLabel="Teams">
            {teamOptions.map((team) => (
              <SimTeamCard key={team.team_id} team={team} valueMode="trade" openLabel={`Trade with ${team.name}`} onOpen={(id) => dispatch({ type: 'partner', teamId: id })} />
            ))}
          </View>
        )}
      </View>

      {partner ? (
        <>
          <View style={{ flexDirection: 'column', gap: 8 }} accessibilityLabel="Offer">
            <TradeSideSummary testID="trade-side-give" label="You send" tone="danger" items={sideItems(giveSelected)} onOpen={() => setSheetSide('give')} onRemove={(key) => dispatch({ type: 'toggle', side: 'give', id: key.slice(key.indexOf(':') + 1), max: maxPerSide })} hint="Add from your team" />
            <TradeSideSummary testID="trade-side-get" label="You receive" tone="success" items={sideItems(getSelected)} onOpen={() => setSheetSide('get')} onRemove={(key) => dispatch({ type: 'toggle', side: 'get', id: key.slice(key.indexOf(':') + 1), max: maxPerSide })} hint={`Add from ${partner.name}`} />
          </View>
          <AppText style={[common.muted, fit.over ? { color: colors.danger } : null]} testID="trade-fit">
            Your roster after: {fit.after}/{game.settings.roster_limit}
            {fit.over ? ` (cut ${fit.over} after the trade)` : fit.room ? ` (${fit.room} open)` : ''}
          </AppText>
        </>
      ) : null}

      {ready ? (
        <View style={common.stack} accessibilityLiveRegion="polite" accessibilityLabel="Verdict">
          {previewing && !verdict ? <SkeletonCard rows={2} /> : null}
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
              {verdict.decision === 'accept' ? (
                <Button
                  label="Send offer"
                  loading={sending}
                  onPress={() => {
                    const payload = simTradePayload(draft);
                    if (payload) void send(payload);
                  }}
                />
              ) : null}
            </>
          ) : null}
        </View>
      ) : null}

      {partner && sheetSide ? (
        <TradePickerSheet
          key={sheetSide}
          title={sheetSide === 'give' ? 'You send' : 'You receive'}
          subtitle={sheetSide === 'give' ? 'From your team' : `From ${partner.name}`}
          tone={sheetSide === 'give' ? 'danger' : 'success'}
          items={sheetItems}
          initialSelected={(sheetSide === 'give' ? draft.give : draft.get).map((id) => `${simIsPickId(id) ? 'pick' : 'player'}:${id}`)}
          max={maxPerSide}
          onApply={(keys) => {
            dispatch({ type: 'set', side: sheetSide, ids: selectedItems(sheetItems, keys).map((i) => i.id), max: maxPerSide });
            setSheetSide(null);
          }}
          onClose={() => setSheetSide(null)}
          hidden={viewing !== null}
          flexFilter={game.settings.slots.includes('FLEX')}
          valueLabel="Trade value"
          renderPlayerRow={(item, { on, blocked, toggle }) => {
            const player = item.ref as SimGamePlayer;
            return (
              <SimPlayerLine
                player={player}
                week={game.week}
                stats={simListStats(player, { adp: false, tradeValue: true })}
                selected={on}
                onOpen={setViewing}
                trailing={
                  <Pressable
                    onPress={toggle}
                    disabled={blocked}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: on, disabled: blocked }}
                    accessibilityLabel={`${on ? 'Remove' : 'Add'} ${player.name}`}
                    hitSlop={6}
                    style={{ width: 36, height: 36, borderRadius: 18, borderWidth: 2, borderColor: on ? colors.accent : colors.borderStrong, backgroundColor: on ? colors.accent : 'transparent', alignItems: 'center', justifyContent: 'center', opacity: blocked ? 0.45 : 1 }}
                  >
                    {on ? <Ionicons name="checkmark" size={18} color={colors.onAccent} /> : null}
                  </Pressable>
                }
              />
            );
          }}
        />
      ) : null}
      {viewing ? (
        <SimPlayerSheet
          gameId={gameId}
          startYear={game.settings.start_year}
          player={viewing}
          onClose={() => setViewing(null)}
          actions={<Button size="sm" variant="ghost" label="‹ Back to picker" onPress={() => setViewing(null)} />}
        />
      ) : null}
    </View>
  );
}

/** Trades tab: your inbox of AI offers and the offer builder. */
export function SimTradesTab({ ctx, seed, onSeedUsed }: { ctx: SimCtx; seed: SimTradeSeed | null; onSeedUsed: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [mode, setMode] = useState<'inbox' | 'build' | 'block'>(seed ? 'build' : 'inbox');
  // "Make an offer" from the block view seeds the builder locally (partner + the asset asked for).
  const [blockSeed, setBlockSeed] = useState<SimTradeSeed | null>(null);
  const hasBlock = (ctx.game.settings.block_v ?? 0) >= 1;
  const offers = ctx.game.pending?.inbox ?? 0;
  const [prevSeed, setPrevSeed] = useState(seed);
  if (seed && seed !== prevSeed) {
    setPrevSeed(seed);
    setMode('build');
  }
  return (
    <View style={common.stack}>
      <SegmentedTabBar<'inbox' | 'build' | 'block'>
        options={[
          { key: 'inbox', label: `Inbox${offers ? ` ${offers}` : ''}`, glyph: 'inbox' },
          { key: 'build', label: 'Make an offer', glyph: 'build' },
          ...(hasBlock ? [{ key: 'block' as const, label: 'My block', glyph: 'mine' as const }] : []),
        ]}
        active={mode}
        onChange={setMode}
      />
      {!ctx.game.can_trade && mode === 'inbox' ? <AppText style={common.muted}>{simTradeClosedReason(ctx.game)}</AppText> : null}
      {mode === 'inbox' ? (
        <Inbox ctx={ctx} />
      ) : mode === 'block' ? (
        <SimBlockView
          ctx={ctx}
          onMakeOffer={(partner, get) => {
            setBlockSeed({ partner, get });
            setMode('build');
          }}
        />
      ) : (
        <Builder
          ctx={ctx}
          seed={blockSeed ?? seed}
          onSeedUsed={() => {
            setBlockSeed(null);
            onSeedUsed();
          }}
        />
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
  });
}
