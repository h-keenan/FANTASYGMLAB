import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import PlayerAvatar from '../components/PlayerAvatar';
import TierBadge from '../components/TierBadge';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import { api, type RankedPlayer, type TeamStrategy, type TradeVerdict } from '../lib/api';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeAnalyzer'>;
type Side = 'send' | 'receive';

const MAX_SEARCH_RESULTS = 40;

const STRATEGIES: Array<{ value: TeamStrategy; label: string }> = [
  { value: 'contender', label: 'Contender' },
  { value: 'fringe_contender', label: 'Fringe Contender' },
  { value: 'retool', label: 'Retool' },
  { value: 'rebuild', label: 'Rebuild' },
  { value: 'tank', label: 'Tank' },
];

const TONE_COLORS: Record<TradeVerdict['tone'], string> = {
  accept: colors.success,
  decline: colors.danger,
  counter: colors.accent,
  fair: colors.textSecondary,
};

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
  const [otherTeams, setOtherTeams] = useState<OtherTeam[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>(ALL_TEAMS_ID);
  const [rankings, setRankings] = useState<RankedPlayer[]>([]);
  const [sendIds, setSendIds] = useState<RankedPlayer[]>([]);
  const [receiveIds, setReceiveIds] = useState<RankedPlayer[]>([]);
  const [activeSide, setActiveSide] = useState<Side>('send');
  const [search, setSearch] = useState('');
  const [strategy, setStrategy] = useState<TeamStrategy>('retool');
  const [analyzing, setAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<TradeVerdict | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Trade Analyzer', leagueName);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [myRoster, rankingsResult, usersResult, rostersResult] = await Promise.all([
          api.getMyRoster(leagueId),
          api.getLeagueRankings(leagueId, { lens: 'Dynasty', limit: 300 }),
          api.getLeagueUsers(leagueId),
          api.getLeagueRosters(leagueId),
        ]);
        if (cancelled) return;

        let myId = '';
        if (myRoster.reason) {
          setNotReadyReason(myRoster.reason);
        } else {
          const players = Array.isArray(myRoster.roster?.players) ? (myRoster.roster!.players as unknown[]) : [];
          setMyRosterIds(new Set(players.map(String)));
          myId = String(myRoster.roster?.roster_id ?? '');
        }

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

  const searchResults = useMemo(() => {
    const query = search.trim().toLowerCase();
    return searchPool
      .filter((p) => !selectedIds.has(p.player_id))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query))
      .slice(0, MAX_SEARCH_RESULTS);
  }, [searchPool, selectedIds, search]);

  const addToSide = (player: RankedPlayer) => {
    if (activeSide === 'send') {
      setSendIds((prev) => [...prev, player]);
    } else {
      setReceiveIds((prev) => [...prev, player]);
    }
    setVerdict(null);
  };

  const removeFromSide = (side: Side, playerId: string) => {
    if (side === 'send') {
      setSendIds((prev) => prev.filter((p) => p.player_id !== playerId));
    } else {
      setReceiveIds((prev) => prev.filter((p) => p.player_id !== playerId));
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
        strategy,
        lens: 'Dynasty',
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
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
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
          players={sendIds}
          active={activeSide === 'send'}
          onPressHeader={() => setActiveSide('send')}
          onRemove={(id) => removeFromSide('send', id)}
        />
        <TradeSide
          label="You Receive"
          players={receiveIds}
          active={activeSide === 'receive'}
          onPressHeader={() => setActiveSide('receive')}
          onRemove={(id) => removeFromSide('receive', id)}
        />
      </View>

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

      <View style={styles.strategyRow}>
        {STRATEGIES.map((option) => (
          <TouchableOpacity
            key={option.value}
            style={[styles.pill, strategy === option.value && styles.pillActive]}
            onPress={() => {
              setStrategy(option.value);
              setVerdict(null);
            }}
          >
            <Text style={[styles.pillText, strategy === option.value && styles.pillTextActive]}>
              {option.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TouchableOpacity
        style={[styles.analyzeButton, (sendIds.length === 0 && receiveIds.length === 0) && styles.analyzeButtonDisabled]}
        onPress={analyze}
        disabled={analyzing || (sendIds.length === 0 && receiveIds.length === 0)}
      >
        {analyzing ? <ActivityIndicator color="#fff" /> : <Text style={styles.analyzeButtonText}>Analyze Trade</Text>}
      </TouchableOpacity>

      {analyzeError ? <Text style={styles.error}>{analyzeError}</Text> : null}
      {verdict ? <VerdictCard verdict={verdict} sendIds={sendIds} receiveIds={receiveIds} leagueName={leagueName} /> : null}

      <TextInput
        style={styles.searchInput}
        placeholder={
          activeSide === 'send'
            ? 'Search your roster'
            : selectedTeamId === ALL_TEAMS_ID
              ? 'Search players to receive'
              : `Search ${otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? 'team'}'s roster`
        }
        value={search}
        onChangeText={setSearch}
        autoCapitalize="none"
        placeholderTextColor={colors.textTertiary}
      />
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      data={searchResults}
      keyExtractor={(item) => item.player_id}
      contentContainerStyle={styles.resultsList}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={header}
      renderItem={({ item }) => (
        <TouchableOpacity style={styles.resultRow} onPress={() => addToSide(item)}>
          <PlayerAvatar playerId={item.player_id} size={36} tier={item.tier} style={styles.resultAvatar} />
          <View style={styles.resultInfo}>
            <Text style={styles.resultName} numberOfLines={1}>
              {item.name ?? 'Unknown'}
            </Text>
            <View style={styles.resultMetaRow}>
              <Text style={styles.resultMeta}>
                {[item.position, item.team].filter(Boolean).join(' · ')}
              </Text>
              <TierBadge storedTier={item.tier} />
            </View>
          </View>
          <Text style={styles.resultScore}>{Math.round(playerScore(item))}</Text>
        </TouchableOpacity>
      )}
      ListEmptyComponent={
        <Text style={styles.empty}>
          {activeSide === 'send' && myRosterIds.size === 0
            ? 'No roster players found.'
            : search
              ? 'No matching players.'
              : 'Start typing to search.'}
        </Text>
      }
    />
  );
}

function VerdictCard({
  verdict,
  sendIds,
  receiveIds,
  leagueName,
}: {
  verdict: TradeVerdict;
  sendIds: RankedPlayer[];
  receiveIds: RankedPlayer[];
  leagueName: string;
}) {
  const [shareOpen, setShareOpen] = useState(false);

  return (
    <View style={[styles.verdictCard, { borderLeftColor: TONE_COLORS[verdict.tone] }]}>
      <View style={styles.verdictHeaderRow}>
        <Text style={[styles.verdictBand, { color: TONE_COLORS[verdict.tone] }]}>{verdict.band}</Text>
        <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
          <Text style={styles.shareButtonText}>Share</Text>
        </TouchableOpacity>
      </View>
      <Text style={styles.verdictConfidence}>{verdict.confidence}</Text>
      <Text style={styles.verdictText}>{verdict.rationale}</Text>
      <Text style={styles.verdictLabel}>Value</Text>
      <Text style={styles.verdictText}>{verdict.value_summary}</Text>
      <Text style={styles.verdictLabel}>Roster fit</Text>
      <Text style={styles.verdictText}>{verdict.roster_summary}</Text>
      <Text style={styles.verdictLabel}>Strategy fit</Text>
      <Text style={styles.verdictText}>{verdict.strategy_summary}</Text>
      <Text style={styles.verdictLabel}>Risk</Text>
      <Text style={styles.verdictText}>{verdict.risk_summary}</Text>
      {verdict.counter_guidance ? (
        <>
          <Text style={styles.verdictLabel}>Counter guidance</Text>
          <Text style={styles.verdictText}>{verdict.counter_guidance}</Text>
        </>
      ) : null}

      <TradeSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueName={leagueName}
        verdict={verdict}
        sendPlayers={sendIds}
        receivePlayers={receiveIds}
      />
    </View>
  );
}

function TradeSide({
  label,
  players,
  active,
  onPressHeader,
  onRemove,
}: {
  label: string;
  players: RankedPlayer[];
  active: boolean;
  onPressHeader: () => void;
  onRemove: (playerId: string) => void;
}) {
  return (
    <View style={[styles.side, active && styles.sideActive]}>
      <TouchableOpacity onPress={onPressHeader}>
        <Text style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</Text>
      </TouchableOpacity>
      {players.map((player) => (
        <TouchableOpacity
          key={player.player_id}
          style={styles.chip}
          onPress={() => onRemove(player.player_id)}
        >
          <Text style={styles.chipText} numberOfLines={1}>
            {player.name ?? 'Unknown'}
          </Text>
          <Text style={styles.chipRemove}>{'×'}</Text>
        </TouchableOpacity>
      ))}
      {players.length === 0 ? <Text style={styles.sideEmpty}>Tap to add</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background, padding: spacing.lg },
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
  sideLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase', marginBottom: spacing.sm },
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
  teamRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  strategyRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
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
  verdictConfidence: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.sm },
  verdictLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
    textTransform: 'uppercase',
    marginTop: spacing.sm,
  },
  verdictText: { fontSize: 13, color: colors.textPrimary, lineHeight: 18 },
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
  resultInfo: { flex: 1, marginRight: spacing.sm },
  resultName: { fontSize: 15, fontWeight: '500', color: colors.textPrimary },
  resultMeta: { fontSize: 12, color: colors.textSecondary },
  resultMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 3 },
  resultScore: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
});
