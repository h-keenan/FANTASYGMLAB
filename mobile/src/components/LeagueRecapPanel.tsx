import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import ErrorState from './ErrorState';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { keepPreviousData, useIsRestoring, useQuery } from '@tanstack/react-query';

import CompactModule from './CompactModule';
import EmptyState from './EmptyState';
import ManagerProfileModal from './ManagerProfileModal';
import ModuleMore from './ModuleMore';
import PlayerAccordionRow, { usePlayerAccordion } from './PlayerAccordionRow';
import { PresenceSwap } from './Presence';
import RoundupPanel from './RoundupPanel';
import RecapSharePreviewModal from './RecapSharePreviewModal';
import PageControlRow, { ViewTabs, WeekSelect } from './PageControlRow';
import { SkeletonModule, SkeletonPage, SkeletonRegion, SkeletonStatusHeader } from './Skeleton';
import StatusHeader from './StatusHeader';
import TeamAvatar from './TeamAvatar';
import TradeCompactCard, { TradeAssetCard, type TradeCardAsset } from './TradeCompactCard';
import { api, type RecapStory, type RecapTradeAsset, type WeeklyRecap } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { markRecapOpened } from '../lib/recapSeen';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { buildRecapPage, isMatchupStory, recapFaab, recapMetric, recapScoreline, recapWeekChips, storyInvolves, type RecapSection } from '../lib/recapPage';
import Money from './Money';
import { formatMoney } from '../lib/money';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type RecapView = 'Recaps' | 'Roundup';
const RECAP_VIEWS: readonly RecapView[] = ['Recaps', 'Roundup'];

export type RosterMap = Record<string, { playerIds: string[]; teamName: string; avatarId: string; ownerName: string }>;

/**
 * The weekly recap, built from the shared templates (docs/ui-patterns.md, "Weekly recap page"): ONE week strip (the shared
 * segmented control, scrolling with the active week centred), a StatusHeader with the week's result, then a CompactModule per
 * kind of story that expands in place into team rows with crests, player rows with avatars and the shared trade card. Gold
 * marks only the week's scoring leader. Every value comes from `GET .../recap`; the crests come from the team profiles.
 * Twin of web-next/src/components/RecapWeekView.tsx; the model is lib/recapPage.ts.
 */
export default function LeagueRecapPanel({
  leagueId,
  leagueName,
  initialTab,
  week: requestedRoundupWeek,
  leading = null,
}: {
  leagueId: string;
  leagueName: string;
  initialTab?: 'recap' | 'roundup';
  week?: number;
  /** The page's section select (NFL / My League): first in the one control row. */
  leading?: React.ReactNode;
}) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [tab, setTab] = useState<'recap' | 'roundup'>(initialTab ?? 'recap');
  // Picked from the GM orb or a weekly-roundup push while Recaps is already open.
  useEffect(() => {
    if (initialTab) setTab(initialTab);
  }, [initialTab]);
  const [selectedWeek, setSelectedWeek] = useState<number | null>(null);
  const [shareOpen, setShareOpen] = useState(false);
  const [rosterMap, setRosterMap] = useState<RosterMap>({});
  const [profile, setProfile] = useState<{ rosterId: string; teamName: string } | null>(null);
  const isRestoring = useIsRestoring();
  // Own cache entry (the response carries `my_roster_id`, which the shared current-recap entry used by Today and Alerts does not).
  const recapQuery = useQuery({
    queryKey: [...queryKeys.recap(leagueId), 'page', selectedWeek ?? 'latest'] as const,
    queryFn: () => api.getLeagueRecap(leagueId, { ...(selectedWeek != null ? { week: selectedWeek } : null), me: true }),
    enabled: !isRestoring,
    // A week switch shows the new week's skeleton; the previous response stays as placeholder so the guards below have data.
    placeholderData: keepPreviousData,
  });
  const recapData = recapQuery.data;
  const recap: WeeklyRecap | null = recapData?.recap ?? null;
  const maxCompletedWeek = recapData?.max_completed_week ?? 0;
  const myRosterId = recapData?.my_roster_id ?? '';
  const notReady = recapData != null && !recapData.recap;
  const loading = isRestoring || recapQuery.isFetching;
  const error = recapQuery.isError && !recapData ? toUserErrorMessage(recapQuery.error, 'Failed to load recap.') : null;

  // Marks this exact recap (by fingerprint-based recap_id) as opened on this device so Today's "new recap" module goes away.
  useEffect(() => {
    if (recap && !recap.incomplete) void markRecapOpened(leagueId, recap.recap_id);
  }, [leagueId, recap]);

  // Crests and the roster ids team rows open (best effort: a miss shows the initials ring).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [rostersResult, profilesResult] = await Promise.all([api.getLeagueRosters(leagueId), api.getLeagueTeamProfiles(leagueId)]);
        if (cancelled) return;
        const map: RosterMap = {};
        for (const roster of rostersResult.rosters) {
          const rosterId = String(roster.roster_id ?? '');
          if (!rosterId) continue;
          const players = Array.isArray(roster.players) ? roster.players : [];
          map[rosterId] = {
            playerIds: players.map(String),
            teamName: profilesResult.profiles[rosterId]?.team_name || '',
            avatarId: profilesResult.profiles[rosterId]?.avatar_id || '',
            ownerName: profilesResult.profiles[rosterId]?.owner_name || '',
          };
        }
        setRosterMap(map);
      } catch {
        /* non-fatal */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const openTeam = (rosterId: string, fallbackName: string) => setProfile({ rosterId, teamName: rosterMap[rosterId]?.teamName || fallbackName });

  const viewSelect = (
    <ViewTabs<RecapView>
      options={RECAP_VIEWS}
      value={tab === 'roundup' ? 'Roundup' : 'Recaps'}
      onChange={(label) => setTab(label === 'Roundup' ? 'roundup' : 'recap')}
      testID="recap-view-select"
    />
  );
  const controlRow = (weekSelect: React.ReactNode = null) => (
    <PageControlRow testID="recap-controls">
      {leading}
      {viewSelect}
      {weekSelect}
    </PageControlRow>
  );

  if (tab === 'roundup') {
    return (
      <View style={styles.root}>
        <RoundupPanel
          leagueId={leagueId}
          leagueName={leagueName}
          initialWeek={requestedRoundupWeek}
          bottomInset={orbClearance}
          leading={<>{leading}{viewSelect}</>}
        />
      </View>
    );
  }

  if (loading && !recap) {
    return (
      <View style={styles.root}>
        {controlRow()}
        <SkeletonPage label="League Recaps" layout="detail" style={{ paddingHorizontal: 0 }} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.root}>
        {controlRow()}
        <ErrorState title="Couldn't load the recap" message={error} onRetry={() => void recapQuery.refetch()} />
      </View>
    );
  }

  const chips = recapWeekChips(maxCompletedWeek);
  const activeWeek = String(selectedWeek ?? recap?.week ?? maxCompletedWeek);
  const weekStrip = controlRow(<WeekSelect weeks={chips.map((c) => Number(c.value))} value={Number(activeWeek)} onChange={setSelectedWeek} />);

  if (notReady || !recap) {
    return (
      <View style={styles.root}>
        {weekStrip}
        <EmptyState icon="newspaper-outline" title="Recap not ready yet" subtitle="Check back after this week's matchups finish scoring." />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      {weekStrip}
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        {loading ? (
          <SkeletonRegion label="Weekly recap" style={styles.stack}>
            <SkeletonStatusHeader rows={0} />
            <SkeletonModule lines={2} />
            <SkeletonModule lines={2} />
            <SkeletonModule lines={2} />
          </SkeletonRegion>
        ) : (
          <PresenceSwap swapKey={`week-${recap.week}`}>
            <RecapBody recap={recap} myRosterId={myRosterId} rosterMap={rosterMap} openTeam={openTeam} onShare={() => setShareOpen(true)} onOpenTrades={() => navigation.navigate('TradeHistory')} />
          </PresenceSwap>
        )}
      </ScrollView>
      <RecapSharePreviewModal visible={shareOpen} onClose={() => setShareOpen(false)} leagueName={leagueName} recap={recap} rosterMap={rosterMap} />
      {profile ? (
        <ManagerProfileModal
          visible
          onClose={() => setProfile(null)}
          leagueId={leagueId}
          leagueName={leagueName}
          rosterId={profile.rosterId}
          teamName={profile.teamName}
          ownerName={rosterMap[profile.rosterId]?.ownerName || null}
          avatarId={rosterMap[profile.rosterId]?.avatarId || null}
        />
      ) : null}
    </View>
  );
}

type OpenTeam = (rosterId: string, fallbackName: string) => void;

function RecapBody({
  recap,
  myRosterId,
  rosterMap,
  openTeam,
  onShare,
  onOpenTrades,
}: {
  recap: WeeklyRecap;
  myRosterId: string;
  rosterMap: RosterMap;
  openTeam: OpenTeam;
  onShare: () => void;
  onOpenTrades: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const page = buildRecapPage(recap, myRosterId);
  const leader = page.hero.leader;
  return (
    <StatusHeader
      model={{
        kicker: page.hero.kicker,
        headline: page.hero.headline,
        context: page.hero.context,
        ring: page.hero.ring,
        stats: page.hero.stats,
        attention: [],
        primary: recap.incomplete ? null : { label: 'Share recap', actionKey: 'share' },
      }}
      onAction={() => onShare()}
      testID="recap-status-header"
    >
      {leader ? (
        <View style={styles.leaderStrip} testID="recap-leader">
          <TeamRow
            name={leader.team}
            rosterId={leader.rosterId}
            avatarId={rosterMap[leader.rosterId]?.avatarId}
            mine={Boolean(myRosterId) && leader.rosterId === myRosterId}
            gold
            sub="Scoring leader"
            trailing={leader.points}
            openTeam={openTeam}
          />
        </View>
      ) : null}
      {recap.incomplete || page.sections.length === 0 ? (
        <AppText style={styles.muted}>{recap.empty_reason || 'Not enough historical data for a recap this week.'}</AppText>
      ) : (
        page.sections.map((section, index) => (
          <SectionModule key={section.key} section={section} index={index} rosterMap={rosterMap} myRosterId={myRosterId} openTeam={openTeam} onOpenTrades={onOpenTrades} />
        ))
      )}
    </StatusHeader>
  );
}

function SectionModule({ section, index, rosterMap, myRosterId, openTeam, onOpenTrades }: { section: RecapSection; index: number; rosterMap: RosterMap; myRosterId: string; openTeam: OpenTeam; onOpenTrades: () => void }) {
  const acc = usePlayerAccordion();
  return (
    <CompactModule id={`recap.${section.key}`} title={section.title} parts={section.parts} defaultOpen={index === 0} testID={`recap-section-${section.key}`}>
      {section.stories.map((story, i) => (
        <StoryBody key={`${story.story_type}-${i}`} story={story as RecapStory} idKey={`${story.story_type}-${i}`} rosterMap={rosterMap} myRosterId={myRosterId} openTeam={openTeam} acc={acc} onOpenTrades={onOpenTrades} />
      ))}
    </CompactModule>
  );
}

function YouChip() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.youChip}>
      <AppText style={styles.youText}>YOU</AppText>
    </View>
  );
}

/** A team: crest, name (wraps, never cut off), an optional "You" marker and one trailing figure. Taps open the manager profile. */
function TeamRow({
  name,
  rosterId,
  avatarId,
  mine,
  trailing,
  sub,
  muted = false,
  gold = false,
  openTeam,
}: {
  name: string;
  rosterId: string;
  avatarId?: string;
  mine: boolean;
  trailing?: string;
  sub?: string;
  muted?: boolean;
  gold?: boolean;
  openTeam: OpenTeam;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const body = (
    <>
      <TeamAvatar avatarId={avatarId} name={name} size={36} style={gold ? { borderWidth: 2, borderColor: colors.premium } : undefined} />
      <View style={styles.teamMain}>
        <View style={styles.teamNameLine}>
          <AppText style={[styles.teamName, muted && styles.teamNameMuted]}>{name}</AppText>
          {mine ? <YouChip /> : null}
        </View>
        {sub ? <AppText style={styles.teamSub}>{sub}</AppText> : null}
      </View>
      {trailing ? <AppText style={styles.teamFigure}><Money>{trailing}</Money></AppText> : null}
    </>
  );
  if (!rosterId) return <View style={styles.teamRow}>{body}</View>;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${name}, open manager profile`} onPress={() => openTeam(rosterId, name)} style={styles.teamRow}>
      {body}
    </Pressable>
  );
}

function Chip({ children }: { children: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.chip}>
      <AppText style={styles.chipText}>{children}</AppText>
    </View>
  );
}

function tradeAsset(asset: RecapTradeAsset, key: string): TradeCardAsset {
  if (asset.kind === 'pick') return { key, pickLabel: asset.label || asset.name };
  return { key, player: { id: asset.player_id || null, name: asset.name, position: asset.position ?? null, team: asset.team ?? null } };
}

function tradeSides(story: RecapStory): { team_name: string; roster_id: string; assets: RecapTradeAsset[] }[] {
  if (story.sides && story.sides.length > 0) return story.sides.map((s) => ({ team_name: s.team_name, roster_id: s.roster_id, assets: s.assets ?? [] }));
  return [
    { team_name: story.primary_team, roster_id: story.primary_roster_id, assets: story.left_assets ?? [] },
    { team_name: story.secondary_team, roster_id: story.secondary_roster_id, assets: story.right_assets ?? [] },
  ].filter((s) => s.team_name);
}

function StoryFrame({ story, children }: { story: RecapStory; children: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.story} testID="recap-story">
      <AppText style={styles.storyTitle}>{story.title}</AppText>
      {children}
      {story.summary ? <AppText style={styles.summary}>{story.summary}</AppText> : null}
      {story.editorial_label ? <Chip>{story.editorial_label}</Chip> : null}
    </View>
  );
}

function TradeStory({ story, myRosterId, onOpenTrades }: { story: RecapStory; myRosterId: string; onOpenTrades: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const sides = tradeSides(story);
  const details = (
    <>
      {story.value_lenses?.map((lens) => (
        <AppText key={lens.lens} style={styles.note}>{`${lens.label}: ${lens.note}`}</AppText>
      ))}
      <ModuleMore label="View trade history" onPress={onOpenTrades} />
    </>
  );
  const hasAssets = sides.some((s) => s.assets.length > 0);
  const title = `${story.title}${storyInvolves(story, myRosterId) ? ' · you' : ''}`;
  if (hasAssets && sides.length === 2) {
    return (
      <TradeCompactCard
        title={title}
        give={sides[0].assets.map((a, i) => tradeAsset(a, `a${i}`))}
        get={sides[1].assets.map((a, i) => tradeAsset(a, `b${i}`))}
        giveLabel={`${sides[0].team_name} got`}
        getLabel={`${sides[1].team_name} got`}
        meta={[story.editorial_label ?? ''].filter(Boolean)}
        meter={null}
        testID="recap-trade-card"
      >
        {story.summary ? <AppText style={styles.summary}>{story.summary}</AppText> : null}
        {details}
      </TradeCompactCard>
    );
  }
  return (
    <View style={styles.tradeCard} testID="recap-trade-card">
      <AppText style={styles.tradeTitle}>{story.title}</AppText>
      {sides.map((side, i) => (
        <View key={`${side.roster_id}-${i}`} style={styles.tradeSide}>
          <AppText style={styles.tradeKicker}>{`${side.team_name} got`}</AppText>
          {side.assets.map((a, j) => (
            <TradeAssetCard key={j} asset={tradeAsset(a, `s${i}-${j}`)} mode="desk" />
          ))}
        </View>
      ))}
      {story.summary ? <AppText style={styles.summary}>{story.summary}</AppText> : null}
      {details}
    </View>
  );
}

function StoryBody({
  story,
  idKey,
  rosterMap,
  myRosterId,
  openTeam,
  acc,
  onOpenTrades,
}: {
  story: RecapStory;
  idKey: string;
  rosterMap: RosterMap;
  myRosterId: string;
  openTeam: OpenTeam;
  acc: ReturnType<typeof usePlayerAccordion>;
  onOpenTrades: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const mine = (rosterId: string) => Boolean(myRosterId) && rosterId === myRosterId;
  const avatar = (rosterId: string) => rosterMap[rosterId]?.avatarId || undefined;
  if (story.story_type === 'trade') return <TradeStory story={story} myRosterId={myRosterId} onOpenTrades={onOpenTrades} />;
  if (story.story_type === 'waiver' || story.story_type === 'waiver_low') {
    const asset = story.player_assets?.find((a) => a.player_id);
    const faab = recapFaab(story);
    if (!asset) {
      return (
        <StoryFrame story={story}>
          <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} avatarId={avatar(story.primary_roster_id)} mine={mine(story.primary_roster_id)} openTeam={openTeam} trailing={faab != null ? formatMoney(faab) : undefined} sub={story.players.join(', ')} />
        </StoryFrame>
      );
    }
    return (
      <View style={styles.story} testID="recap-story">
        <AppText style={styles.storyTitle}>{story.title}</AppText>
        <PlayerAccordionRow
          player={{ id: asset.player_id, name: asset.name, position: asset.position ?? null, team: asset.team ?? null }}
          mode="desk"
          metaText={[asset.team, 'Added'].filter(Boolean).join(' · ')}
          trailingFact={faab != null ? { key: 'faab', label: 'FAAB', value: formatMoney(faab), tone: 'success' } : null}
          open={acc.isOpen(idKey)}
          onToggle={() => acc.toggle(idKey)}
          testID="recap-waiver-row"
        >
          <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} avatarId={avatar(story.primary_roster_id)} mine={mine(story.primary_roster_id)} openTeam={openTeam} sub="Claimed by" />
          {story.summary ? <AppText style={styles.summary}>{story.summary}</AppText> : null}
        </PlayerAccordionRow>
      </View>
    );
  }
  if (isMatchupStory(story)) {
    const score = recapScoreline(story);
    return (
      <StoryFrame story={story}>
        <View>
          <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} avatarId={avatar(story.primary_roster_id)} mine={mine(story.primary_roster_id)} openTeam={openTeam} trailing={score?.winner} sub="Won" />
          <TeamRow name={story.secondary_team} rosterId={story.secondary_roster_id} avatarId={avatar(story.secondary_roster_id)} mine={mine(story.secondary_roster_id)} openTeam={openTeam} trailing={score?.loser} sub="Lost" muted />
        </View>
        {recapMetric(story) ? <Chip>{`${story.metric_label || 'Margin'} ${recapMetric(story)}`}</Chip> : null}
      </StoryFrame>
    );
  }
  const metric = recapMetric(story);
  const isPoints = story.story_type.startsWith('performance');
  return (
    <StoryFrame story={story}>
      <TeamRow
        name={story.primary_team}
        rosterId={story.primary_roster_id}
        avatarId={avatar(story.primary_roster_id)}
        mine={mine(story.primary_roster_id)}
        openTeam={openTeam}
        sub={isPoints ? 'Points' : story.metric_label || undefined}
        trailing={metric || undefined}
      />
      {story.players.length > 0 ? (
        <View style={styles.chipRow}>
          {story.players.map((name) => (
            <Chip key={name}>{name}</Chip>
          ))}
        </View>
      ) : null}
    </StoryFrame>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { gap: spacing.md },
    stack: { gap: spacing.sm },
    muted: { fontSize: 14, color: colors.textTertiary },
    leaderStrip: { backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.md, paddingHorizontal: spacing.md, minHeight: 44 },
    teamRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    teamMain: { flex: 1, minWidth: 0 },
    teamNameLine: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 6 },
    teamName: { flexShrink: 1, fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    teamNameMuted: { color: colors.textSecondary },
    teamSub: { fontSize: 12, color: colors.textTertiary },
    teamFigure: { fontSize: 17, fontWeight: '800', color: colors.textPrimary, fontVariant: ['tabular-nums'] },
    youChip: { height: 18, paddingHorizontal: 6, borderRadius: radii.pill, backgroundColor: colors.accentMuted, justifyContent: 'center' },
    youText: { fontSize: 12, fontWeight: '800', color: colors.accentOnTint, letterSpacing: 0.6 },
    story: { gap: 6 },
    storyTitle: { fontSize: 12.5, fontWeight: '700', color: colors.textSecondary },
    summary: { fontSize: 14, color: colors.textSecondary, lineHeight: 19 },
    note: { fontSize: 12, color: colors.textTertiary },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
    chip: { alignSelf: 'flex-start', minHeight: 24, paddingHorizontal: 8, borderRadius: radii.pill, justifyContent: 'center', backgroundColor: colors.accentMuted, borderWidth: 1, borderColor: colors.glassBorder },
    chipText: { fontSize: 12, fontWeight: '700', color: colors.textSecondary },
    tradeCard: { gap: spacing.sm, padding: spacing.md, backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.tile },
    tradeTitle: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    tradeSide: { gap: 2 },
    tradeKicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
  });
}
