import React, { useContext, useEffect, useMemo, useReducer, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import FadeInView from './FadeInView';
import Input from './Input';
import { ReviewGlyphChip } from './SeasonReviewSections';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import SimCrest from './SimCrest';
import SimGlyph from './SimGlyph';
import { SimPlayerChip, SimPlayerLine, SimPopIn, SimSideLabel, SimStat, SimTeamOpenContext, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { SIM_ASSET_ALL, simFilterGroups, simGroupByPosition, simSideSummary, simTradeFit, type SimAssetGroup } from '../lib/simLayout';
import {
  SIM_TRADE_EMPTY,
  SIM_TRADE_MAX_PER_SIDE,
  simFmtPts,
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
  type SimTradeVerdict,
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

function PlayerList({ players }: { players: SimGamePlayer[] }) {
  return (
    <View>
      {players.map((p) => (
        <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingVertical: 4 }}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <SimPlayerChip player={p} size={28} quick />
          </View>
          <SimStat label="Proj" value={simFmtPts(p.projection)} />
        </View>
      ))}
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
    const body = await call(() => api.respondSimInbox(gameId, item.id, action));
    setBusyId(null);
    if (body) {
      setItems(body.items ?? []);
      ctx.notify(action === 'accept' && body.executed ? `Trade done with ${item.from.name}.` : `Declined ${item.from.name}'s offer.`, action === 'accept' ? 'success' : 'muted');
      ctx.bump();
      await ctx.reloadGame();
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
        <OfferCard key={item.id} item={item} defaultOpen={index === 0} busy={busyId === item.id} canTrade={Boolean(ctx.game.can_trade)} onRespond={respond} />
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
  const names = (list: SimGamePlayer[]) => list.map((p) => p.name.split(' ').slice(-1)[0]).join(', ');
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
              <ToneBadge label={`Wk ${item.expires_week}`} color={colors.warning} size="xs" />
              <AppText style={common.muted} accessibilityElementsHidden>
                {open ? '\u2212' : '+'}
              </AppText>
            </View>
          </View>
          <AppText style={common.small}>
            <AppText style={{ fontWeight: '800', color: colors.danger, fontSize: 13 }}>Give</AppText> {names(item.you_give)} ({give.value}){' \u00b7 '}
            <AppText style={{ fontWeight: '800', color: colors.success, fontSize: 13 }}>Get</AppText> {names(item.you_get)} ({get.value})
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
function Builder({ ctx, seed, onSeedUsed }: { ctx: SimCtx; seed: { partner: string; get: string } | null; onSeedUsed: () => void }) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [draft, dispatch] = useReducer(simTradeReducer, SIM_TRADE_EMPTY);
  const [teams, setTeams] = useState<SimLeagueTeam[] | null>(null);
  const [teamsFailed, setTeamsFailed] = useState(false);
  const [teamsAttempt, setTeamsAttempt] = useState(0);
  const [partnerLoaded, setPartnerLoaded] = useState<{ partner: string; players: SimGamePlayer[] } | null>(null);
  const [mine, setMine] = useState<SimGamePlayer[]>([]);
  // The verdict is stored with the offer it answers, so a changed offer
  // never shows the old verdict.
  const [verdictFor, setVerdictFor] = useState<{ key: string; verdict: SimTradeVerdict | null } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [side, setSide] = useState<'give' | 'get'>(seed ? 'get' : 'give');
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
        if (!cancelled) setTeamsFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, teamsAttempt]);

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((b) => !cancelled && setMine(b.players ?? []))
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
      .then((b) => !cancelled && setPartnerLoaded({ partner: partnerId, players: b.players ?? [] }))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [gameId, draft.partner, ctx.tick]);
  const partnerRoster = partnerLoaded && partnerLoaded.partner === draft.partner ? partnerLoaded.players : [];

  // "Trade for him" from the Players tab: preselect the partner and the player.
  useEffect(() => {
    if (!seed) return;
    dispatch({ type: 'partner', teamId: seed.partner });
    if (seed.get) dispatch({ type: 'toggle', side: 'get', id: seed.get });
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
      ctx.notify('Trade done. The players are on their new rosters.', 'success');
      dispatch({ type: 'clear' });
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
    return <EmptyState icon="lock-closed-outline" title="Trades are closed" subtitle={closed} />;
  }
  if (teamsFailed) {
    return <ErrorState title="Teams did not load" message="Check your connection and try again." onRetry={() => {
          setTeamsFailed(false);
          setTeamsAttempt((n) => n + 1);
        }} />;
  }
  if (!teams) return <SkeletonCard rows={4} />;

  const giveSelected = mine.filter((p) => draft.give.includes(p.id));
  const getSelected = partnerRoster.filter((p) => draft.get.includes(p.id));
  const fit = simTradeFit(mine.length, game.settings.roster_limit, giveSelected.length, getSelected.length);
  const pool = side === 'give' ? mine : partnerRoster;
  const groups = simGroupByPosition(pool.filter((p) => simTradable(p.pos)), simPositionsFor(game.settings.slots));

  return (
    <View style={common.stack}>
      <View style={common.tight} accessibilityLabel="Trade partner">
        <SectionHeading title="Partner" caption={partner ? undefined : 'Pick a team to trade with.'} />
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingBottom: 4 }} accessibilityLabel="Teams">
          {teamOptions.map((team) => {
            const active = draft.partner === team.team_id;
            return (
              <Pressable
                key={team.team_id}
                accessibilityRole="button"
                accessibilityLabel={`Trade with ${team.name}`}
                accessibilityState={{ selected: active }}
                onPress={() => dispatch({ type: 'partner', teamId: team.team_id })}
                style={{
                  width: 80,
                  alignItems: 'center',
                  gap: 4,
                  padding: 6,
                  borderRadius: 12,
                  borderWidth: 1,
                  borderColor: active ? colors.accent : colors.border,
                  backgroundColor: active ? colors.accentMuted : 'transparent',
                }}
              >
                <SimCrest name={team.name} size={32} />
                <AppText style={{ fontSize: 12, fontWeight: '700', lineHeight: 14, textAlign: 'center', color: colors.textPrimary }} numberOfLines={2}>
                  {team.name}
                </AppText>
              </Pressable>
            );
          })}
        </ScrollView>
        {partner ? (
          <View style={common.rowBetween}>
            <View style={[common.row, { flex: 1, minWidth: 0 }]}>
              <ToneBadge label={partner.persona.label} color={colors.accent} size="xs" />
              <AppText style={[common.small, { flexShrink: 1 }]} numberOfLines={1}>
                {partner.persona.blurb}
              </AppText>
            </View>
            <ScoutButton teamId={partner.team_id} name={partner.name} />
          </View>
        ) : null}
      </View>

      {partner ? (
        <>
          <View style={{ flexDirection: 'row', gap: 8 }} accessibilityLabel="Offer">
            <SideSummary label="You send" tone="danger" active={side === 'give'} onSelect={() => setSide('give')} players={giveSelected} onRemove={(id) => dispatch({ type: 'toggle', side: 'give', id })} />
            <SideSummary label="You receive" tone="success" active={side === 'get'} onSelect={() => setSide('get')} players={getSelected} onRemove={(id) => dispatch({ type: 'toggle', side: 'get', id })} />
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

      {partner ? (
        <AssetPicker
          key={side}
          label={side === 'give' ? 'Your roster' : `${partner.name}'s roster`}
          groups={groups}
          selected={side === 'give' ? draft.give : draft.get}
          verb={side === 'give' ? 'Give' : 'Get'}
          doneVerb={side === 'give' ? 'Giving' : 'Getting'}
          onToggle={(id) => dispatch({ type: 'toggle', side, id })}
          onOpen={ctx.openPlayer}
        />
      ) : null}
    </View>
  );
}

/** One side of the offer as a compact summary: count, total value and the chosen players (tap the x to remove). */
function SideSummary({ label, tone, active, onSelect, players, onRemove }: { label: string; tone: 'danger' | 'success'; active: boolean; onSelect: () => void; players: SimGamePlayer[]; onRemove: (id: string) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const sum = simSideSummary(players);
  const color = simToneColor(tone, colors);
  return (
    <View
      style={{ flex: 1, minWidth: 0, gap: 6, padding: 8, borderRadius: 12, borderWidth: 1, borderColor: active ? colors.accent : colors.glassBorder, backgroundColor: colors.glass }}
      testID={`trade-side-${tone === 'danger' ? 'give' : 'get'}`}
    >
      <Pressable onPress={onSelect} accessibilityRole="button" accessibilityState={{ selected: active }} accessibilityLabel={`${label}: ${sum.count} selected. Choose players`} style={{ minHeight: 44, justifyContent: 'center', gap: 2 }}>
        <View style={common.row}>
          <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: color }} />
          <AppText style={{ fontSize: 12, fontWeight: '800', textTransform: 'uppercase', color: active ? colors.accent : colors.textTertiary }}>{label}</AppText>
        </View>
        <AppText style={{ fontSize: 14, fontWeight: '800', color: colors.textPrimary }}>
          {sum.count} <AppText style={common.muted}>· value {sum.value}</AppText>
        </AppText>
      </Pressable>
      {players.length === 0 ? (
        <AppText style={[common.muted, { fontStyle: 'italic' }]}>Tap to add</AppText>
      ) : (
        players.map((p) => (
          <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <SimPlayerChip player={p} size={20} quick hidePosition />
            </View>
            <Pressable onPress={() => onRemove(p.id)} accessibilityRole="button" accessibilityLabel={`Remove ${p.name}`} hitSlop={8} style={{ minWidth: 28, minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
              <AppText style={{ fontSize: 16, fontWeight: '700', color: colors.textTertiary }}>×</AppText>
            </Pressable>
          </View>
        ))
      )}
    </View>
  );
}

/**
 * The trade picker: position chips (plus any other group, e.g. a future
 * "Picks"), a search box and the roster in collapsible groups, not one flat
 * list. Groups are generic (kind: 'player' | 'pick'), so draft picks slot in
 * as another group without changing this component.
 */
function AssetPicker({ label, groups, selected, verb, doneVerb, onToggle, onOpen }: { label: string; groups: SimAssetGroup<SimGamePlayer>[]; selected: string[]; verb: string; doneVerb: string; onToggle: (id: string) => void; onOpen: (p: SimGamePlayer) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [filter, setFilter] = useState(SIM_ASSET_ALL);
  const [search, setSearch] = useState('');
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const shown = simFilterGroups(groups, filter, search);
  const single = filter !== SIM_ASSET_ALL || search.trim() !== '';
  return (
    <View style={common.stack} accessibilityLabel={label}>
      <SectionHeading title={label} caption={`Up to ${SIM_TRADE_MAX_PER_SIDE}. ${selected.length} selected.`} />
      <SegmentedTabBar<string> scrollable options={[{ key: SIM_ASSET_ALL, label: 'All' }, ...groups.map((g) => ({ key: g.key, label: g.label }))]} active={filter} onChange={setFilter} />
      <Input value={search} onChangeText={setSearch} placeholder="Search players" accessibilityLabel="Search players" returnKeyType="search" autoCorrect={false} autoCapitalize="none" clearButtonMode="while-editing" />
      {shown.length === 0 ? (
        <AppText style={common.muted}>{search ? 'No matching players.' : 'No tradable players here.'}</AppText>
      ) : (
        shown.map((group, index) => {
          const open = toggled[group.key] ?? (single || index === 0);
          const chosen = group.items.filter((p) => selected.includes(p.id)).length;
          return (
            <View key={group.key} style={{ borderRadius: 12, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glass, overflow: 'hidden' }} accessibilityLabel={`${group.label} group`}>
              <Pressable
                onPress={() => setToggled((prev) => ({ ...prev, [group.key]: !open }))}
                accessibilityRole="button"
                accessibilityState={{ expanded: open }}
                accessibilityLabel={`${group.label}, ${group.items.length} players${chosen ? `, ${chosen} selected` : ''}`}
                style={{ minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12 }}
              >
                <AppText style={common.bodyStrong}>{group.label}</AppText>
                <ToneBadge label={`${group.items.length}`} color={colors.accent} size="xs" />
                {chosen > 0 ? <ToneBadge label={`${chosen} selected`} color={colors.success} size="xs" /> : null}
                <AppText style={[common.muted, { marginLeft: 'auto' }]} accessibilityElementsHidden>
                  {open ? '\u2212' : '+'}
                </AppText>
              </Pressable>
              {open ? (
                <View style={{ paddingHorizontal: 8, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border }}>
                  {group.items.map((p) => {
                    const on = selected.includes(p.id);
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
                            <Button size="sm" variant={on ? 'primary' : 'secondary'} label={on ? doneVerb : verb} onPress={() => onToggle(p.id)} />
                          </>
                        }
                      />
                    );
                  })}
                </View>
              ) : null}
            </View>
          );
        })
      )}
    </View>
  );
}

/** Trades tab: your inbox of AI offers and the offer builder. */
export function SimTradesTab({ ctx, seed, onSeedUsed }: { ctx: SimCtx; seed: { partner: string; get: string } | null; onSeedUsed: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [mode, setMode] = useState<'inbox' | 'build'>(seed ? 'build' : 'inbox');
  const offers = ctx.game.pending?.inbox ?? 0;
  const [prevSeed, setPrevSeed] = useState(seed);
  if (seed && seed !== prevSeed) {
    setPrevSeed(seed);
    setMode('build');
  }
  return (
    <View style={common.stack}>
      <SegmentedTabBar<'inbox' | 'build'>
        options={[
          { key: 'inbox', label: `Inbox${offers ? ` ${offers}` : ''}` },
          { key: 'build', label: 'Make an offer' },
        ]}
        active={mode}
        onChange={setMode}
      />
      {!ctx.game.can_trade && mode === 'inbox' ? <AppText style={common.muted}>{simTradeClosedReason(ctx.game)}</AppText> : null}
      {mode === 'inbox' ? <Inbox ctx={ctx} /> : <Builder ctx={ctx} seed={seed} onSeedUsed={onSeedUsed} />}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
  });
}
