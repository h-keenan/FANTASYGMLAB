import React, { useEffect, useMemo, useReducer, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import FadeInView from './FadeInView';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPlayerLine, SimPopIn, SimStat, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
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
  type SimTradeVerdict,
} from '../lib/simGame';
import type { ThemeColors } from '../theme';

function PlayerList({ players }: { players: SimGamePlayer[] }) {
  return (
    <View>
      {players.map((p) => (
        <SimPlayerLine key={p.id} player={p} trailing={<SimStat label="Proj" value={simFmtPts(p.projection)} />} />
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
    <View style={common.stack}>
      {items.map((item) => (
        <FadeInView key={item.id}>
          <AccentCard accent={colors.premium}>
            <View style={common.rowBetween}>
              <AppText style={[common.bodyStrong, common.grow]}>{item.from.name}</AppText>
              <ToneBadge label={`Expires week ${item.expires_week}`} color={colors.textSecondary} size="xs" />
            </View>
            {item.message ? <AppText style={common.small}>{item.message}</AppText> : null}
            <AppText style={styles.kicker}>You give</AppText>
            <PlayerList players={item.you_give} />
            <AppText style={styles.kicker}>You get</AppText>
            <PlayerList players={item.you_get} />
            <View style={common.row}>
              <Button size="sm" label="Accept" loading={busyId === item.id} disabled={!ctx.game.can_trade} onPress={() => respond(item, 'accept')} />
              <Button size="sm" variant="secondary" label="Decline" disabled={busyId === item.id} onPress={() => respond(item, 'decline')} />
            </View>
          </AccentCard>
        </FadeInView>
      ))}
    </View>
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
            <AppText style={common.title}>{simTradeDecisionLabel(verdict.decision)}</AppText>
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
              <AppText style={common.bodyStrong}>Their counter</AppText>
              <AppText style={styles.kicker}>You give</AppText>
              <PlayerList players={verdict.counter.give} />
              <AppText style={styles.kicker}>You get</AppText>
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
    dispatch({ type: 'toggle', side: 'get', id: seed.get });
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
  // Once a partner is chosen the list collapses to that team, so the offer and verdict stay in reach.
  const visibleTeams = partner && !changingPartner ? teamOptions.filter((t) => t.team_id === partner.team_id) : teamOptions;

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

  return (
    <View style={common.stack}>
      <View style={common.stack}>
        <SectionHeading title="Partner" caption="Tap a team to see its roster and how it likes to trade." />
        {visibleTeams.map((team) => (
          <Pressable
            key={team.team_id}
            accessibilityRole="button"
            accessibilityState={{ selected: draft.partner === team.team_id }}
            onPress={() => {
              dispatch({ type: 'partner', teamId: team.team_id });
              setChangingPartner(false);
            }}
          >
            <AccentCard accent={draft.partner === team.team_id ? colors.accent : colors.borderStrong} compact>
              <View style={common.rowBetween}>
                <AppText style={[common.bodyStrong, common.grow]}>{team.name}</AppText>
                <ToneBadge label={team.persona.label} color={colors.accent} size="xs" />
              </View>
              {draft.partner === team.team_id ? <AppText style={common.small}>{team.persona.blurb}</AppText> : null}
            </AccentCard>
          </Pressable>
        ))}
        {partner && !changingPartner ? <Button size="sm" variant="ghost" label="Change partner" onPress={() => setChangingPartner(true)} style={{ alignSelf: 'flex-start' }} /> : null}
      </View>

      {partner ? (
        <>
          <View>
            <SectionHeading title="You give" caption={`Up to ${SIM_TRADE_MAX_PER_SIDE}. ${draft.give.length} selected.`} />
            {mine
              .filter((p) => simTradable(p.pos))
              .map((p) => (
                <SimPlayerLine
                  key={p.id}
                  player={p}
                  selected={draft.give.includes(p.id)}
                  trailing={
                    <>
                      <SimStat label="Value" value={Math.round(p.value)} />
                      <Button size="sm" variant={draft.give.includes(p.id) ? 'primary' : 'secondary'} label={draft.give.includes(p.id) ? 'Giving' : 'Give'} onPress={() => dispatch({ type: 'toggle', side: 'give', id: p.id })} />
                    </>
                  }
                />
              ))}
          </View>
          <View>
            <SectionHeading title="You get" caption={`${partner.name}'s roster. ${draft.get.length} selected.`} />
            {partnerRoster
              .filter((p) => simTradable(p.pos))
              .map((p) => (
                <SimPlayerLine
                  key={p.id}
                  player={p}
                  selected={draft.get.includes(p.id)}
                  trailing={
                    <>
                      <SimStat label="Value" value={Math.round(p.value)} />
                      <Button size="sm" variant={draft.get.includes(p.id) ? 'primary' : 'secondary'} label={draft.get.includes(p.id) ? 'Getting' : 'Get'} onPress={() => dispatch({ type: 'toggle', side: 'get', id: p.id })} />
                    </>
                  }
                />
              ))}
          </View>
        </>
      ) : null}

      {ready ? (
        <View style={common.stack} accessibilityLiveRegion="polite">
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
