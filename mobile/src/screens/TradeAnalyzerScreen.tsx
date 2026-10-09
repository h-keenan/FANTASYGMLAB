import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import AppText from '../components/AppText';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import FilterDropdownButton from '../components/FilterDropdownButton';
import GridBackground from '../components/GridBackground';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import CircularProgressRing from '../components/CircularProgressRing';
import TeamAvatar from '../components/TeamAvatar';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeValueBar from '../components/TradeValueBar';
import TradeValueHero from '../components/TradeValueHero';
import {
  api,
  type DraftPickAsset,
  type RankedPlayer,
  type TeamProfile,
  type TradeVerdict,
} from '../lib/api';
import { useGmStance } from '../context/GmStanceContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { useOrbClearance } from '../lib/orbLayout';
import { toUserErrorMessage } from '../lib/errorMessages';
import { valueDirectionLabel } from '../lib/tradeValue';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { disabledOpacity, radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

// Prop-driven now (TradesScreen owns the single `Trades` route and hosts
// this screen as one of its tabs) — leagueId/leagueName/navigation arrive as
// plain props instead of via route.params, but `navigation` is still the
// real root-stack navigation prop, used exactly as before for PlayerDetail/
// PickDetail/Paywall.
type TradeAnalyzerNavigation = NativeStackNavigationProp<RootStackParamList>;

interface Props {
  leagueId: string;
  leagueName: string;
  navigation: TradeAnalyzerNavigation;
}
type Side = 'send' | 'receive';
type AssetType = 'players' | 'picks';

type SideAssetItem =
  | { kind: 'player'; player: RankedPlayer }
  | { kind: 'pick'; pick: DraftPickAsset };

type SearchItem =
  | { kind: 'player'; player: RankedPlayer }
  | { kind: 'pick'; pick: DraftPickAsset };

const MAX_SEARCH_RESULTS = 40;
const POSITION_FILTERS = ['QB', 'RB', 'WR', 'TE', 'K', 'DEF'];
const ALL_POSITION_OPTIONS = ['ALL', ...POSITION_FILTERS];

function toneColors(colors: ThemeColors): Record<TradeVerdict['tone'], string> {
  return {
    accept: colors.success,
    decline: colors.danger,
    counter: colors.accent,
    fair: colors.textSecondary,
    // Never actually produced here — Trade Analyzer only ever renders a
    // real accept/decline/counter/fair verdict, never Trade Hub's 'idea'
    // tone — included only so this stays a valid Record<TradeVerdict['tone'], ...>.
    idea: colors.accent,
  };
}

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
  avatarId: string | null;
  playerIds: Set<string>;
}

const ALL_TEAMS_ID = '__all__';

export default function TradeAnalyzerScreen({ leagueId, leagueName, navigation }: Props) {
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
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
  // Quick Compare: an instant, client-side players-only value readout that
  // folds in what used to be the standalone Trade Calculator screen. Picks
  // never supported Trade Calculator, so they're force-excluded below.
  const [quickMode, setQuickMode] = useState(false);
  // Read-only here: stance is changed from the header button only.
  const { strategy } = useGmStance(leagueId);
  const { lens } = useValuationLens(leagueId);
  const [analyzing, setAnalyzing] = useState(false);
  const [verdict, setVerdict] = useState<TradeVerdict | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const orbClearance = useOrbClearance();

  // A verdict is analyzed under one stance/lens, so it goes stale the
  // moment either changes. The removed in-page strategy pills cleared it
  // inline; the header buttons can change stance/lens from anywhere, so
  // watch both values instead. (No-op on first render — `verdict` starts
  // null.)
  useEffect(() => {
    setVerdict(null);
  }, [strategy, lens]);

  // Entering Quick Compare must never leave an ambiguous state: force
  // players-only (picks never entered Trade Calculator's pool), drop any
  // picks already staged from Full Analysis, and clear any stale verdict
  // from a previous full-analysis run.
  useEffect(() => {
    if (!quickMode) return;
    setAssetType('players');
    setSendPicks([]);
    setReceivePicks([]);
    setVerdict(null);
  }, [quickMode]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [myRoster, rankingsResult, usersResult, rostersResult, picksResult, teamProfilesResult] = await Promise.all([
          api.getMyRoster(leagueId),
          api.getLeagueRankings(leagueId, { lens, limit: 300 }),
          api.getLeagueUsers(leagueId),
          api.getLeagueRosters(leagueId),
          api.getLeagueDraftPicks(leagueId).catch(() => ({ ok: true as const, picks: [], reason: 'unavailable' })),
          // Same team-profiles endpoint TeamsScreen/MyTeamScreen use for
          // `TeamAvatar` — avatar_id already has the server's real
          // roster-metadata -> user-metadata fallback chain baked in
          // (modules.sleeper.get_league_roster_profiles), unlike reading a
          // raw Sleeper user's `avatar` field directly.
          api.getLeagueTeamProfiles(leagueId).catch(() => ({ ok: true as const, profiles: {} })),
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
        const teamProfiles: Record<string, TeamProfile> = teamProfilesResult.profiles ?? {};
        const teams: OtherTeam[] = rostersResult.rosters
          .map((roster) => {
            const rosterId = String(roster.roster_id ?? '');
            const ownerId = String(roster.owner_id ?? '');
            const players = Array.isArray(roster.players) ? roster.players : [];
            return {
              rosterId,
              ownerName: usersById.get(ownerId) ?? 'Unclaimed team',
              avatarId: teamProfiles[rosterId]?.avatar_id ?? null,
              playerIds: new Set(players.map(String)),
            };
          })
          .filter((team) => team.rosterId && team.rosterId !== myId);
        setOtherTeams(teams);

        setRankings(rankingsResult.players);
      } catch (err) {
        if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load trade data.'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens]);

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

  // Switching which side new taps go to must also drop whatever text/position
  // filter was scoped to the *other* side's roster — otherwise the search
  // input's placeholder flips to "Search players to receive" while the field
  // still holds e.g. "Washington" (typed to find a player already added to
  // Send), silently zeroing the Receive results list against the opposing
  // roster and making "Tap to add" look completely broken (coridian_,
  // Discord: could add 2 players to Send but "cannot tap you receive side to
  // add players to that side" — the tap worked, the leftover filter just
  // hid every candidate).
  const selectSide = (side: Side) => {
    setActiveSide(side);
    setSearch('');
    setPositionFilter(null);
  };

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

  // Quick Compare's instant readout — receive-side total minus send-side
  // total, players only (ports Trade Calculator's own delta calc). Never
  // server-computed: this is what lets Quick Compare stay instant and never
  // call api.postTradeAnalyzer.
  const quickCompareDelta = useMemo(
    () => receiveIds.reduce((sum, p) => sum + playerScore(p), 0) - sendIds.reduce((sum, p) => sum + playerScore(p), 0),
    [sendIds, receiveIds],
  );

  const analyze = async () => {
    if (quickMode) return;
    setAnalyzeError(null);
    setAnalyzing(true);
    try {
      const result = await api.postTradeAnalyzer(leagueId, {
        sendPlayerIds: sendIds.map((p) => p.player_id),
        receivePlayerIds: receiveIds.map((p) => p.player_id),
        sendPickIds: sendPicks.map((p) => p.pick_id),
        receivePickIds: receivePicks.map((p) => p.pick_id),
        strategy,
        lens,
        partnerRosterId: selectedTeamId === ALL_TEAMS_ID ? '' : selectedTeamId,
      });
      if (result.verdict) {
        setVerdict(result.verdict);
      } else {
        setAnalyzeError(NOT_READY_MESSAGES[result.reason] ?? 'Could not analyze this trade.');
      }
    } catch (err) {
      setAnalyzeError(toUserErrorMessage(err, 'Could not analyze this trade.'));
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  if (notReadyReason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't verify your roster in this league."}
        </AppText>
      </View>
    );
  }

  const header = (
    <View>
      <ScreenInfoNote
        text={
          quickMode
            ? `Raw asset value only — ${leagueName}'s "Dynasty" valuations. Doesn't yet weigh roster fit or strategy, unlike the full Trade Analyzer.`
            : `The real accept / decline / counter verdict for ${leagueName} — weighs asset value, starting lineup impact, roster needs, age, draft capital, and injury risk.`
        }
      />

      <View style={styles.modeRow}>
        <SegmentedTabBar<'full' | 'quick'>
          options={[
            { key: 'full', label: 'Full Analysis' },
            { key: 'quick', label: 'Quick Compare' },
          ]}
          active={quickMode ? 'quick' : 'full'}
          onChange={(key) => setQuickMode(key === 'quick')}
        />
      </View>

      <View style={styles.sidesRow}>
        <TradeSide
          label="You Send"
          dotColor={colors.danger}
          items={[
            ...sendIds.map((player): SideAssetItem => ({ kind: 'player', player })),
            ...sendPicks.map((pick): SideAssetItem => ({ kind: 'pick', pick })),
          ]}
          active={activeSide === 'send'}
          onPressHeader={() => selectSide('send')}
          onRemove={(id) => removeFromSide('send', id)}
        />
        <TradeSide
          label="You Receive"
          dotColor={colors.successBright}
          items={[
            ...receiveIds.map((player): SideAssetItem => ({ kind: 'player', player })),
            ...receivePicks.map((pick): SideAssetItem => ({ kind: 'pick', pick })),
          ]}
          active={activeSide === 'receive'}
          onPressHeader={() => selectSide('receive')}
          onRemove={(id) => removeFromSide('receive', id)}
        />
      </View>

      {!quickMode ? (
        <View style={styles.assetTypeRow}>
          <TouchableOpacity
            style={[styles.pill, assetType === 'players' && styles.pillActive]}
            onPress={() => setAssetType('players')}
          >
            <AppText style={[styles.pillText, assetType === 'players' && styles.pillTextActive]}>Players</AppText>
          </TouchableOpacity>
          <TouchableOpacity
            style={[styles.pill, assetType === 'picks' && styles.pillActive]}
            onPress={() => setAssetType('picks')}
          >
            <AppText style={[styles.pillText, assetType === 'picks' && styles.pillTextActive]}>Picks</AppText>
          </TouchableOpacity>
        </View>
      ) : null}

      {assetType === 'players' ? (
        <View style={styles.teamRow}>
          <FilterDropdownButton
            label="Position"
            options={ALL_POSITION_OPTIONS}
            value={positionFilter ?? 'ALL'}
            onChange={(next) => setPositionFilter(next === 'ALL' ? null : next)}
          />
        </View>
      ) : null}

      {activeSide === 'receive' && otherTeams.length > 0 ? (
        <View style={styles.teamRow}>
          <TouchableOpacity
            style={[styles.pill, selectedTeamId === ALL_TEAMS_ID && styles.pillActive]}
            onPress={() => setSelectedTeamId(ALL_TEAMS_ID)}
          >
            <AppText style={[styles.pillText, selectedTeamId === ALL_TEAMS_ID && styles.pillTextActive]}>
              All Teams
            </AppText>
          </TouchableOpacity>
          {otherTeams.map((team) => (
            <TouchableOpacity
              key={team.rosterId}
              style={[styles.teamPill, selectedTeamId === team.rosterId && styles.pillActive]}
              onPress={() => setSelectedTeamId(team.rosterId)}
            >
              <TeamAvatar avatarId={team.avatarId} size={16} />
              <AppText
                style={[styles.pillText, selectedTeamId === team.rosterId && styles.pillTextActive]}
                numberOfLines={1}
              >
                {team.ownerName}
              </AppText>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}

      {quickMode ? (
        hasAnyAssets ? (
          <View style={styles.quickCompareSection}>
            <AppText style={styles.deltaLabel}>{valueDirectionLabel(quickCompareDelta)}</AppText>
            <TradeValueBar delta={quickCompareDelta} style={styles.verdictValueBar} />
          </View>
        ) : null
      ) : (
        <>
          <TouchableOpacity
            style={[styles.analyzeButton, !hasAnyAssets && styles.analyzeButtonDisabled]}
            onPress={analyze}
            disabled={analyzing || !hasAnyAssets}
          >
            {analyzing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <AppText style={styles.analyzeButtonText}>Analyze Trade</AppText>
            )}
          </TouchableOpacity>

          {analyzeError ? <AppText style={styles.error}>{analyzeError}</AppText> : null}
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
        </>
      )}

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
      contentContainerStyle={[styles.resultsList, { paddingBottom: orbClearance, paddingTop: headerHeight }]}
      keyboardShouldPersistTaps="handled"
      ListHeaderComponent={header}
      renderItem={({ item, index }) => {
        const showDivider = index < searchResults.length - 1;
        if (item.kind === 'player') {
          return (
            <PlayerIdentityRow
              playerId={item.player.player_id}
              name={item.player.name}
              position={item.player.position}
              team={item.player.team}
              tier={item.player.tier}
              overallRating={item.player.overall_rating}
              positionRank={item.player.position_rank}
              trailingValue={String(Math.round(playerScore(item.player)))}
              onPress={() => addPlayerToSide(item.player)}
              showDivider={showDivider}
            />
          );
        }
        return (
          <View style={[styles.pickResultRow, showDivider && styles.pickResultDivider]}>
            <DraftPickAssetRow
              style={styles.pickResultRowInner}
              pickId={item.pick.pick_id}
              round={item.pick.round}
              label={item.pick.label}
              projectedRange={item.pick.projected_pick_range}
              pickTier={item.pick.pick_tier}
              trailingValue={item.pick.score != null ? String(Math.round(item.pick.score)) : '—'}
              onPress={() => addPickToSide(item.pick)}
            />
            {/* This info button is the escape hatch to "why is it worth
                that?" (the same Pick Detail the Draft Center's pick list
                opens) — the row itself still adds the pick on tap, so
                bulk-adding stays one tap. */}
            <TouchableOpacity
              style={styles.pickInfoButton}
              hitSlop={8}
              onPress={() =>
                navigation.navigate('PickDetail', { pick: item.pick, leagueId, leagueName })
              }
            >
              <Ionicons name="information-circle-outline" size={20} color={colors.textTertiary} />
            </TouchableOpacity>
          </View>
        );
      }}
      ListEmptyComponent={
        <AppText style={styles.empty}>
          {assetType === 'players' && activeSide === 'send' && myRosterIds.size === 0
            ? 'No roster players found.'
            : search
              ? `No matching ${assetType === 'picks' ? 'picks' : 'players'}.`
              : 'Start typing to search.'}
        </AppText>
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!text) return null;
  return (
    <View style={styles.verdictSection}>
      <View style={styles.verdictSectionLabelRow}>
        <Ionicons name={icon} size={13} color={color} />
        <AppText style={[styles.verdictLabel, { color }]}>{label}</AppText>
      </View>
      <AppText style={styles.verdictText}>{text}</AppText>
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
  const { colors } = useThemeMode();
  const { showExplanations } = useDensity();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [shareOpen, setShareOpen] = useState(false);
  const toneColor = toneColors(colors)[verdict.tone];
  // trade_offer_analyzer.py's decide_offer_verdict already separates a
  // routine ACCEPT/DECLINE from a genuinely lopsided one into its own named
  // band (VERDICT_SMASH_ACCEPT / VERDICT_HARD_DECLINE) — that split only
  // fires at the value/fit extremes _VALUE_SMASH / _VALUE_HARD, well beyond
  // a normal accept/decline gap. Reusing that existing band string here
  // (rather than re-deriving a client-side value-delta threshold) is what
  // coridian_ asked for after a 2-for-nothing trade came back as a plain
  // "HARD DECLINE, 90% confidence" card indistinguishable from a mild
  // decline: "we need a custom screens for things like this ... when it's
  // absolutely lopsided."
  const isExtreme = verdict.band === 'HARD DECLINE' || verdict.band === 'SMASH ACCEPT';
  // Recorded alongside the share so the quiet Trade Outcomes result sweep
  // can re-value these same players under the same lens later.
  const { lens } = useValuationLens(leagueId);

  return (
    <AnimatedCard
      style={StyleSheet.flatten([
        styles.verdictCard,
        { borderLeftColor: toneColor },
        isExtreme && styles.verdictCardExtreme,
      ])}
      // `glow` is this app's existing "the one card on screen that matters"
      // treatment (Dashboard's Top Priority card) — reused as-is instead of
      // inventing a second emphasis language, tinted to the verdict's own
      // tone so an extreme accept glows success-green and an extreme decline
      // glows danger-red.
      glow={isExtreme}
      glowColor={toneColor}
    >
      {isExtreme ? (
        <View style={[styles.extremeEyebrowRow, { backgroundColor: toneColor }]}>
          <Ionicons name="alert-circle" size={13} color="#fff" />
          <AppText style={styles.extremeEyebrowText}>
            {verdict.tone === 'accept' ? 'Extremely Lopsided In Your Favor' : 'Extremely Lopsided Against You'}
          </AppText>
        </View>
      ) : null}
      <View style={styles.verdictHeaderRow}>
        <AppText style={[styles.verdictBand, isExtreme && styles.verdictBandExtreme, { color: toneColor }]}>
          {verdict.band}
        </AppText>
        <TouchableOpacity style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
          <AppText style={styles.shareButtonText}>Share</AppText>
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
          <AppText style={styles.verdictRingCaption} numberOfLines={1}>
            {verdict.confidence}
          </AppText>
        </View>
      </View>
      {/* Same "who's winning" shape-reinforcement TradeValueBar gives Trade
          Hub's cards, applied to the verdict's own value_delta so the two
          surfaces agree on what a value edge looks like. */}
      <TradeValueBar delta={verdict.value_delta} style={styles.verdictValueBar} />
      {showExplanations ? (
        <>
          <AppText style={[styles.verdictText, styles.verdictRationale]}>{verdict.rationale}</AppText>

          <VerdictSection icon="cash-outline" label="Value" text={verdict.value_summary} color={toneColor} />
          <VerdictSection icon="people-outline" label="Roster fit" text={verdict.roster_summary} color={toneColor} />
          <VerdictSection icon="compass-outline" label="Strategy fit" text={verdict.strategy_summary} color={toneColor} />
          <VerdictSection icon="warning-outline" label="Risk" text={verdict.risk_summary} color={colors.danger} />
          {verdict.counter_guidance ? (
            <VerdictSection
              icon="swap-horizontal-outline"
              label="Counter guidance"
              text={verdict.counter_guidance}
              color={colors.premium}
            />
          ) : null}
        </>
      ) : null}
      {verdict.counter_action && verdict.counter_action.asset_type === 'player' ? (
        <TouchableOpacity style={styles.counterButton} onPress={onBuildCounter}>
          <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          <AppText style={styles.counterButtonText}>Build the counter</AppText>
        </TouchableOpacity>
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
        valuationLens={lens}
      />
    </AnimatedCard>
  );
}

/**
 * One side (You Send / You Receive) of the trade being built — the same
 * Send/Receive card language Trade Hub/Trade Finder use for a proposed
 * trade's asset lists (§30), just editable here: each row's own tap removes
 * it instead of opening detail, and tapping anywhere on the card (not just
 * the label row) makes this side the active add target for the search list
 * below. The card itself is the touchable, so nested per-item rows (each a
 * TouchableOpacity in their own right) still win their own taps for removal
 * — RN resolves the responder to the deepest touchable under the finger.
 */
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
  items: SideAssetItem[];
  active: boolean;
  onPressHeader: () => void;
  onRemove: (id: string) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <TouchableOpacity
      style={[styles.side, active && styles.sideActive]}
      onPress={onPressHeader}
      activeOpacity={0.85}
    >
      <View style={styles.sideLabelRow}>
        <View style={[styles.sideDot, { backgroundColor: dotColor }]} />
        <AppText style={[styles.sideLabel, active && styles.sideLabelActive]}>{label}</AppText>
      </View>
      {items.length > 0 ? (
        <View style={styles.sideAssetSurface}>
          {items.map((item, index) => {
            const showDivider = index < items.length - 1;
            if (item.kind === 'player') {
              return (
                <PlayerIdentityRow
                  key={`player-${item.player.player_id}`}
                  playerId={item.player.player_id}
                  name={item.player.name}
                  position={item.player.position}
                  team={item.player.team}
                  tier={item.player.tier}
                  overallRating={item.player.overall_rating}
                  positionRank={item.player.position_rank}
                  onPress={() => onRemove(item.player.player_id)}
                  showDivider={showDivider}
                />
              );
            }
            return (
              <DraftPickAssetRow
                key={`pick-${item.pick.pick_id}`}
                pickId={item.pick.pick_id}
                round={item.pick.round}
                label={item.pick.label}
                projectedRange={item.pick.projected_pick_range}
                pickTier={item.pick.pick_tier}
                onPress={() => onRemove(item.pick.pick_id)}
                showDivider={showDivider}
              />
            );
          })}
        </View>
      ) : (
        <AppText style={styles.sideEmpty}>Tap to add</AppText>
      )}
    </TouchableOpacity>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
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
  modeRow: { marginBottom: spacing.sm },
  sidesRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  // The side panel is a drop target, so it needs a visible edge even when
  // inactive — a `surface` fill alone is only 1.09 against `background`.
  // The 2pt width is unchanged between states; only the color swaps.
  side: {
    flex: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: colors.cardBorder,
    padding: spacing.md,
    minHeight: 80,
  },
  sideActive: { borderColor: colors.accent },
  sideLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm },
  sideDot: { width: 7, height: 7, borderRadius: 3.5 },
  sideLabel: { fontSize: 12, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  sideLabelActive: { color: colors.accent },
  sideEmpty: { fontSize: 12, color: colors.textSecondary, fontStyle: 'italic' },
  // Nested inside `side` (a `surface` panel): step *up* the ramp rather than
  // down, so the asset group reads as a raised token instead of a hole
  // punched in the panel at near-identical luminance — same treatment Trade
  // Hub/Trade Finder give their own exchange-side surfaces.
  sideAssetSurface: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
  },
  assetTypeRow: { flexDirection: 'row', gap: spacing.xs, marginBottom: spacing.sm },
  teamRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
  },
  // Same pill as above, plus the leading TeamAvatar other-team filter pills
  // show next to the owner name — "All Teams" keeps the plain `pill` style
  // since it has no single team/avatar to show.
  teamPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.cardBorder,
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
  analyzeButtonDisabled: { opacity: disabledOpacity },
  analyzeButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  // Quick Compare's instant readout — same label + bar shape as the full
  // verdict's value strip (below), just driven by a client-computed delta.
  quickCompareSection: { marginBottom: spacing.md },
  deltaLabel: {
    textAlign: 'center',
    fontSize: 14,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  // AnimatedCard already supplies the surface fill/radius/border/shadow —
  // this just adds the tone-colored left rail and the card's own spacing.
  verdictCard: {
    borderLeftWidth: 4,
    marginBottom: spacing.md,
  },
  // Extra left-rail weight for the SMASH ACCEPT / HARD DECLINE bands, on top
  // of AnimatedCard's own `glow` rim+shadow — the rail alone reads too close
  // to a normal verdict's 4pt rail once the glow is also present.
  verdictCardExtreme: { borderLeftWidth: 6 },
  // A solid, full-width tone-colored strip above the band — the one
  // "unmissable even at a glance" cue, distinct from every other card on
  // this screen which only ever gets a thin colored rail.
  extremeEyebrowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'flex-start',
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    marginBottom: spacing.sm,
  },
  extremeEyebrowText: { fontSize: 11, fontWeight: '800', color: '#fff', textTransform: 'uppercase', letterSpacing: 0.3 },
  verdictHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  verdictBand: { fontSize: 18, fontWeight: '800', marginBottom: spacing.xs },
  verdictBandExtreme: { fontSize: 22 },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.cardBorder,
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
  verdictValueBar: { marginBottom: spacing.md },
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
    borderColor: colors.cardBorder,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 10,
    fontSize: 15,
    backgroundColor: colors.surface,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  resultsList: { paddingBottom: spacing.xl },
  // A pick search row pairs DraftPickAssetRow (which owns the "add to
  // package" tap) with a separate "view pick detail" button — the outer row
  // carries the group divider so both children read as one continuous row.
  pickResultRow: { flexDirection: 'row', alignItems: 'center' },
  pickResultRowInner: { flex: 1 },
  pickResultDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  pickInfoButton: { marginLeft: spacing.sm },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginBottom: spacing.sm },
  });
}
