import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { useMutation } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import BrandedSpinner from './BrandedSpinner';
import Button from './Button';
import DraftPickAssetRow from './DraftPickAssetRow';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import Input from './Input';
import PlayerIdentityRow from './PlayerIdentityRow';
import PremiumLock from './PremiumLock';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type DraftPickAsset, type RankedPlayer, type TeamProfile, type ValuationLens } from '../lib/api';
import {
  buildVetoRequest,
  formatSigned,
  vetoBandTone,
  vetoHasResult,
  vetoPointsLine,
  vetoPostureLabel,
  vetoStatusMessage,
  vetoWorstPositionLine,
  VETO_BAND_LABEL,
  type VetoBand,
  type VetoCheckResponse,
  type VetoSide,
} from '../lib/commissionerIntegrity';
import { toUserErrorMessage } from '../lib/errorMessages';
import { spacing, type ThemeColors } from '../theme';

/**
 * Commissioner: Trade veto calculator. The commissioner enters a proposed
 * two-team trade (Sleeper does not publish pending trades) and the server
 * (modules/trade_veto.py) grades it for BOTH whole rosters at each team's own
 * posture, so a rebuilding team that sells a vet for youth or picks can lose
 * market value and still read fine. Nothing is computed here. A decision aid:
 * the league's rules decide. Mirrors web-next's VetoCalculator.
 */

interface TeamOption {
  rosterId: string;
  label: string;
  playerIds: Set<string>;
}

interface PoolData {
  teams: TeamOption[];
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
}

const MAX_RESULTS = 40;

type Styles = ReturnType<typeof createStyles>;

function useToneColor() {
  const { colors } = useThemeMode();
  return (band: VetoBand): string => {
    const tone = vetoBandTone(band);
    return tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : tone === 'danger' ? colors.danger : colors.textTertiary;
  };
}

function SideCard({ side, hurt, styles }: { side: VetoSide; hurt: boolean; styles: Styles }) {
  const { colors } = useThemeMode();
  const posture = vetoPostureLabel(side.posture);
  const worst = vetoWorstPositionLine(side);
  return (
    <AccentCard accent={hurt ? colors.warning : colors.glassBorder}>
      <View style={styles.cardHead}>
        <AppText style={[styles.teamName, styles.flex]}>{side.team_name}</AppText>
        {posture ? <ToneBadge label={posture} color={colors.textTertiary} /> : null}
      </View>
      <AppText style={styles.body}>Sends: {side.sends.length ? side.sends.join(', ') : 'nothing'}</AppText>
      <AppText style={styles.body}>Receives: {side.receives.length ? side.receives.join(', ') : 'nothing'}</AppText>
      <AppText style={styles.body}>Market value {formatSigned(side.market_delta)}</AppText>
      <AppText style={styles.body}>{vetoPointsLine(side)}</AppText>
      {worst ? <AppText style={styles.body}>{worst}</AppText> : null}
    </AccentCard>
  );
}

function VetoResult({ result, styles }: { result: VetoCheckResponse; styles: Styles }) {
  const toneColor = useToneColor();
  if (!vetoHasResult(result)) return null;
  const band = result.band as VetoBand;
  const color = toneColor(band);
  return (
    <View style={styles.stack}>
      <AccentCard accent={color}>
        <View style={styles.cardHead}>
          <View>
            <AppText style={[styles.score, { color }]}>{Math.round(result.outrage ?? 0)}</AppText>
            <AppText style={styles.muted}>out of 100</AppText>
          </View>
          <View style={styles.flex}>
            <View style={styles.badgeEnd}>
              <ToneBadge label={VETO_BAND_LABEL[band] ?? result.label ?? band} color={color} />
            </View>
          </View>
        </View>
        {result.advice ? <AppText style={styles.body}>{result.advice}</AppText> : null}
      </AccentCard>
      {(result.sides ?? []).map((side) => (
        <SideCard key={side.roster_id} side={side} hurt={String(side.roster_id) === String(result.hurt_roster_id)} styles={styles} />
      ))}
      {result.reasons?.length ? (
        <View style={styles.bullets}>
          <AppText style={styles.caption}>Why</AppText>
          {result.reasons.map((reason) => (
            <AppText key={reason} style={styles.bullet}>
              {'•'} {reason}
            </AppText>
          ))}
        </View>
      ) : null}
      {result.limits?.length ? (
        <View style={styles.bullets}>
          {result.limits.map((limit) => (
            <AppText key={limit} style={styles.muted}>
              {limit}
            </AppText>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function VetoBuilder({ leagueId, lens, pool, styles }: { leagueId: string; lens: string; pool: PoolData; styles: Styles }) {
  const [teamA, setTeamA] = useState('');
  const [teamB, setTeamB] = useState('');
  const [side, setSide] = useState<'a' | 'b'>('a');
  const [assetType, setAssetType] = useState<'players' | 'picks'>('players');
  const [search, setSearch] = useState('');
  const [aPlayers, setAPlayers] = useState<RankedPlayer[]>([]);
  const [bPlayers, setBPlayers] = useState<RankedPlayer[]>([]);
  const [aPicks, setAPicks] = useState<DraftPickAsset[]>([]);
  const [bPicks, setBPicks] = useState<DraftPickAsset[]>([]);

  const check = useMutation({
    mutationFn: (request: NonNullable<ReturnType<typeof buildVetoRequest>>) => api.postCommissionerVetoCheck(leagueId, request),
  });
  const { reset } = check;

  const activeTeam = pool.teams.find((t) => t.rosterId === (side === 'a' ? teamA : teamB));
  const nameOf = (id: string) => pool.teams.find((t) => t.rosterId === id)?.label ?? '';

  function chooseTeam(which: 'a' | 'b', id: string) {
    if (which === 'a') {
      setTeamA(id);
      setAPlayers([]);
      setAPicks([]);
      if (teamB === id) setTeamB('');
    } else {
      setTeamB(id);
      setBPlayers([]);
      setBPicks([]);
      if (teamA === id) setTeamA('');
    }
    reset();
  }

  const selectedPlayerIds = useMemo(() => new Set([...aPlayers, ...bPlayers].map((p) => p.player_id)), [aPlayers, bPlayers]);
  const selectedPickIds = useMemo(() => new Set([...aPicks, ...bPicks].map((p) => p.pick_id)), [aPicks, bPicks]);

  const playerResults = useMemo(() => {
    if (!activeTeam) return [];
    const q = search.trim().toLowerCase();
    return pool.rankings
      .filter((p) => activeTeam.playerIds.has(p.player_id) && !selectedPlayerIds.has(p.player_id))
      .filter((p) => !q || (p.name ?? '').toLowerCase().includes(q))
      .slice(0, MAX_RESULTS);
  }, [pool.rankings, activeTeam, search, selectedPlayerIds]);

  const pickResults = useMemo(() => {
    if (!activeTeam) return [];
    const q = search.trim().toLowerCase();
    return pool.picks
      .filter((p) => String(p.owner_roster_id) === activeTeam.rosterId && !selectedPickIds.has(p.pick_id))
      .filter((p) => !q || (p.label ?? '').toLowerCase().includes(q))
      .slice(0, MAX_RESULTS);
  }, [pool.picks, activeTeam, search, selectedPickIds]);

  const request = buildVetoRequest({
    rosterA: teamA,
    rosterB: teamB,
    aPlayers: aPlayers.map((p) => p.player_id),
    bPlayers: bPlayers.map((p) => p.player_id),
    aPicks: aPicks.map((p) => p.pick_id),
    bPicks: bPicks.map((p) => p.pick_id),
    lens,
  });

  const teamOptions = pool.teams.map((t) => ({ key: t.rosterId, label: t.label }));

  function sendList(which: 'a' | 'b') {
    const players = which === 'a' ? aPlayers : bPlayers;
    const picks = which === 'a' ? aPicks : bPicks;
    const setPlayers = which === 'a' ? setAPlayers : setBPlayers;
    const setPicks = which === 'a' ? setAPicks : setBPicks;
    const title = `${nameOf(which === 'a' ? teamA : teamB) || (which === 'a' ? 'Team A' : 'Team B')} sends`;
    return (
      <View style={styles.bullets}>
        <AppText style={styles.caption}>{title}</AppText>
        {players.length + picks.length === 0 ? <AppText style={styles.muted}>None selected</AppText> : null}
        {players.map((p, i) => (
          <PlayerIdentityRow
            key={p.player_id}
            playerId={p.player_id}
            name={p.name}
            position={p.position}
            team={p.team}
            tier={p.tier}
            overallRating={p.overall_rating}
            onPress={() => {
              setPlayers((prev) => prev.filter((x) => x.player_id !== p.player_id));
              reset();
            }}
            showDivider={i < players.length - 1 || picks.length > 0}
          />
        ))}
        {picks.map((p, i) => (
          <DraftPickAssetRow
            key={p.pick_id}
            pickId={p.pick_id}
            round={p.round}
            label={p.label}
            projectedRange={p.projected_pick_range}
            pickTier={p.pick_tier}
            onPress={() => {
              setPicks((prev) => prev.filter((x) => x.pick_id !== p.pick_id));
              reset();
            }}
            showDivider={i < picks.length - 1}
          />
        ))}
      </View>
    );
  }

  const result = check.data;
  let outcome: React.ReactNode = null;
  if (check.isPending) {
    outcome = <BrandedSpinner style={styles.spinner} />;
  } else if (check.error) {
    outcome = (
      <ErrorState
        title="Couldn't check this trade"
        message={toUserErrorMessage(check.error, 'Could not check this trade.')}
        onRetry={request ? () => check.mutate(request) : undefined}
      />
    );
  } else if (result) {
    if (result.status === 'locked') {
      outcome = (
        <PremiumLock
          feature="commissioner"
          title={result.upsell?.title || 'Check a trade before it processes'}
          description={result.upsell?.body || 'The trade veto calculator is a Pro feature: it grades a proposed trade for both whole rosters.'}
        />
      );
    } else if (result.status === 'ok' && vetoHasResult(result)) {
      outcome = <VetoResult result={result} styles={styles} />;
    } else if (result.status === 'error' || result.status === 'unavailable') {
      outcome = (
        <ErrorState
          title="Couldn't check this trade"
          message={vetoStatusMessage(result)}
          onRetry={request ? () => check.mutate(request) : undefined}
        />
      );
    } else {
      outcome = <EmptyState icon="swap-horizontal-outline" title="Can't check this trade" subtitle={vetoStatusMessage(result)} />;
    }
  }

  return (
    <View style={styles.stack}>
      <AppText style={styles.caption}>Team A</AppText>
      <SegmentedTabBar scrollable options={teamOptions} active={teamA} onChange={(k) => chooseTeam('a', k)} />
      <AppText style={styles.caption}>Team B</AppText>
      <SegmentedTabBar scrollable options={teamOptions.filter((o) => o.key !== teamA)} active={teamB} onChange={(k) => chooseTeam('b', k)} />

      {teamA && teamB ? (
        <>
          {sendList('a')}
          {sendList('b')}
          <SegmentedTabBar<'a' | 'b'>
            scrollable
            options={[
              { key: 'a', label: `${nameOf(teamA)} sends` },
              { key: 'b', label: `${nameOf(teamB)} sends` },
            ]}
            active={side}
            onChange={(k) => {
              setSide(k);
              setSearch('');
            }}
          />
          <SegmentedTabBar<'players' | 'picks'>
            options={[
              { key: 'players', label: 'Players' },
              { key: 'picks', label: 'Picks' },
            ]}
            active={assetType}
            onChange={setAssetType}
          />
          <Input value={search} onChangeText={setSearch} placeholder={assetType === 'picks' ? 'Search picks' : 'Search players'} autoCorrect={false} />
          <View>
            {assetType === 'picks'
              ? pickResults.length
                ? pickResults.map((p, i) => (
                    <DraftPickAssetRow
                      key={p.pick_id}
                      pickId={p.pick_id}
                      round={p.round}
                      label={p.label}
                      projectedRange={p.projected_pick_range}
                      pickTier={p.pick_tier}
                      onPress={() => {
                        (side === 'a' ? setAPicks : setBPicks)((prev) => [...prev, p]);
                        reset();
                      }}
                      showDivider={i < pickResults.length - 1}
                    />
                  ))
                : <AppText style={styles.muted}>No picks to add.</AppText>
              : playerResults.length
                ? playerResults.map((p, i) => (
                    <PlayerIdentityRow
                      key={p.player_id}
                      playerId={p.player_id}
                      name={p.name}
                      position={p.position}
                      team={p.team}
                      tier={p.tier}
                      overallRating={p.overall_rating}
                      onPress={() => {
                        (side === 'a' ? setAPlayers : setBPlayers)((prev) => [...prev, p]);
                        reset();
                      }}
                      showDivider={i < playerResults.length - 1}
                    />
                  ))
                : <AppText style={styles.muted}>No players to add.</AppText>}
          </View>
          <Button label="Check this trade" onPress={() => request && check.mutate(request)} disabled={!request} loading={check.isPending} />
        </>
      ) : (
        <AppText style={styles.muted}>Pick the two teams in the trade, then add what each one sends.</AppText>
      )}
      {outcome}
    </View>
  );
}

export default function VetoCalculator({ leagueId, lens }: { leagueId: string; lens: ValuationLens | string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const [pool, setPool] = useState<PoolData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    (async () => {
      try {
        const [rankings, picks, rosters, profiles] = await Promise.all([
          api.getLeagueRankings(leagueId, { lens: lens as ValuationLens, limit: 300 }),
          api.getLeagueDraftPicks(leagueId, { lens: lens as ValuationLens }).catch(() => ({ picks: [] as DraftPickAsset[] })),
          api.getLeagueRosters(leagueId),
          api.getLeagueTeamProfiles(leagueId).catch(() => ({ profiles: {} as Record<string, TeamProfile> })),
        ]);
        if (cancelled) return;
        const teams = rosters.rosters
          .map((roster) => {
            const rosterId = String(roster.roster_id ?? '');
            const players = Array.isArray(roster.players) ? roster.players : [];
            const profile = profiles.profiles?.[rosterId];
            const label = [profile?.team_name, profile?.owner_name].filter(Boolean).join(' · ') || `Team ${rosterId}`;
            return { rosterId, label, playerIds: new Set(players.map(String)) };
          })
          .filter((t) => t.rosterId)
          .sort((a, b) => a.label.localeCompare(b.label));
        setPool({ teams, rankings: rankings.players, picks: picks.picks });
      } catch (err) {
        if (!cancelled) setError(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, leagueId, lens, attempt]);

  let body: React.ReactNode;
  if (!open) {
    body = <Button label="Check a proposed trade" variant="secondary" onPress={() => setOpen(true)} />;
  } else if (error) {
    body = (
      <ErrorState
        title="Couldn't load the league's teams"
        message={toUserErrorMessage(error, 'Could not load the league’s teams.')}
        onRetry={() => setAttempt((n) => n + 1)}
      />
    );
  } else if (loading || !pool) {
    body = <BrandedSpinner style={styles.spinner} />;
  } else if (pool.teams.length < 2) {
    body = <EmptyState icon="people-outline" title="Not enough teams" subtitle="This league needs at least two teams with rosters." />;
  } else {
    body = <VetoBuilder leagueId={leagueId} lens={lens} pool={pool} styles={styles} />;
  }

  return (
    <View style={styles.section}>
      <SectionHeading
        title="Trade veto calculator"
        caption="Enter a proposed trade and see how lopsided it reads for each team's whole roster, at that team's own direction. A decision aid: the league's rules decide."
      />
      {body}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { marginTop: spacing.xl, paddingTop: spacing.lg, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.glassBorder, gap: spacing.md },
    stack: { gap: spacing.md },
    flex: { flex: 1 },
    spinner: { padding: spacing.xl },
    cardHead: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', gap: spacing.sm },
    badgeEnd: { alignItems: 'flex-end' },
    score: { fontSize: 40, fontWeight: '900', lineHeight: 44 },
    teamName: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 14, color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    caption: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.8, color: colors.textTertiary },
    bullets: { gap: spacing.xs },
    bullet: { fontSize: 13, color: colors.textSecondary },
  });
}
