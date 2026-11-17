import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AppText from './AppText';
import Button from './Button';
import CompactModule from './CompactModule';
import { api, type TrackRecordResponse } from '../lib/api';
import { planOf, type Plan } from '../lib/plan';
import {
  basicSummary,
  calibrationNote,
  compareLine,
  plural,
  reliabilityLabel,
  type TrackLevel,
} from '../lib/trackRecordView';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

/**
 * "Your track record": how our advice did for you, and how your own calls did. Compact, tap to expand.
 * Basic outcome history is free; advice-vs-your-own-calls and confidence calibration are Pro (`planOf`, and the
 * server withholds them too). Every number carries its sample size; below the minimum it says "too early".
 * Web twin: web-next/src/components/TrackRecordModule.tsx; wording: lib/trackRecordView.ts.
 */
export function TrackRecordView({ record, plan, onUpgrade }: { record: TrackRecordResponse; plan: Plan; onUpgrade?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { basic, advanced } = record;
  const parts = basicSummary(basic).map((text, index) => ({
    key: `b${index}`,
    text,
    strong: index === 0,
    tone:
      index > 0 && text.endsWith('net')
        ? basic.net_points_total > 0
          ? ('success' as const)
          : undefined // a net loss is muted, never red
        : undefined,
  }));
  const showLock = !advanced && plan === 'free';
  const levels: TrackLevel[] = ['high', 'medium', 'low'];

  return (
    <CompactModule id="track-record" title="Your track record" parts={parts} testID="track-record">
      <AppText style={styles.secondary}>
        {basic.trades_graded > 0
          ? `${plural(basic.trades_graded, 'confirmed trade')} graded on real points. ${reliabilityLabel(basic.reliability)}: a few weeks of games is a small sample, so luck still plays a part.`
          : 'Confirm a trade and, a few weeks later, its real points show up here.'}
      </AppText>

      {advanced ? (
        <View style={styles.block} testID="track-record-advanced">
          <AppText style={styles.primary}>{compareLine(advanced)}</AppText>
          {levels.map((level) => {
            const note = calibrationNote(level, advanced);
            return note ? (
              <AppText key={level} style={styles.secondary}>
                {note}
              </AppText>
            ) : null;
          })}
          <AppText style={styles.muted}>{advanced.caveat}</AppText>
        </View>
      ) : null}

      {showLock ? (
        <View style={styles.lock} testID="track-record-lock">
          <AppText style={styles.secondary}>Pro: advice vs your own calls and confidence calibration</AppText>
          {onUpgrade ? <Button label="See Pro" variant="premium" size="sm" onPress={onUpgrade} /> : null}
        </View>
      ) : null}
    </CompactModule>
  );
}

export default function TrackRecordModule() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [state, setState] = useState<{ record: TrackRecordResponse; plan: Plan } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getTrackRecord(), api.getMe().catch(() => null)])
      .then(([record, me]) => {
        if (!cancelled) setState({ record, plan: planOf(me?.user) });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  // Fail soft: no record (offline, table unreachable) simply hides the module.
  return state ? <TrackRecordView record={state.record} plan={state.plan} onUpgrade={() => navigation.navigate('Paywall')} /> : null;
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    block: { gap: spacing.xs },
    lock: { gap: spacing.sm, alignItems: 'flex-start' },
    primary: { fontSize: 14.5, color: colors.textPrimary },
    secondary: { fontSize: 14, color: colors.textSecondary },
    muted: { fontSize: 12.5, color: colors.textTertiary },
  });
}
