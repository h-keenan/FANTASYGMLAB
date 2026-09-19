import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import BrandedSpinner from '../components/BrandedSpinner';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import PositionBadge from '../components/PositionBadge';
import TierBadge from '../components/TierBadge';
import CircularProgressRing from '../components/CircularProgressRing';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeValueHero from '../components/TradeValueHero';
import {
  api,
  type DraftPickAsset,
  type RankedPlayer,
  type TradeVerdict,
} from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeAnalyzer'>;
type Side = 'send' | 'receive';
type AssetType = 'players' | 'picks';

interface SideChip {
  id: string;
  name: string;
}

type SearchItem =
  | { kind: 'player'; player: RankedPlayer }
  | { kind: 'pick'; pick: DraftPickAsset };

const MAX_SEARCH_RESULTS = 40;
const POSITION_FILTERS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];

const TONE_COLORS: Record<TradeVerdict['tone'], string> = {
  accept: colors.success,
  decline: colors.danger,
  counter: colors.accent,
  fair: colors.textSecondary,
};

// modules/trade_offer_analyzer.py's only three confidence strings — mapped
// to a ring fill so "how sure is the model" reads as a glanceable number
// instead of just an adjective next to a wall of text.
const CONFIDENCE_PERCENT: Record<string, number> = {
  'high confidence': 90,
  'moderate confidence': 60,
  'close call': 35,
};

function confidencePercent(confidence: string): number {
  return CONFIDENCE_PERCENT[confidence.toLowerCase()] ?? 50;
}

function playerScore(player: RankedPlayer): number {
  return typeof player.score === 'number' ? player.score : 0;
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Trade Analyzer needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
};

interface OtherTeam {
  rosterId: string;
  ownerName: string;
  playerIds: Set<string>;
}

const ALL_TEAMS_ID = '__all__';

export default function TradeAnalyzerScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [myRosterIds, setMyRosterIds] = useState<Set<string>>(new Set());
  const [myRosterId, setMyRosterId] = useState('');
  const [otherTeams, setOtherTeams] = useState<OtherTeam[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>(ALL_TEAMS_ID);
  const [rankings, setRankings] = useState<RankedPlayer[]>([]);
  const [allPicks, setAllPicks] = useState<DraftPickAsset[]>([]);
  const [sendIds, setSendIds] = useState<RankedPlayer[]>([]);
  const [receiveIds, setReceiveIds] = useState<RankedPlayer[]>([]);
  const [sendPicks, setSendPicks] = useState<DraftPickAsset[]>([]);
  const [receivePicks, setReceivePicks] = useState<DraftPickAsset[]>([]);
  const [activeSide, setActiveSide] = useState<Side>('send');
  const [assetType, setAssetType] = useState<AssetType>('players');
  const [positionFilter, setPositionFilter] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  // Read-only here: stance is changed from the header button only.
  const { strategy } = useGmStance(leagueId);
  const [analyzing, setAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<TradeVerdict | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const orbClearance = useOrbClearance();

  useScreenHeaderTitle(navigation, 'Trade Analyzer', leagueName);

  useEffect(() => {
    navigation.setOptions({ headerRight: () => <GmStanceHeaderButton leagueId={leagueId} /> });
  }, [navigation, leagueId]);

  // A verdict is analyzed under one stance, so it goes stale the moment the
  // stance changes. The removed in-page strategy pills cleared it inline;
  // the header button can change stance from anywhere, so watch the value
  // instead. (No-op on first render — `verdict` starts null.)
  useEffect(() => {
    setVerdict(null);
  }, [strategy]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [myRoster, rankingsResult, usersResult, rostersResult, picksResult] = await Promise.all([
          api.getMyRoster(leagueId),
          api.getLeagueRankings(leagueId, { lens: 'Dynasty', limit: 300 }),
          api.getLeagueUsers(leagueId),
          api.getLeagueRosters(leagueId),
          api.getLeagueDraftPicks(leagueId).catch(() => ({ ok: true as const, picks: [], reason: 'unavailable' })),
        ]);
        if (cancelled) return;

        let myId = '';
        if (myRoster.reason) {
          setNotReadyReason(myRoster.reason);
        } else {
          const players = Array.isArray(myRoster.roster?.players) ? (myRoster.roster!.players as unknown[]) : [];
          setMyRosterIds(new Set(players.map(String)));
          myId = String(myRoster.roster?.roster_id ?? '');
          setMyRosterId(myId);
        }
        setAllPicks(picksResult.picks);

        const usersById = new Map<string, string>();
        for (const user of usersResult.users) {
          const id = String(user.user_id ?? '');
          if (id) usersById.set(id, String(user.display_name ?? user.username ?? 'Unknown owner'));
        }
        const teams: OtherTeam[] = rostersResult.rosters
          .map((roster) => {
            const rosterId = String(roster.roster_id ?? '');
            const ownerId = String(roster.owner_id ?? '');
            const players = Array.isArray(roster.players) ? roster.players : [];
            return {
              rosterId,
              ownerName: usersById.get(ownerId) ?? 'Unclaimed team',
              playerIds: new Set(players.map(String)),
            };
          })
          .filter((team) => team.rosterId && team.rosterId !== myId);
        setOtherTeams(teams);

        setRankings(rankingsResult.players);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load trade data.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const selectedIds = useMemo(
    () => new Set([...sendIds, ...receiveIds].map((p) => p.player_id)),
    [sendIds, receiveIds],
  );
  const selectedPickIds = useMemo(
    () => new Set([...sendPicks, ...receivePicks].map((p) => p.pick_id)),
    [sendPicks, receivePicks],
  );
  const hasAnyAssets =
    sendIds.length > 0 || receiveIds.length > 0 || sendPicks.length > 0 || receivePicks.length > 0;

  const searchPool = useMemo(() => {
    if (activeSide === 'send') {
      return rankings.filter((p) => myRosterIds.has(p.player_id));
    }
    if (selectedTeamId === ALL_TEAMS_ID) {
      return rankings.filter((p) => !myRosterIds.has(p.player_id));
    }
    const team = otherTeams.find((t) => t.rosterId === selectedTeamId);
    if (!team) return [];
    return rankings.filter((p) => team.playerIds.has(p.player_id));
  }, [rankings, myRosterIds, otherTeams, selectedTeamId, activeSide]);

  const pickSearchPool = useMemo(() => {
    if (activeSide === 'send') {
      return allPicks.filter((p) => p.owner_roster_id === myRosterId);
    }
    if (selectedTeamId === ALL_TEAMS_ID) {
      return allPicks.filter((p) => p.owner_roster_id !== myRosterId);
    }
    return allPicks.filter((p) => p.owner_roster_id === selectedTeamId);
  }, [allPicks, myRosterId, selectedTeamId, activeSide]);

  const searchResults = useMemo<SearchItem[]>(() => {
    const query = search.trim().toLowerCase();
    if (assetType === 'picks') {
      return pickSearchPool
        .filter((p) => !selectedPickIds.has(p.pick_id))
        .filter((p) => !query || (p.label ?? '').toLowerCase().includes(query))
        .slice(0, MAX_SEARCH_RESULTS)
        .map((pick) => ({ kind: 'pick' as const, pick }));
    }
    return searchPool
      .filter((p) => !selectedIds.has(p.player_id))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query))
      .filter((p) => !positionFilter || (p.position ?? '').toUpperCase() === positionFilter)
      .slice(0, MAX_SEARCH_RESULTS)
      .map((player) => ({ kind: 'player' as const, player }));
  }, [assetType, searchPool, pickSearchPool, selectedIds, selectedPickIds, search, positionFilter]);

  const addPlayerToSide = (player: RankedPlayer) => {
    if (activeSide === 'send') {
      setSendIds((prev) => [...prev, player]);
    } else {
      setReceiveIds((prev) => [...prev, player]);
    }
    setVerdict(null);
  };

  const addPickToSide = (pick: DraftPickAsset) => {
    if (activeSide === 'send') {
      setSendPicks((prev) => [...prev, pick]);
    } else {
      setReceivePicks((prev) => [...prev, pick]);
    }
    setVerdict(null);
  };

  const removeFromSide = (side: Side, id: string) => {
    if (side === 'send') {
      setSendIds((prev) => prev.filter((p) => p.player_id !== id));
      setSendPicks((prev) => prev.filter((p) => p.pick_id !== id));
    } else {
      setReceiveIds((prev) => prev.filter((p) => p.player_id !== id));
      setReceivePicks((prev) => prev.filter((p) => p.pick_id !== id));
    }
    setVerdict(null);
  };

  const applyCounterAction = () => {
    const action = verdict?.counter_action;
    if (!action || action.asset_type !== 'player' || !action.player_id) return;
    if (action.action === 'remove_from_send') {
      setSendIds((prev) => prev.filter((p) => p.player_id !== action.player_id));
    } else if (action.action === 'add_to_receive') {
      const player = rankings.find((p) => p.player_id === action.player_id);
      if (!player) return;
      setReceiveIds((prev) => (prev.some((p) => p.player_id === player.player_id) ? prev : [...prev, player]));
    }
    setVerdict(null);
  };

  const analyze = async () => {
    setAnalyzeError(null);
    setAnalyzing(true);
    try {
      const result = await api.postTradeAnalyzer(leagueId, {
        sendPlayerIds: sendIds.map((p) => p.player_id),
        receivePlayerIds: receiveIds.map((p) => p.player_id),
        sendPickIds: sendPicks.map((p) => p.pick_id),
        receivePickIds: receivePicks.map((p) => p.pick_id),
        strategy,
        lens: 'Dynasty',
        partnerRosterId: selectedTeamId === ALL_TEAMS_ID ? '' : selectedTeamId,
      });
      if (result.verdict) {
        setVerdict(result.verdict);
      } else {
        setAnalyzeError(NOT_READY_MESSAGES[result.reason] ?? 'Could not analyze this trade.');
      }
    } catch (err) {
      setAnalyzeError(err instanceof Error ? err.message : 'Could not analyze this trade.');
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return <BrandedSpinner style={styles.center} />;
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't verify your roster in this league."}
        </Text>
      </View>
    );
  }

  const header = (
    <View>
      <Text style={styles.disclaimer}>
        The real accept / decline / counter verdict for {leagueName} — weighs asset value, starting
        lineup impact, roster needs, age, draft capital, and injury risk.
      </Text>

      <View style={styles.sidesRow}>
        <TradeSide
          label="You Send"
          dotColor={colors.danger}
          items={[
            ...sendIds.map((p) => ({ id: p.player_id, name: p.name ?? 'Unknown' })),
            ...sendPicks.map((p) => ({ id: p.pick_id, name: p.label ?? 'Draft pick' })),
          ]}
          active={activeSide === 'send'}
          onPressHeader={() => setActiveSide('send')}
          onRemove={(id) => removeFromSide('send', id)}
        />
        <TradeSide
          label="You Receive"
          dotColor={colors.successBright}
          items={[
            ...receiveIds.map((p) => ({ id: p.player_id, name: p.name ?? 'Unknown' })),
            ...receivePicks.map((p) => ({ id: p.pick_id, name: p.label ?? 'Draft pick' })),
          ]}
          active={activeSide === 'receive'}
          onPressHeader={() => setActiveSide('receive')}
          onRemove={(id) => removeFromSide('receive', id)}
        />
      </View>

      <View style={styles.assetTypeRow}>
        <TouchableOpacity
          style={[styles.pill, assetType === 'players' && styles.pillActive]}
          onPress={() => setAssetType('players')}
        >
          <Text style={[styles.pillText, assetType === 'players' && styles.pillTextActive]}>Players</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.pill, assetType === 'picks' && styles.pillActive]}
          onPress={() => setAssetType('picks')}
        >
          <Text style={[styles.pillText, assetType === 'picks' && styles.pillTextActive]}>Picks</Text>
        </TouchableOpacity>
      </View>

      {assetType === 'players' ? (
        <View style={styles.teamRow}>
          <TouchableOpacity
            style={[styles.pill, positionFilter === null && styles.pillActive]}
            onPress={() => setPositionFilter(null)}
          >
            <Text style={[styles.pillText, positionFilter === null && styles.pillTextActive]}>All</Text>
          </TouchableOpacity>
          {POSITION_FILTERS.map((position) => (
            <TouchableOpacity
              key={position}
              style={[styles.pill, positionFilter === position && styles.pillActive]}
              onPress={() => setPositionFilter(positionFilter === position ? null : position)}
            >
              <Text style={[styles.pillText, positionFilter === position && styles.pillTextActive]}>{position}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}

      {activeSide === 'receive' && otherTeams.length > 0 ? (
        <View style={styles.teamRow}>
          <TouchableOpacity
            style={[styles.pill, selectedTeamId === ALL_TEAMS_ID && styles.pillActive]}
            onPress={() => setSelectedTeamId(ALL_TEAMS_ID)}
          >
            <Text style={[styles.pillText, selectedTeamId === ALL_TEAMS_ID && styles.pillTextActive]}>
              All Teams
            </Text>
          </TouchableOpacity>
          {otherTeams.map((team) => (
            <TouchableOpacity
              key={team.rosterId}
              style={[styles.pill, selectedTeamId === team.rosterId && styles.pillActive]}
              onPress={() => setSelectedTeamId(team.rosterId)}
            >
              <Text
                style={[styles.pillText, selectedTeamId === team.rosterId && styles.pillTextActive]}
                numberOfLines={1}
              >
                {team.ownerName}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}

      <TouchableOpacity
        style={[styles.analyzeButton, !hasAnyAssets && styles.analyzeButtonDisabled]}
        onPress={analyze}
        disabled={analyzing || !hasAnyAssets}
      >
        {analyzing ? <ActivityIndicator color="#fff" /> : <Text style={styles.analyzeButtonText}>Analyze Trade</Text>}
      </TouchableOpacity>

      {analyzeError ? <Text style={styles.error}>{analyzeError}</Text> : null}
      {verdict ? (
        <VerdictCard
          verdict={verdict}
          sendIds={sendIds}
          receiveIds={receiveIds}
          leagueId={leagueId}
          leagueName={leagueName}
          partnerTeamName={otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? ''}
          onBuildCounter={applyCounterAction}
        />
      ) : null}

      <TextInput
        style={styles.searchInput}
        placeholder={
          activeSide === 'send'
            ? `Search your ${assetType === 'picks' ? 'picks' : 'roster'}`
            : selectedTeamId === ALL_TEAMS_ID
              ? `Search ${assetType === 'picks' ? 'picks' : 'players'} to receive`
              : `Search ${otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? 'team'}'s ${assetType === 'picks' ? 'picks' : 'roster'}`
        }
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
        placeholderTextColor={colors.textTertiary}
      />
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <GridBackground />
      <FlatList
      style={styles.container}
      data={searchResults}
      keyExtractor={(item) => (item.kind === 'player' ? item.player.player_id : item.pick.pick_id)}
      contentContainerStyle={[styles.resultsList, { paddingBottom: orbClearance }]}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={header}
      renderItem={({ item }) =>
        item.kind === 'player' ? (
          <TouchableOpacity style={styles.resultRow} onPress={() => addPlayerToSide(item.player)}>
            <PlayerAvatar playerId={item.player.player_id} size={36} tier={item.player.tier} style={styles.resultAvatar} />
            <View style={styles.resultInfo}>
              <Text style={styles.resultName} numberOfLines={1}>
                {item.player.name ?? 'Unknown'}
              </Text>
              <View style={styles.resultMetaRow}>
                <PositionBadge position={item.player.position} />
                <Text style={styles.resultMeta}>{item.player.team}</Text>
                <TierBadge storedTier={item.player.tier} />
              </View>
            </View>
            <Text style={styles.resultScore}>{Math.round(playerScore(item.player))}</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity style={styles.resultRow} onPress={() => addPickToSide(item.pick)}>
            <View style={styles.pickBadge}>
              <Ionicons name="albums-outline" size={18} color={colors.accent} />
            </View>
            <View style={styles.resultInfo}>
              <Text style={styles.resultName} numberOfLines={1}>
                {item.pick.label ?? 'Draft pick'}
              </Text>
              <View style={styles.resultMetaRow}>
                <Text style={styles.resultMeta}>
                  {[item.pick.pick_tier, item.pick.projected_pick_range].filter(Boolean).join(' · ')}
                </Text>
              </View>
            </View>
            <Text style={styles.resultScore}>{item.pick.score != null ? Math.round(item.pick.score) : '—'}</Text>
            {/* Tapping the row still adds the pick to the package — this is
                the escape hatch to "why is it worth that?" (the same Pick
                Detail the Draft Center's pick list opens) without giving up
                one-tap add. */}
            <TouchableOpacity
              style={styles.pickInfoButton}
              hitSlop={8}
              onPress={() =>
                navigation.navigate('PickDetail', { pick: item.pick, leagueId, leagueName })
              }
            >
              <Ionicons name="information-circle-outline" size={20} color={colors.textTertiary} />
            </TouchableOpacity>
          </TouchableOpacity>
        )
      }
      ListEmptyComponent={
        <Text style={styles.empty}>
          {assetType === 'players' && activeSide === 'send' && myRosterIds.size === 0
            ? 'No roster players found.'
            : search
              ? `No matching ${assetType === 'picks' ? 'picks' : 'players'}.`
              : 'Start typing to search.'}
        </Text>
      }
      />
    </KeyboardAvoidingView>
  );
}

function VerdictSection({
  icon,
  label,
  text,
  color,
}: {
  icon: React.ComponentProps<typeof Ionicons>['name'];
  label: string;
  text: string;
  color: string;
}) {
  if (!text) return null;
  return (
    <View style={styles.verdictSection}>
      <View style={styles.verdictSectionLabelRow}>
        <Ionicons name={icon} size={13} color={color} />
        <Text style={[styles.verdictLabel, { color }]}>{label}</Text>
      </View>
      <Text style={styles.verdictText}>{text}</Text>
    </View>
  );
}

function VerdictCard({
  verdict,
  sendIds,
  receiveIds,
  leagueId,
  leagueName,
  partnerTeamName,
  onBuildCounter,
}: {
  verdict: TradeVerdict;
  sendIds: RankedPlayer[];
  receiveIds: RankedPlayer[];
  leagueId: string;
  leagueName: string;
  partnerTeamName: string;
  onBuildCounter: () => void;
}) {
  const [shareOpen, setShareOpen] = useState(false);
  const toneColor = TONE_COLORS[verdict.tone];

  return (
    <View style={[styles.verdictCard, { borderLeftColor: toneColor }]}>
      <View style={styles.verdictHeaderRow}>
        <Text style={[styles.verdictBand, { color: toneColor }]}>{verdict.band}</Text>
        <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
          <Text style={styles.shareButtonText}>Share</Text>
        </TouchableOpacity>
      </View>

      {/* Quick visual: the same big color-coded value-change number the share
          PNG leads with, so the verdict reads at a glance without tapping
          Share. Rationale moved below the strip — it was cramped into the
          remaining width beside the ring before. */}
      <View style={styles.verdictHeroRow}>
        <TradeValueHero delta={verdict.value_delta} size="lg" style={styles.verdictValueHero} />
        <View style={styles.verdictRingGroup}>
          <CircularProgressRing
            percent={confidencePercent(verdict.confidence)}
            size={64}
            strokeWidth={6}
            color={toneColor}
          />
          <Text style={styles.verdictRingCaption} numberOfLines={1}>
            {verdict.confidence}
          </Text>
        </View>
      </View>
      <Text style={[styles.verdictText, styles.verdictRationale]}>{verdict.rationale}</Text>

      <VerdictSection icon="cash-outline" label="Value" text={verdict.value_summary} color={toneColor} />
      <VerdictSection icon="people-outline" label="Roster fit" text={verdict.roster_summary} color={toneColor} />
      <VerdictSection icon="compass-outline" label="Strategy fit" text={verdict.strategy_summary} color={toneColor} />
      <VerdictSection icon="warning-outline" label="Risk" text={verdict.risk_summary} color={colors.danger} />
      {verdict.counter_guidance ? (
        <>
          <VerdictSection
            icon="swap-horizontal-outline"
            label="Counter guidance"
            text={verdict.counter_guidance}
            color={colors.premium}
          />
          {verdict.counter_action && verdict.counter_action.asset_type === 'player' ? (
            <TouchableOpacity style={styles.counterButton} onPress={onBuildCounter}>
              <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
              <Text style={styles.counterButtonText}>Build the counter</Text>
            </TouchableOpacity>
          ) : null}
        </>
      ) : null}

      <TradeSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueId={leagueId}
        leagueName={leagueName}
        partnerTeamName={partnerTeamName}
        verdict={verdict}
        sendPlayers={sendIds}
        receivePlayers={receiveIds}
      />
    </View>
  );
}

function TradeSide({
  label,
  dotColor,
  items,
  active,
  onPressHeader,
  onRemove,
}: {
  label: string;
  dotColor: string;
  items: SideChip[];
  active: boolean;
  onPressHeader: () => void;
  onRemove: (id: string) => void;
}) {
  return (
    <View style={[styles.side, active && styles.sideActive]}>
      <TouchableOpacity style={styles.sideLabelRow} onPress={onPressHeader}>
        <View style={[styles.sideDot, { backgroundColor: dotColor }]} />
        <Text style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</Text>
      </TouchableOpacity>
      {items.map((item) => (
        <TouchableOpacity key={item.id} style={styles.chip} onPress={() => onRemove(item.id)}>
          <Text style={styles.chipText} numberOfLines={1}>
            {item.name}
          </Text>
          <Text style={styles.chipRemove}>{'×'}</Text>
        </TouchableOpacity>
      ))}
      {items.length === 0 ? <Text style={styles.sideEmpty}>Tap to add</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent', padding: spacing.lg },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 16 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  sidesRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  side: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: 'transparent',
    padding: spacing.md,
    minHeight: 80,
  },
  sideActive: { borderColor: colors.accent },
  sideLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm },
  sideDot: { width: 7, height: 7, borderRadius: 3.5 },
  sideLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  sideLabelActive: { color: colors.accent },
  sideEmpty: { fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.background,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    marginBottom: spacing.xs,
  },
  chipText: { flex: 1, fontSize: 13, color: colors.textPrimary, marginRight: spacing.xs },
  chipRemove: { fontSize: 14, color: colors.textSecondary, fontWeight: '700' },
  assetTypeRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.sm },
  teamRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: '#fff' },
  analyzeButton: {
    backgroundColor: colors.accent,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  analyzeButtonDisabled: { opacity: 0.5 },
  analyzeButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  verdictCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    borderLeftWidth: 4,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  verdictHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  verdictBand: { fontSize: 18, fontWeight: '800', marginBottom: spacing.xs },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
  },
  shareButtonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  counterButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    marginTop: spacing.sm,
    paddingVertical: spacing.sm,
    borderWidth: 1.5,
    borderColor: colors.accent,
  },
  counterButtonText: { fontSize: 13, fontWeight: '700', color: colors.accent },
  verdictHeroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  verdictValueHero: { flex: 1 },
  verdictRingGroup: { alignItems: 'center', gap: 4 },
  verdictRingCaption: {
    fontSize: 10,
    fontWeight: '600',
    color: colors.textSecondary,
    textTransform: 'capitalize',
  },
  verdictSection: { marginTop: spacing.sm },
  verdictSectionLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 5, marginBottom: 2 },
  verdictLabel: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  verdictText: { fontSize: 13, color: colors.textPrimary, lineHeight: 18, flex: 1 },
  // The rationale is a full-width block under the hero strip now, not a
  // flex child sharing a row with the confidence ring.
  verdictRationale: { flex: 0 },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  resultsList: { paddingBottom: spacing.xl },
  resultRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  resultAvatar: { marginRight: spacing.sm },
  pickInfoButton: { marginLeft: spacing.sm },
  pickBadge: {
    width: 36,
    height: 36,
    borderRadius: radii.pill,
    backgroundColor: colors.badgeBackground,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  resultInfo: { flex: 1, marginRight: spacing.sm },
  resultName: { fontSize: 15, fontWeight: '500', color: colors.textPrimary },
  resultMeta: { fontSize: 12, color: colors.textSecondary },
  resultMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  resultScore: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
});
