import { TRADE_SIDE_LABEL } from '../lib/tradeSideLabels';
import ExchangeSide from '../components/ExchangeSide';
import { dropRepeatedSentences, shortSummary } from '../lib/verdictText';
import { cautionDetail, verdictCautions } from '../lib/tradeCautions';
import NextSteps from '../components/NextSteps';
import ShareToCommunityToggle from '../components/ShareToCommunityToggle';
import type { SharedTradeAssetInput } from '../lib/sharedTrades';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  View,
} from 'react-native';
import PostureChip from '../components/PostureChip';
import AppText from '../components/AppText';
import ToneBadge, { withAlpha } from '../components/ToneBadge';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import Button from '../components/Button';
import LimitWall from '../components/LimitWall';
import { limitWallForReason, type LimitWallModel } from '../lib/limitWall';
import { useAuth } from '../context/AuthContext';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SegmentedTabBar from '../components/SegmentedTabBar';
import MeterRow from '../components/ConfidenceMeter';
import TeamAvatar from '../components/TeamAvatar';
import ManagerTendenciesChips from '../components/ManagerTendenciesChips';
import MultiTeamTradePanel from '../components/MultiTeamTradePanel';
import { isEspnLeagueId } from '../lib/leaguePlatform';
import TradeSharePreviewModal from '../components/TradeSharePreviewModal';
import TradeOddsEffect from '../components/TradeOddsEffect';
import TradeValueBar from '../components/TradeValueBar';
import VerdictTrust from '../components/VerdictTrust';
import type { VerdictAssumptions } from '../lib/verdictTrust';
import type { RosterOverflow } from '../lib/api';
import { fetchMissingPlayersById, mergeSearchMatches, useLeaguePlayerSearch } from '../lib/leaguePlayerSearch';
import { RosterOverflowNote } from '../components/SuggestedDrop';
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
import { trackUse } from '../lib/analytics';
import { toUserErrorMessage } from '../lib/errorMessages';
import { valueDirectionLabel } from '../lib/tradeValue';
import { formatTradeGain } from '../lib/liveDraft';
import { idpTradePoolPlayers } from '../lib/idpPresentation';
import { quickAddPlacement } from '../lib/tradeShortcuts';
import TradePickerSheet, { TradeSideSummary } from '../components/TradePickerSheet';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { pickToSheetItem, playerToSheetItem } from '../lib/tradeSheetItems';
import { selectedItems, type SheetItem } from '../lib/tradeSheetPicker';
import { offerPrefillKey, resolvePrefill, type OfferPrefill } from '../lib/tradeOffer';
import { prefillKey } from '../lib/multiTeamIdeas';
import type { MultiTransfer } from '../lib/multiTeamTrade';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import BeginnerHelp from '../components/BeginnerHelp';
import ValuesCredit from '../components/ValuesCredit';
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
  /** PlayerDetail / Players "Add to Trade" (tap-depth audit #1): filed on
   * the right side once rosters load, owning team selected, and the active
   * side moved to the empty one. */
  quickAddPlayer?: RankedPlayer;
  /** A built offer ("Build an offer"): loaded once into both sides so it can
   * be tweaked, regraded and shared. Ids not in this league are skipped. */
  offerPrefill?: OfferPrefill;
  /** A 3-team trade (a Trade Hub idea): opens the Multi-team builder with it loaded and graded. */
  multiPrefill?: MultiTransfer[];
}
type Side = 'send' | 'receive';


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

// Ring level (1-3). With the lineup model the label comes from a computed
// P(direction is right); older servers only send the three label strings.
function confidenceLevel(verdict: TradeVerdict): 1 | 2 | 3 {
  if (verdict.confidence_pct != null) {
    return verdict.confidence_pct >= 88 ? 3 : verdict.confidence_pct >= 70 ? 2 : 1;
  }
  const pct = confidencePercent(verdict.confidence);
  return pct >= 80 ? 3 : pct >= 50 ? 2 : 1;
}

// Signed lineup points: one decimal under 10, none above ("+4.2", "-92").
function formatLineupPoints(points: number): string {
  const rounded = Math.abs(points) < 10 ? Math.round(points * 10) / 10 : Math.round(points);
  return `${rounded > 0 ? '+' : rounded < 0 ? '-' : ''}${Math.abs(rounded)}`;
}

function playerScore(player: RankedPlayer): number {
  return typeof player.score === 'number' ? player.score : 0;
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Trade Analyzer needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  assets_unresolved:
    'Some players or picks in this package could not be found, so no verdict was given (a verdict on part of a trade would be misleading). Remove them and try again.',
};

interface OtherTeam {
  rosterId: string;
  ownerName: string;
  /** Team name for the multi-team builder (falls back to the owner). */
  teamName: string;
  avatarId: string | null;
  playerIds: Set<string>;
}

const ALL_TEAMS_ID = '__all__';

export default function TradeAnalyzerScreen({ leagueId, leagueName, navigation, quickAddPlayer, offerPrefill, multiPrefill }: Props) {

  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [myRosterIds, setMyRosterIds] = useState<Set<string>>(new Set());
  const [myRosterId, setMyRosterId] = useState('');
  const [otherTeams, setOtherTeams] = useState<OtherTeam[]>([]);
  const [myTeam, setMyTeam] = useState<{ name: string; avatarId: string | null }>({ name: 'Your team', avatarId: null });
  // Two teams (Full Analysis / Quick Compare) or a 3 to 6 team trade. Imported
  // (ESPN, MFL, ...) leagues only get the two team Analyzer.
  const [multiMode, setMultiMode] = useState(Boolean(multiPrefill?.length));
  const multiPrefillKey = multiPrefill?.length ? prefillKey(multiPrefill) : '';
  // A new idea opened while this tab is already mounted switches to Multi-team.
  useEffect(() => {
    if (multiPrefillKey) setMultiMode(true);
  }, [multiPrefillKey]);
  const multiTeamAvailable = !isEspnLeagueId(leagueId);
  const [selectedTeamId, setSelectedTeamId] = useState<string>(ALL_TEAMS_ID);
  const [rankings, setRankings] = useState<RankedPlayer[]>([]);
  const [allPicks, setAllPicks] = useState<DraftPickAsset[]>([]);
  const [sendIds, setSendIds] = useState<RankedPlayer[]>([]);
  const [receiveIds, setReceiveIds] = useState<RankedPlayer[]>([]);
  const [sendPicks, setSendPicks] = useState<DraftPickAsset[]>([]);
  const [receivePicks, setReceivePicks] = useState<DraftPickAsset[]>([]);
  // Which side's piece-picker sheet is open (tap a side to open it), and its search text for server-side matches.
  const [sheetSide, setSheetSide] = useState<Side | null>(null);
  const [sheetSearch, setSheetSearch] = useState('');
  const { openPlayer: openQuickView } = usePlayerQuickView();
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
  const [limitWall, setLimitWall] = useState<LimitWallModel | null>(null);
  const { isGuest } = useAuth();
  const [planningNote, setPlanningNote] = useState('');
  const [roleNotes, setRoleNotes] = useState<string[]>([]);
  const [assumptions, setAssumptions] = useState<VerdictAssumptions | null>(null);
  const [rosterOverflow, setRosterOverflow] = useState<RosterOverflow | null>(null);

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
    setSendPicks([]);
    setReceivePicks([]);
    setVerdict(null);
  }, [quickMode]);

  // Ids carried in by a deep link/prefill may be ranked below the top-300 window;
  // the load below resolves them by exact id. A ref so a new prefill does not refetch everything.
  const prefillIdsRef = useRef<string[]>([]);
  prefillIdsRef.current = [
    quickAddPlayer?.player_id ?? '',
    ...(offerPrefill ? [...offerPrefill.send, ...offerPrefill.receive] : []),
    ...(multiPrefill ?? []).filter((t) => t.type === 'player').map((t) => t.id),
  ].filter(Boolean);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [myRoster, rankingsResult, usersResult, rostersResult, picksResult, teamProfilesResult, idpResult] = await Promise.all([
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
          // IDP leagues only (`idp: false` otherwise); a failure leaves offense untouched.
          api.getLeagueIdpValues(leagueId, { includeBelow: true }).catch(() => null),
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
              teamName: teamProfiles[rosterId]?.team_name || usersById.get(ownerId) || 'Unclaimed team',
              avatarId: teamProfiles[rosterId]?.avatar_id ?? null,
              playerIds: new Set(players.map(String)),
            };
          })
          .filter((team) => team.rosterId && team.rosterId !== myId);
        setOtherTeams(teams);
        setMyTeam({ name: teamProfiles[myId]?.team_name || 'Your team', avatarId: teamProfiles[myId]?.avatar_id ?? null });

        const extras = await fetchMissingPlayersById(leagueId, lens, prefillIdsRef.current, rankingsResult.players);
        if (cancelled) return;
        setRankings([...mergeSearchMatches(rankingsResult.players, extras), ...idpTradePoolPlayers(idpResult)]);
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

  // "Add to Trade" quick-add — once per player id, after the first load
  // (needs myRosterIds/otherTeams to know whose player this is). Mirrors web
  // TradeAnalyzerContent's quickAddPlayerId; a player on no roster here is
  // simply not added (fail open). Prefers the freshly ranked row (current
  // lens score) over the one handed in by the caller.
  const appliedQuickAddId = useRef<string | null>(null);
  useEffect(() => {
    if (loading || !quickAddPlayer?.player_id) return;
    if (appliedQuickAddId.current === quickAddPlayer.player_id) return;
    appliedQuickAddId.current = quickAddPlayer.player_id;
    const placement = quickAddPlacement(quickAddPlayer.player_id, myRosterIds, otherTeams);
    if (!placement) return;
    const player = rankings.find((p) => p.player_id === quickAddPlayer.player_id) ?? quickAddPlayer;
    const addOnce = (prev: RankedPlayer[]) =>
      prev.some((p) => p.player_id === player.player_id) ? prev : [...prev, player];
    if (placement.side === 'send') {
      setSendIds(addOnce);
    } else {
      setReceiveIds(addOnce);
      if (placement.partnerRosterId) setSelectedTeamId(placement.partnerRosterId);
    }
    setVerdict(null);
  }, [loading, quickAddPlayer, myRosterIds, otherTeams, rankings]);

  // "Build an offer" hand-off, once per offer, after the first load.
  const appliedOfferKey = useRef<string | null>(null);
  useEffect(() => {
    if (loading || !offerPrefill) return;
    const key = offerPrefillKey(offerPrefill);
    if (appliedOfferKey.current === key) return;
    appliedOfferKey.current = key;
    const resolved = resolvePrefill(offerPrefill, rankings, allPicks);
    setSendIds(resolved.send);
    setReceiveIds(resolved.receive);
    setSendPicks(resolved.sendPicks);
    setReceivePicks(resolved.receivePicks);
    const owner = otherTeams.find((team) => resolved.receive.some((p) => team.playerIds.has(p.player_id)));
    if (owner) setSelectedTeamId(owner.rosterId);
    setVerdict(null);
  }, [loading, offerPrefill, rankings, allPicks, otherTeams]);

  const hasAnyAssets =
    sendIds.length > 0 || receiveIds.length > 0 || sendPicks.length > 0 || receivePicks.length > 0;

  // `rankings` is the top-300 window; a rostered player ranked below it must still
  // be tradeable, so the sheet's search also asks the server.
  const searchMatches = useLeaguePlayerSearch(leagueId, lens, sheetSearch);
  const pool = useMemo(() => mergeSearchMatches(rankings, searchMatches), [rankings, searchMatches]);

  // Items for the open sheet: the side's own pool (your roster, or the partner's / everyone else's), plus whatever
  // that side already holds so applying never drops a prefilled asset that sits outside the pool.
  const sheetItems = useMemo<SheetItem<RankedPlayer | DraftPickAsset>[]>(() => {
    if (!sheetSide) return [];
    const team = otherTeams.find((t) => t.rosterId === selectedTeamId);
    const players =
      sheetSide === 'send'
        ? pool.filter((p) => myRosterIds.has(p.player_id))
        : selectedTeamId === ALL_TEAMS_ID
          ? pool.filter((p) => !myRosterIds.has(p.player_id))
          : team
            ? pool.filter((p) => team.playerIds.has(p.player_id))
            : [];
    const pickPool =
      sheetSide === 'send'
        ? allPicks.filter((p) => p.owner_roster_id === myRosterId)
        : selectedTeamId === ALL_TEAMS_ID
          ? allPicks.filter((p) => p.owner_roster_id !== myRosterId)
          : allPicks.filter((p) => p.owner_roster_id === selectedTeamId);
    const held = sheetSide === 'send' ? { players: sendIds, picks: sendPicks } : { players: receiveIds, picks: receivePicks };
    const playerItems = [...new Map([...players, ...held.players].map((p) => [p.player_id, p])).values()].map(playerToSheetItem);
    const pickItems = [...new Map([...pickPool, ...held.picks].map((p) => [p.pick_id, p])).values()].map(pickToSheetItem);
    return [...playerItems, ...pickItems];
  }, [sheetSide, pool, allPicks, myRosterIds, myRosterId, otherTeams, selectedTeamId, sendIds, sendPicks, receiveIds, receivePicks]);

  const openSheet = (side: Side) => {
    setSheetSearch('');
    setSheetSide(side);
  };

  /** The sheet's Apply: replace this side's players and picks with the selection in one step. */
  const applySheet = (keys: string[]) => {
    if (!sheetSide) return;
    const chosen = selectedItems(sheetItems, keys);
    const players = chosen.filter((i) => i.kind === 'player').map((i) => i.ref as RankedPlayer);
    const pickList = chosen.filter((i) => i.kind === 'pick').map((i) => i.ref as DraftPickAsset);
    if (sheetSide === 'send') {
      setSendIds(players);
      setSendPicks(pickList);
    } else {
      setReceiveIds(players);
      setReceivePicks(pickList);
    }
    setVerdict(null);
    setSheetSide(null);
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
    if (!action || !action.player_id) return;
    if (action.asset_type === 'pick') {
      // Picks round-trip through `player_id` too (trade_analyzer_assembly.
      // pick_asset_from_mapping's `pick_id`, the same DraftPickAsset.pick_id
      // allPicks is already keyed on) — see the player branch below for
      // the original player-only version of this.
      if (action.action === 'remove_from_send') {
        setSendPicks((prev) => prev.filter((p) => p.pick_id !== action.player_id));
      } else if (action.action === 'add_to_receive') {
        const pick = allPicks.find((p) => p.pick_id === action.player_id);
        if (!pick) return;
        setReceivePicks((prev) => (prev.some((p) => p.pick_id === pick.pick_id) ? prev : [...prev, pick]));
      }
    } else if (action.action === 'remove_from_send') {
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

  const sendCount = sendIds.length + sendPicks.length;
  const receiveCount = receiveIds.length + receivePicks.length;
  const canAnalyze = hasAnyAssets;
  const analyzeLabel = canAnalyze ? `Analyze Trade (${sendCount} for ${receiveCount})` : 'Analyze Trade';

  const analyze = async () => {
    if (quickMode) return;
    setAnalyzeError(null);
    setLimitWall(null);
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
      setPlanningNote(result.planning_note ?? '');
      setRoleNotes(result.role_notes ?? []);
      setAssumptions(result.assumptions ?? null);
      setRosterOverflow(result.roster_overflow ?? null);
      trackUse('trade_analyzer', 'evaluated', {
        leagueId,
        props: { result: result.verdict ? 'verdict' : 'no_verdict' },
      });
      if (result.verdict) {
        setVerdict(result.verdict);
      } else {
        const wall = limitWallForReason(result.reason, { info: result.limit, isGuest });
        if (wall) setLimitWall(wall);
        else setAnalyzeError(NOT_READY_MESSAGES[result.reason] ?? 'Could not analyze this trade.');
      }
    } catch (err) {
      setAnalyzeError(toUserErrorMessage(err, 'Could not analyze this trade.'));
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
        <ErrorState title="Couldn't load the trade analyzer" message={error} />
      </View>
    );
  }

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <EmptyState icon="time-outline" title="Not ready yet" subtitle={NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't verify your roster in this league."} />
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
        <SegmentedTabBar<'full' | 'quick' | 'multi'>
          options={[
            { key: 'full', label: 'Full Analysis' },
            { key: 'quick', label: 'Quick Compare' },
            ...(multiTeamAvailable ? [{ key: 'multi' as const, label: 'Multi-team' }] : []),
          ]}
          active={multiMode ? 'multi' : quickMode ? 'quick' : 'full'}
          onChange={(key) => {
            setMultiMode(key === 'multi');
            setQuickMode(key === 'quick');
          }}
        />
      </View>

      {otherTeams.length > 0 ? (
        <View style={styles.partnerBlock}>
          <AppText style={styles.partnerLabel}>TRADING WITH</AppText>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.partnerRow} keyboardShouldPersistTaps="handled">
            <TouchableOpacity
              accessibilityRole="button"
              accessibilityState={{ selected: selectedTeamId === ALL_TEAMS_ID }}
              style={[styles.pill, selectedTeamId === ALL_TEAMS_ID && styles.pillActive]}
              onPress={() => setSelectedTeamId(ALL_TEAMS_ID)}
            >
              <AppText style={[styles.pillText, selectedTeamId === ALL_TEAMS_ID && styles.pillTextActive]}>Any team</AppText>
            </TouchableOpacity>
            {otherTeams.map((team) => (
              <TouchableOpacity
                accessibilityRole="button"
                accessibilityState={{ selected: selectedTeamId === team.rosterId }}
                key={team.rosterId}
                style={[styles.teamPill, selectedTeamId === team.rosterId && styles.pillActive]}
                onPress={() => setSelectedTeamId(team.rosterId)}
              >
                <TeamAvatar avatarId={team.avatarId} size={16} />
                <AppText style={[styles.pillText, selectedTeamId === team.rosterId && styles.pillTextActive]} numberOfLines={1}>
                  {team.ownerName}
                </AppText>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      ) : null}

      <View style={styles.sidesRow}>
        <TradeSideSummary
          testID="trade-side-send"
          label={TRADE_SIDE_LABEL.send}
          tone="danger"
          items={[...sendIds.map(playerToSheetItem), ...sendPicks.map(pickToSheetItem)]}
          onOpen={() => openSheet('send')}
          onRemove={(key) => removeFromSide('send', key.slice(key.indexOf(':') + 1))}
          hint="Add from your roster"
        />
        <TradeSideSummary
          testID="trade-side-receive"
          label={TRADE_SIDE_LABEL.receive}
          tone="success"
          items={[...receiveIds.map(playerToSheetItem), ...receivePicks.map(pickToSheetItem)]}
          onOpen={() => openSheet('receive')}
          onRemove={(key) => removeFromSide('receive', key.slice(key.indexOf(':') + 1))}
          hint={selectedTeamId === ALL_TEAMS_ID ? 'Add from any team' : `Add from ${otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? 'team'}`}
        />
      </View>

      {!quickMode ? (
        <>
          <Button label={analyzeLabel} onPress={analyze} disabled={!canAnalyze} loading={analyzing} style={styles.analyzeButton} />
          {!canAnalyze ? <AppText style={styles.analyzeHint}>Add players or picks to analyze.</AppText> : null}

          {limitWall ? <LimitWall wall={limitWall} feature="trade_analyzer_weekly_limit" /> : null}
          {analyzeError ? <AppText style={styles.error}>{analyzeError}</AppText> : null}
          {/* Past the trade deadline the analyzer stays open for offseason
              planning — this note just says the trade can't be sent yet. */}
          {planningNote ? <AppText style={styles.planningNote}>{planningNote}</AppText> : null}
          {roleNotes.length ? (
            <View style={styles.roleNotes}>
              <AppText style={styles.roleNotesTitle}>ROLE CHANGES (PRO)</AppText>
              {roleNotes.map((line) => (
                <AppText key={line} style={styles.roleNote}>
                  {line}
                </AppText>
              ))}
            </View>
          ) : null}
          {verdict ? (
            <>
            <VerdictCard
              verdict={verdict}
              sendIds={sendIds}
              receiveIds={receiveIds}
              sendPicks={sendPicks}
              receivePicks={receivePicks}
              leagueId={leagueId}
              leagueName={leagueName}
              partnerTeamName={otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? ''}
              onBuildCounter={applyCounterAction}
            />
            {rosterOverflow ? <RosterOverflowNote overflow={rosterOverflow} /> : null}
            <VerdictTrust
              assumptions={assumptions}
              context={{
                surface: 'trade_analyzer',
                platform: Platform.OS === 'ios' ? 'ios' : 'android',
                leagueId,
                lens,
                strategy,
                sendIds: [...sendIds.map((p) => p.player_id), ...sendPicks.map((p) => p.pick_id)],
                receiveIds: [...receiveIds.map((p) => p.player_id), ...receivePicks.map((p) => p.pick_id)],
                verdictLabel: verdict.ui_verdict,
                confidence: verdict.confidence,
                valueDelta: verdict.value_delta,
                assumptionsLine: assumptions?.line ?? '',
              }}
            />
            </>
          ) : null}
        </>
      ) : null}

      {selectedTeamId !== ALL_TEAMS_ID ? (
        <ManagerTendenciesChips
          leagueId={leagueId}
          teamName=""
          rosterId={selectedTeamId}
        />
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
        </>
      )}

    </View>
  );

  if (multiMode && multiTeamAvailable) {
    const panelTeams = [
      { rosterId: myRosterId, name: myTeam.name, avatarId: myTeam.avatarId, playerIds: myRosterIds },
      ...otherTeams.map((team) => ({ rosterId: team.rosterId, name: team.teamName, avatarId: team.avatarId, playerIds: team.playerIds })),
    ];
    return (
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <GridBackground />
        <ScrollView
          style={styles.container}
          contentContainerStyle={[styles.resultsList, { paddingBottom: orbClearance }]}
          keyboardShouldPersistTaps="handled"
        >
          <View style={styles.modeRow}>
            <SegmentedTabBar<'full' | 'quick' | 'multi'>
              options={[
                { key: 'full', label: 'Full Analysis' },
                { key: 'quick', label: 'Quick Compare' },
                { key: 'multi', label: 'Multi-team' },
              ]}
              active="multi"
              onChange={(key) => {
                setMultiMode(key === 'multi');
                setQuickMode(key === 'quick');
              }}
            />
          </View>
          <MultiTeamTradePanel
            key={multiPrefillKey || 'builder'}
            prefill={multiPrefill}
            leagueId={leagueId}
            leagueName={leagueName}
            myRosterId={myRosterId}
            teams={panelTeams}
            rankings={rankings}
            picks={allPicks}
            lens={lens}
          />
          <ValuesCredit />
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.resultsList, { paddingBottom: orbClearance }]}
        keyboardShouldPersistTaps="handled"
      >
        {header}
        <ValuesCredit />
      </ScrollView>
      {sheetSide ? (
        <TradePickerSheet
          key={sheetSide}
          title={sheetSide === 'send' ? TRADE_SIDE_LABEL.send : TRADE_SIDE_LABEL.receive}
          subtitle={
            sheetSide === 'send'
              ? 'From your roster'
              : selectedTeamId === ALL_TEAMS_ID
                ? 'From any team'
                : `From ${otherTeams.find((t) => t.rosterId === selectedTeamId)?.ownerName ?? 'team'}`
          }
          tone={sheetSide === 'send' ? 'danger' : 'success'}
          items={sheetItems}
          playersOnly={quickMode}
          initialSelected={[
            ...(sheetSide === 'send' ? sendIds : receiveIds).map((p) => `player:${p.player_id}`),
            ...(sheetSide === 'send' ? sendPicks : receivePicks).map((p) => `pick:${p.pick_id}`),
          ]}
          onApply={applySheet}
          onClose={() => setSheetSide(null)}
          onSearch={setSheetSearch}
          hideOnInfo
          onInfo={(item, restore) =>
            openQuickView(item.ref as RankedPlayer, { leagueId, leagueName, sourceLabel: 'Trade Analyzer', onClosed: restore })
          }
        />
      ) : null}
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
      <View style={[styles.verdictGlyph, { backgroundColor: withAlpha(color, 0.15) }]}>
        <Ionicons name={icon} size={16} color={color} />
      </View>
      <View style={styles.verdictSectionBody}>
        <ToneBadge label={label} color={color} />
        <AppText style={styles.verdictText}>{text}</AppText>
      </View>
    </View>
  );
}

function toShareAssets(players: RankedPlayer[], picks: DraftPickAsset[]): SharedTradeAssetInput[] {
  return [
    ...players.map((p): SharedTradeAssetInput => ({
      asset_type: 'player',
      name: p.name ?? '',
      position: p.position ?? undefined,
      player_id: p.player_id,
    })),
    ...picks.map((p): SharedTradeAssetInput => ({ asset_type: 'pick', name: p.label ?? 'Draft pick' })),
  ];
}

function VerdictCard({
  verdict,
  sendIds,
  receiveIds,
  sendPicks,
  receivePicks,
  leagueId,
  leagueName,
  partnerTeamName,
  onBuildCounter,
}: {
  verdict: TradeVerdict;
  sendIds: RankedPlayer[];
  receiveIds: RankedPlayer[];
  sendPicks: DraftPickAsset[];
  receivePicks: DraftPickAsset[];
  leagueId: string;
  leagueName: string;
  partnerTeamName: string;
  onBuildCounter: () => void;
}) {
  const { colors } = useThemeMode();
  const copy = useExperienceCopy();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [shareOpen, setShareOpen] = useState(false);
  const [readMore, setReadMore] = useState(false);
  const toneColor = toneColors(colors)[verdict.tone];
  // The lineup sentence used to print twice (lineup explanation + rationale).
  // Default view shows a one-sentence summary; the rest is behind Read more.
  const lineupExplanation = verdict.lineup_model?.explanation ?? '';
  const summary = shortSummary(verdict.rationale || lineupExplanation);
  const rationaleRest = dropRepeatedSentences(verdict.rationale ?? '', [summary]);
  const lineupRest = dropRepeatedSentences(lineupExplanation, [summary, verdict.rationale ?? '']);
  const alternatePackages = verdict.alternate_packages ?? [];
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
          <Ionicons name="alert-circle" size={13} color={colors.onAccent} />
          <AppText style={styles.extremeEyebrowText}>
            {verdict.tone === 'accept' ? 'Extremely Lopsided In Your Favor' : 'Extremely Lopsided Against You'}
          </AppText>
        </View>
      ) : null}
      <View style={styles.verdictHeaderRow}>
        <AppText style={[styles.verdictBand, isExtreme && styles.verdictBandExtreme, { color: toneColor }]}>
          {verdict.band}
        </AppText>
        <TouchableOpacity accessibilityRole="button" style={styles.shareButton} onPress={() => setShareOpen(true)} hitSlop={8}>
          <Ionicons name="share-outline" size={16} color={colors.textSecondary} />
          <AppText style={styles.shareButtonText}>Share</AppText>
        </TouchableOpacity>
      </View>
      {verdict.posture ? <PostureChip posture={verdict.posture} /> : null}
      {verdictCautions(verdict).map((caution) => (
        <View
          key={caution.code}
          testID="verdict-caution"
          accessibilityLabel={`Caution: ${caution.tag}`}
          style={[styles.lineupWarning, { borderLeftColor: colors.warning }]}
        >
          <AppText style={styles.lineupWarningHeadline}>{caution.tag}</AppText>
          <AppText style={styles.lineupWarningDetail}>{cautionDetail(caution, verdict.band)}</AppText>
        </View>
      ))}
      <BeginnerHelp text={copy.verdictHelp(verdict.ui_verdict)} style={styles.beginnerHelp} />

      {/* Quick visual: the same big color-coded value-change number the share
          PNG leads with, so the verdict reads at a glance without tapping
          Share. Rationale moved below the strip — it was cramped into the
          remaining width beside the ring before. */}
      <View style={styles.verdictHeroRow}>
        <TradeValueHero delta={verdict.value_delta} size="lg" style={styles.verdictValueHero} />
        <View style={styles.verdictMeter}>
          <MeterRow
            label="CONFIDENCE"
            value={verdict.confidence_pct != null ? `${verdict.confidence} (${Math.round(verdict.confidence_pct)}%)` : verdict.confidence}
            level={confidenceLevel(verdict)}
            color={toneColor}
          />
        </View>
      </View>
      {/* Same "who's winning" shape-reinforcement TradeValueBar gives Trade
          Hub's cards, applied to the verdict's own value_delta so the two
          surfaces agree on what a value edge looks like. */}
      <TradeValueBar delta={verdict.value_delta} style={styles.verdictValueBar} />
      <BeginnerHelp
        text={copy.help('analyzerValueBalance') && `Value balance: ${copy.help('analyzerValueBalance')}`}
        style={styles.beginnerHelp}
      />
      <BeginnerHelp
        text={copy.help('analyzerConfidence') && `Confidence: ${copy.help('analyzerConfidence')}`}
        style={styles.beginnerHelp}
      />
      {(verdict.lineup_warnings ?? []).map((warning) => (
        <View
          key={`${warning.code}-${warning.position}`}
          accessibilityRole={warning.severity === 'critical' ? 'alert' : undefined}
          style={[
            styles.lineupWarning,
            { borderLeftColor: warning.severity === 'critical' ? colors.danger : colors.warning },
          ]}
        >
          <AppText
            style={[styles.lineupWarningHeadline, warning.severity === 'critical' && { color: colors.danger }]}
          >
            {warning.headline}
          </AppText>
          <AppText style={styles.lineupWarningDetail}>{warning.detail}</AppText>
        </View>
      ))}
      {verdict.lineup_model ? (
        <View testID="lineup-model" style={styles.lineupModel}>
          <AppText style={styles.lineupModelLabel}>LINEUP IMPACT</AppText>
          <AppText
            style={[
              styles.lineupModelHeadline,
              verdict.posture_assessment?.lineup_costly && { color: colors.danger },
            ]}
          >
            {formatLineupPoints(verdict.lineup_model.points.ros_delta)} lineup pts over Weeks{' '}
            {verdict.lineup_model.weeks.first}-{verdict.lineup_model.weeks.last} (
            {formatLineupPoints(verdict.lineup_model.points.this_week_delta)} this week)
          </AppText>
        </View>
      ) : null}
      <TradeOddsEffect
        leagueId={leagueId}
        send={sendIds}
        receive={receiveIds}
        hasPicks={sendPicks.length > 0 || receivePicks.length > 0}
      />
      {summary ? (
        <VerdictSection
          icon="bulb-outline"
          label={verdict.rationale_label || 'Why this works'}
          text={summary}
          color={colors.accent}
        />
      ) : null}
      {alternatePackages.length > 0 ? (
        <View testID="alternate-packages" style={styles.lineupModel}>
          <AppText style={styles.lineupModelLabel}>
            {alternatePackages.every((pkg) => pkg.clears_bar === false) ? 'CLOSEST COUNTER' : 'TRY THIS INSTEAD'}
          </AppText>
          {alternatePackages.map((pkg, index) => (
            <View key={`${pkg.label}-${index}`} style={styles.lineupWarning}>
              <AppText style={styles.lineupWarningHeadline}>
                {pkg.label} ({pkg.ui_verdict || pkg.band})
              </AppText>
              {pkg.why ? <AppText style={styles.lineupWarningDetail}>{pkg.why}</AppText> : null}
              <ExchangeSide side="send" assets={pkg.send_assets} />
              <ExchangeSide side="get" assets={pkg.receive_assets} />
              <AppText style={styles.lineupModelFootnote}>Value balance {formatTradeGain(pkg.value_delta)}</AppText>
            </View>
          ))}
        </View>
      ) : verdict.counter_search?.status === 'none' ? (
        <AppText testID="no-counter-found" style={styles.verdictText}>
          {verdict.counter_search.message || 'No better package found.'}
        </AppText>
      ) : null}
      {verdict.counter_action ? (
        <TouchableOpacity accessibilityRole="button" style={styles.counterButton} onPress={onBuildCounter}>
          <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          <AppText style={styles.counterButtonText}>Build the counter</AppText>
        </TouchableOpacity>
      ) : null}
      <TouchableOpacity
        accessibilityRole="button"
        accessibilityState={{ expanded: readMore }}
        testID="verdict-read-more"
        onPress={() => setReadMore((v) => !v)}
        hitSlop={8}
      >
        <AppText style={styles.lineupModelLabel}>{readMore ? 'READ LESS' : 'READ MORE'}</AppText>
      </TouchableOpacity>
      {readMore ? (
        <>
          {rationaleRest ? <AppText style={[styles.verdictText, styles.verdictRationale]}>{rationaleRest}</AppText> : null}
          {lineupRest ? <AppText style={styles.lineupWarningDetail}>{lineupRest}</AppText> : null}
          {verdict.lineup_model ? (
            <AppText style={styles.lineupModelFootnote}>
              Trade score {formatTradeGain(verdict.lineup_model.trade_score)} = value balance plus lineup points under
              your posture.
            </AppText>
          ) : null}
          <VerdictSection icon="cash-outline" label="Value" text={verdict.value_summary} color={toneColor} />
          <VerdictSection icon="people-outline" label="Roster fit" text={verdict.roster_summary} color={toneColor} />
          <VerdictSection icon="compass-outline" label="Strategy fit" text={verdict.strategy_summary} color={toneColor} />
          <VerdictSection icon="warning-outline" label="Risk" text={verdict.risk_summary} color={colors.warning} />
          {verdict.counter_guidance ? (
            <VerdictSection
              icon="arrow-forward"
              label="Next move"
              text={verdict.counter_guidance}
              color={colors.accent}
            />
          ) : null}
        </>
      ) : null}

      <ShareToCommunityToggle
        key={[...sendIds, ...receiveIds].map((p) => p.player_id).join('|') + [...sendPicks, ...receivePicks].map((p) => p.pick_id).join('|') + verdict.band}
        verdict={verdict}
        send={toShareAssets(sendIds, sendPicks)}
        receive={toShareAssets(receiveIds, receivePicks)}
      />

      <NextSteps title="Want other options?" steps={['trade-finder', 'trade-hub']} leagueId={leagueId} leagueName={leagueName} />

      <TradeSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueId={leagueId}
        leagueName={leagueName}
        partnerTeamName={partnerTeamName}
        verdict={verdict}
        analyzer
        sendPicks={sendPicks}
        receivePicks={receivePicks}
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
function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    beginnerHelp: { marginBottom: spacing.xs },
  root: { flex: 1, backgroundColor: 'transparent' },
  container: { flex: 1, backgroundColor: 'transparent', padding: spacing.lg },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: 'transparent',
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 13.5, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 18 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  modeRow: { marginBottom: spacing.sm },
  sidesRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.sm },
  // The side panel is a drop target, so it needs a visible edge even when
  // inactive — a `surface` fill alone is only 1.09 against `background`.
  // The 2pt width is unchanged between states; only the color swaps.
  side: {
    flex: 1,
    backgroundColor: colors.glass,
    borderRadius: radii.md,
    borderWidth: 2,
    borderColor: colors.glassBorder,
    padding: spacing.md,
    minHeight: 80,
  },
  sideActive: { borderColor: colors.accent },
  sideLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: spacing.sm },
  sideDot: { width: 7, height: 7, borderRadius: 3.5 },
  sideLabel: { fontSize: 13.5, fontWeight: '700', color: colors.textSecondary, textTransform: 'uppercase' },
  sideLabelActive: { color: colors.accent },
  sideEmpty: { fontSize: 13.5, color: colors.textSecondary, fontStyle: 'italic' },
  // Nested inside `side` (a `surface` panel): step *up* the ramp rather than
  // down, so the asset group reads as a raised token instead of a hole
  // punched in the panel at near-identical luminance — same treatment Trade
  // Hub/Trade Finder give their own exchange-side surfaces.
  sideAssetSurface: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.md,
    paddingHorizontal: spacing.sm,
  },
  partnerBlock: { marginBottom: spacing.sm, gap: spacing.xs },
  partnerLabel: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
  partnerRow: { flexDirection: 'row', gap: spacing.xs, paddingVertical: 2 },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
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
    backgroundColor: colors.glass,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pillText: { fontSize: 13.5, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: colors.onAccent },
  analyzeButton: { marginBottom: spacing.sm },
  analyzeHint: { color: colors.textTertiary, fontSize: 13.5, marginBottom: spacing.md },
  // Quick Compare's instant readout — same label + bar shape as the full
  // verdict's value strip (below), just driven by a client-computed delta.
  quickCompareSection: { marginBottom: spacing.md },
  deltaLabel: {
    textAlign: 'center',
    fontSize: 15.5,
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
  extremeEyebrowText: { fontSize: 12.5, fontWeight: '800', color: colors.onAccent, textTransform: 'uppercase', letterSpacing: 0.3 },
  verdictHeaderRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  verdictBand: { fontSize: 19.5, fontWeight: '800', marginBottom: spacing.xs },
  verdictBandExtreme: { fontSize: 23 },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.glassBorder,
  },
  shareButtonText: { fontSize: 13.5, fontWeight: '600', color: colors.textSecondary },
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
  counterButtonText: { fontSize: 14.5, fontWeight: '700', color: colors.accent },
  verdictHeroRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  verdictValueHero: { flex: 1 },
  verdictValueBar: { marginBottom: spacing.md },
  verdictMeter: { flexShrink: 0 },
  verdictSection: { marginTop: spacing.sm, flexDirection: 'row', alignItems: 'flex-start', gap: spacing.md },
  verdictGlyph: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center' },
  verdictSectionBody: { flex: 1, minWidth: 0, alignItems: 'flex-start', gap: 4 },
  verdictLabel: {
    fontSize: 12.5,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  verdictText: { fontSize: 14.5, color: colors.textPrimary, lineHeight: 20, flex: 1 },
  // The rationale is a full-width block under the hero strip now, not a
  // flex child sharing a row with the confidence ring.
  verdictRationale: { flex: 0 },
  lineupWarning: {
    marginTop: spacing.sm,
    padding: spacing.sm,
    borderLeftWidth: 4,
    backgroundColor: colors.warningMuted,
  },
  lineupWarningHeadline: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
  lineupWarningDetail: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 19, marginTop: 2 },
  lineupModel: { marginTop: spacing.sm, gap: 2 },
  lineupModelLabel: { fontSize: 12.5, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary },
  lineupModelHeadline: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
  lineupModelFootnote: { fontSize: 12.5, color: colors.textTertiary, marginTop: 2 },
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
  planningNote: { color: colors.textSecondary, textAlign: 'center', lineHeight: 20, marginBottom: spacing.sm },
  roleNotes: { gap: spacing.xs, marginBottom: spacing.sm },
  roleNotesTitle: { fontSize: 12.5, fontWeight: '700', letterSpacing: 0.8, color: colors.textTertiary },
  roleNote: { fontSize: 14.5, lineHeight: 20, color: colors.textSecondary },
  });
}
