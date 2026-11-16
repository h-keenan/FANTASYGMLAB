import React, { useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import PressableScale from '../components/PressableScale';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AppText from '../components/AppText';
import GridBackground from '../components/GridBackground';
import CompactModule from '../components/CompactModule';
import PlayerAccordionRow, { usePlayerAccordion } from '../components/PlayerAccordionRow';
import StatusHeader from '../components/StatusHeader';
import TradeCompactCard, { type TradeCardAsset } from '../components/TradeCompactCard';
import type { StatusHeaderModel } from '../lib/statusHeader';
import SampleDashboard from '../components/SampleDashboard';
import SampleLeagueBanner, { SampleConnectModule } from '../components/SampleLeagueBanner';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import ToneBadge from '../components/ToneBadge';
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
  const [tab, setTab] = useState<SampleTab>('dashboard');

  // Home hosts the Add League sheet; openAddLeague opens it on arrival.
  // Signed out (reached from the sign-in screen) there is no Home yet: go back to sign in instead.
  const connect = () =>
    navigation.getState().routeNames.includes('Home') ? navigation.navigate('Home', { openAddLeague: true }) : navigation.goBack();

  const acc = usePlayerAccordion();
  // Fictional players have no photo: id null keeps the shared avatar slot on initials.
  const playerRef = (player: SamplePlayer) => ({ id: null, name: player.name, position: player.position, age: player.age });
  const playerRow = (player: SamplePlayer) => (
    <PlayerAccordionRow
      key={player.id}
      player={playerRef(player)}
      mode="desk"
      value={player.value}
      metaText={`Age ${player.age}`}
      open={acc.isOpen(player.id)}
      onToggle={() => acc.toggle(player.id)}
      testID="sample-player"
    >
      <AppText style={styles.muted}>{player.note}</AppText>
    </PlayerAccordionRow>
  );
  const tradeAsset = (player: SamplePlayer): TradeCardAsset => ({ key: player.id, player: playerRef(player), detail: `Age ${player.age} · ${player.note}`, value: player.value });
  const avgAge = SAMPLE_ROSTER.reduce((sum, p) => sum + p.age, 0) / SAMPLE_ROSTER.length;
  const [firstMove, ...otherMoves] = SAMPLE_GAME_PLAN;
  const planModel: StatusHeaderModel = {
    kicker: firstMove.kicker,
    headline: firstMove.headline,
    context: 'Sample moves for Demo Squad',
    ring: null,
    stats: [
      { key: 'moves', label: 'Moves', value: String(SAMPLE_GAME_PLAN.length) },
      { key: 'sell', label: 'Sell', value: '1', tone: 'warning' },
      { key: 'add', label: 'Add', value: '1', tone: 'success' },
    ],
    attention: SAMPLE_GAME_PLAN.map((item, index) => {
      const player = SAMPLE_ROSTER.find((p) => p.id === item.playerId) ?? SAMPLE_ROSTER[0];
      return { key: `${item.kicker}-${index}`, playerId: null, name: player.name, position: player.position, team: null, meta: item.kicker, stat: { value: String(player.value), label: 'VALUE' }, detail: item.reason };
    }),
    primary: { label: firstMove.cta === 'trade' ? 'Open sample trade' : 'Open sample roster', actionKey: firstMove.cta },
  };

  const verdict = sampleTradeVerdict(SAMPLE_TRADE);
  const verdictColor =
    verdict.tone === 'success' ? colors.success : verdict.tone === 'danger' ? colors.danger : colors.accent;

  return (
    <>
      <GridBackground />
      <ScrollView
        style={styles.container}
        // The tab strip (child 2) stays pinned while the page scrolls, like a real league's tab strip.
        stickyHeaderIndices={[2]}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}
      >
        <SampleLeagueBanner onConnect={connect} />
        <View>
          <AppText style={styles.title}>{SAMPLE_TEAM_NAME}</AppText>
          <AppText style={styles.muted}>{SAMPLE_LEAGUE_NAME} (sample)</AppText>
        </View>
        <SegmentedTabBar<SampleTab>
          options={SAMPLE_TABS.map((t) => ({ key: t.value, label: t.label, glyph: t.glyph }))}
          active={tab}
          onChange={setTab}
        />

        {tab === 'dashboard' ? <SampleDashboard /> : null}

        {tab === 'roster' ? (
          <>
            <SectionHeading title="Roster" caption="Sample scores are made-up 0-100 numbers." />
            <CompactModule id="sample.roster" title="Roster" parts={[{ key: 'n', text: `${SAMPLE_ROSTER.length} players`, strong: true }, { key: 'age', text: `Avg age ${avgAge.toFixed(1)}` }]} defaultOpen persist={false}>
              {SAMPLE_ROSTER.map(playerRow)}
            </CompactModule>
          </>
        ) : null}

        {tab === 'game_plan' ? (
          <>
            <SectionHeading title="Today" />
            <StatusHeader model={planModel} attentionTitle="Top moves" onAction={(key) => setTab(key === 'trade' ? 'trade' : 'roster')}>
              {otherMoves.map((item) => (
                <CompactModule key={item.headline} id={`sample.plan.${item.playerId}`} title={item.kicker} parts={[{ key: 'h', text: item.headline, strong: true }]} persist={false}>
                  <AppText style={styles.muted}>{item.reason}</AppText>
                  <PressableScale accessibilityRole="button" onPress={() => setTab(item.cta === 'trade' ? 'trade' : 'roster')}>
                    <AppText style={styles.link}>
                      {item.cta === 'trade' ? 'Open sample trade' : 'Open sample roster'} →
                    </AppText>
                  </PressableScale>
                </CompactModule>
              ))}
            </StatusHeader>
          </>
        ) : null}

        {tab === 'trade' ? (
          <>
            <SectionHeading title="Trade" caption={`Sample offer with ${SAMPLE_TRADE.partner}`} />
            <View style={styles.verdictRow}>
              <ToneBadge label={verdict.label} color={verdictColor} />
              <AppText style={styles.muted}>
                You send {verdict.giveTotal}, you get {verdict.getTotal}
              </AppText>
            </View>
            <TradeCompactCard title={`Offer with ${SAMPLE_TRADE.partner}`} give={SAMPLE_TRADE.give.map(tradeAsset)} get={SAMPLE_TRADE.get.map(tradeAsset)} netValue={verdict.gap} defaultOpen testID="sample-trade-card">
              <AppText style={styles.muted}>
                Sample verdict: a real one weighs your roster needs, league scoring and what this manager tends to accept.
              </AppText>
            </TradeCompactCard>
            <SampleConnectModule onConnect={connect} />
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
    title: { fontSize: 25, fontWeight: '900', color: colors.textPrimary },
    muted: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 18 },
    link: { fontSize: 15.5, fontWeight: '700', color: colors.accent },
    verdictRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, flexWrap: 'wrap' },
  });
}
