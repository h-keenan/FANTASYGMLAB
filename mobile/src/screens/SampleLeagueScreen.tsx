import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import PositionBadge from '../components/PositionBadge';
import SampleLeagueBanner from '../components/SampleLeagueBanner';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ToneBadge from '../components/ToneBadge';
import ValueStat from '../components/ValueStat';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  SAMPLE_GAME_PLAN,
  SAMPLE_LEAGUE_NAME,
  SAMPLE_ROSTER,
  SAMPLE_TABS,
  SAMPLE_TEAM_NAME,
  SAMPLE_TRADE,
  sampleTradeVerdict,
  type SamplePlayer,
  type SampleTab,
} from '../lib/sampleLeague';
import { useOrbClearance } from '../lib/orbLayout';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { spacing, type ThemeColors } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'SampleLeague'>;

/**
 * Static sample league for users with no league connected. No network calls,
 * no auth requirement, no analytics beyond nothing (RootNavigator skips
 * screen tracking for this route). Web twin: SampleLeagueContent.tsx.
 */
export default function SampleLeagueScreen({ navigation }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const headerHeight = useHeaderHeight();
  const orbClearance = useOrbClearance();
  const [tab, setTab] = useState<SampleTab>('roster');

  // Home hosts the Add League sheet; openAddLeague opens it on arrival.
  const connect = () => navigation.navigate('Home', { openAddLeague: true });

  const playerRow = (player: SamplePlayer) => (
    <View key={player.id} style={styles.playerRow}>
      <View style={styles.badgeSlot}>
        <PositionBadge position={player.position} />
      </View>
      <View style={styles.playerText}>
        <AppText style={styles.playerName}>{player.name}</AppText>
        <AppText style={styles.muted}>
          Age {player.age} · {player.note}
        </AppText>
      </View>
      <ValueStat value={player.value} />
    </View>
  );

  const verdict = sampleTradeVerdict(SAMPLE_TRADE);
  const verdictColor =
    verdict.tone === 'success' ? colors.success : verdict.tone === 'danger' ? colors.danger : colors.accent;

  return (
    <>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}
      >
        <SampleLeagueBanner onConnect={connect} />
        <View>
          <AppText style={styles.title}>{SAMPLE_TEAM_NAME}</AppText>
          <AppText style={styles.muted}>{SAMPLE_LEAGUE_NAME} (sample)</AppText>
        </View>
        <SegmentedTabBar<SampleTab>
          options={SAMPLE_TABS.map((t) => ({ key: t.value, label: t.label }))}
          active={tab}
          onChange={setTab}
        />

        {tab === 'roster' ? (
          <>
            <SectionHeading title="Roster" caption="Sample scores are made-up 0-100 numbers." />
            <AccentCard accent={colors.accent} compact>
              {SAMPLE_ROSTER.map(playerRow)}
            </AccentCard>
          </>
        ) : null}

        {tab === 'game_plan' ? (
          <>
            <SectionHeading title="Game Plan" />
            {SAMPLE_GAME_PLAN.map((item) => (
              <AccentCard key={item.headline} accent={colors.accent}>
                <AppText style={styles.kicker}>{item.kicker}</AppText>
                <AppText style={styles.cardTitle}>{item.headline}</AppText>
                <AppText style={styles.muted}>{item.reason}</AppText>
                <TouchableOpacity
                  accessibilityRole="button"
                  onPress={() => setTab(item.cta === 'trade' ? 'trade' : 'roster')}
                >
                  <AppText style={styles.link}>
                    {item.cta === 'trade' ? 'Open sample trade' : 'Open sample roster'} →
                  </AppText>
                </TouchableOpacity>
              </AccentCard>
            ))}
          </>
        ) : null}

        {tab === 'trade' ? (
          <>
            <SectionHeading title="Trade" caption={`Sample offer with ${SAMPLE_TRADE.partner}`} />
            <AccentCard accent={verdictColor}>
              <View style={styles.verdictRow}>
                <ToneBadge label={verdict.label} color={verdictColor} />
                <AppText style={styles.muted}>
                  You send {verdict.giveTotal}, you get {verdict.getTotal}
                </AppText>
              </View>
              <AppText style={styles.kicker}>You give</AppText>
              {SAMPLE_TRADE.give.map(playerRow)}
              <AppText style={styles.kicker}>You get</AppText>
              {SAMPLE_TRADE.get.map(playerRow)}
              <AppText style={styles.muted}>
                Sample verdict: a real one weighs your roster needs, league scoring and what this manager tends to accept.
              </AppText>
            </AccentCard>
          </>
        ) : null}
      </ScrollView>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1 },
    content: { paddingHorizontal: spacing.lg, gap: spacing.lg },
    title: { fontSize: 24, fontWeight: '900', color: colors.textPrimary },
    muted: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    kicker: { fontSize: 11, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.accent },
    cardTitle: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
    link: { fontSize: 14, fontWeight: '700', color: colors.accent },
    badgeSlot: { width: 40, alignItems: 'flex-start' },
    playerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingVertical: spacing.sm },
    playerText: { flex: 1 },
    playerName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    verdictRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  });
}
