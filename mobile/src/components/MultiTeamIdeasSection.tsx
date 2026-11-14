import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import { multiFailureMessage } from './MultiTeamTradePanel';
import MultiTeamSharePreviewModal from './MultiTeamSharePreviewModal';
import PremiumLock from './PremiumLock';
import SkeletonBlock from './SkeletonBlock';
import ToneBadge from './ToneBadge';
import { api, type ValuationLens } from '../lib/api';
import { trackUse } from '../lib/analytics';
import {
  ideaAsResponse,
  ideaTeamLines,
  ideasSection,
  lockedTeaserTitle,
  type MultiTeamIdea,
  type MultiTeamIdeasResponse,
} from '../lib/multiTeamIdeas';
import CompactModule from './CompactModule';
import { compactCount } from '../lib/compactModule';
import { buildShareModel, toneSemantic, type SemanticTone } from '../lib/multiTeamTrade';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * "3-team ideas" in Trade Hub, the app twin of web-next's
 * MultiTeamIdeasSection: cyclic three-way deals where every team's own verdict
 * is Fair or better (GET .../trade-ideas/multi). Pro sees the ideas; Free sees
 * a locked teaser with the count. An idea opens the multi-team Analyzer
 * prefilled (it regrades the deal) and shares the same pitch card the Analyzer
 * does.
 */
export default function MultiTeamIdeasSection({
  leagueId,
  leagueName,
  lens,
  navigation,
}: {
  leagueId: string;
  leagueName: string;
  lens: ValuationLens;
  navigation: NativeStackNavigationProp<RootStackParamList>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [attempt, setAttempt] = useState(0);
  const [response, setResponse] = useState<MultiTeamIdeasResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setResponse(null);
    setError(null);
    api
      .getMultiTeamTradeIdeas(leagueId, lens)
      .then((result) => {
        if (!cancelled) setResponse(result);
      })
      .catch((err) => {
        if (!cancelled) setError(multiFailureMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, attempt]);

  const section = response ? ideasSection(response) : null;
  const parts = error
    ? [{ key: 'e', text: "Couldn't load 3-team ideas", tone: 'danger' as const }]
    : !section
      ? [{ key: 'l', text: 'Looking for 3-team deals' }]
      : section.kind === 'ideas'
        ? [{ key: 'n', text: compactCount(section.ideas.length, '3-team deal'), strong: true }, { key: 'f', text: 'fair for every team' }]
        : section.kind === 'locked'
          ? [{ key: 'n', text: lockedTeaserTitle(section.count), strong: true }, { key: 'p', text: 'Pro', tone: 'action' as const }]
          : [{ key: 'm', text: section.kind === 'closed' ? 'Trading is closed' : 'No 3-team deals right now' }];
  return (
    <View style={styles.root} testID="multi-team-ideas">
      <CompactModule id="trades.multi" title="3-team ideas" tone="action" parts={parts}>
      <AppText style={styles.secondary}>
        Three-way deals where your surplus players and picks fill one team&apos;s need, theirs fills another&apos;s, and every team still comes out fair.
      </AppText>
      {error ? (
        <ErrorState title="Couldn't load 3-team ideas" message={error} onRetry={() => setAttempt((n) => n + 1)} compact />
      ) : !section ? (
        <View style={styles.skeletons} testID="multi-team-ideas-skeleton" accessibilityLabel="Looking for 3-team deals">
          <SkeletonBlock height={140} />
          <SkeletonBlock height={140} />
        </View>
      ) : section.kind === 'locked' ? (
        <PremiumLock
          feature="3_team_ideas"
          title={response?.upsell?.title ?? lockedTeaserTitle(section.count)}
          description={response?.upsell?.body ?? 'Pro finds three-way deals where every team still comes out fair.'}
          leagueName={leagueName}
          example={lockedTeaserTitle(section.count)}
        />
      ) : section.kind === 'empty' || section.kind === 'closed' ? (
        <EmptyState
          icon="git-network-outline"
          title={section.kind === 'closed' ? 'Trading is closed' : 'No 3-team deals right now'}
          subtitle={section.message}
        />
      ) : (
        section.ideas.map((idea) => (
          <IdeaCard key={idea.id} idea={idea} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
        ))
      )}
      </CompactModule>
    </View>
  );
}

function IdeaCard({
  idea,
  leagueId,
  leagueName,
  navigation,
}: {
  idea: MultiTeamIdea;
  leagueId: string;
  leagueName: string;
  navigation: NativeStackNavigationProp<RootStackParamList>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [shareOpen, setShareOpen] = useState(false);
  const toneColor = (tone: SemanticTone) =>
    tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : tone === 'danger' ? colors.danger : colors.textSecondary;
  const lines = ideaTeamLines(idea);
  const perWeek = idea.user.lineup_delta?.per_week ?? 0;
  return (
    <AccentCard accent={toneColor(toneSemantic(idea.user.outcome === 'wins' ? 'accept' : 'fair'))}>
      <View style={styles.badgeRow}>
        <ToneBadge label="3-TEAM" color={colors.accent} />
        {idea.variant ? <ToneBadge label="ONE ADDED PIECE" color={colors.textSecondary} /> : null}
      </View>
      <AppText style={styles.headline}>{idea.headline}</AppText>
      <AppText style={styles.secondary}>
        For you: value {lines[0]?.valueChange ?? '0'}
        {Math.abs(perWeek) >= 0.5 ? `, lineup ${perWeek > 0 ? '+' : ''}${perWeek.toFixed(1)} pts a week` : ''}.
      </AppText>
      {lines.map((line) => (
        <View key={line.rosterId} style={styles.teamLine} testID="idea-team-line">
          <View style={styles.badgeRow}>
            <AppText style={styles.teamName}>{line.name}</AppText>
            <ToneBadge label={line.verdict.toUpperCase()} color={toneColor(toneSemantic(line.tone))} />
            <AppText style={styles.muted}>value {line.valueChange}</AppText>
          </View>
          <AppText style={styles.secondary}>
            Gets {line.gets}. Sends {line.sends}.
          </AppText>
          {line.why ? <AppText style={styles.muted}>{line.why}</AppText> : null}
        </View>
      ))}
      {idea.variant ? <AppText style={styles.muted}>{idea.variant.note}</AppText> : null}
      <View style={styles.actions}>
        <Button
          label="Open in Analyzer"
          size="sm"
          onPress={() => {
            trackUse('trade_hub', 'multi_idea_opened', { leagueId });
            navigation.navigate('Trades', {
              leagueId,
              leagueName,
              initialTab: 'make',
              multiPrefill: idea.analyzer_request.transfers,
            });
          }}
        />
        <Button label="Share the pitch" size="sm" variant="secondary" onPress={() => setShareOpen(true)} />
      </View>
      <MultiTeamSharePreviewModal
        visible={shareOpen}
        onClose={() => setShareOpen(false)}
        leagueId={leagueId}
        leagueName={leagueName}
        model={buildShareModel(ideaAsResponse(idea))}
      />
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { gap: spacing.sm, marginTop: spacing.lg },
    title: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    secondary: { fontSize: 13, color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    skeletons: { gap: spacing.sm },
    headline: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    badgeRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.xs },
    teamLine: { gap: 2 },
    teamName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    actions: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginTop: spacing.xs },
  });
}
