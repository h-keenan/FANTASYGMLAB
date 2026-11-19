import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AppText from './AppText';
import Button from './Button';
import CompactModule from './CompactModule';
import { api, type TrackRecordResponse } from '../lib/api';
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
export function TrackRecordView({ record, onUpgrade }: { record: TrackRecordResponse; onUpgrade?: () => void }) {
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
  // The response says whether the advanced block was withheld (`is_pro`), so the lock never depends on a second /me call.
  const showLock = !advanced && !record.is_pro;
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
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [record, setRecord] = useState<TrackRecordResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getTrackRecord()
      .then((body) => {
        if (!cancelled) setRecord(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // The module stays visible when the read fails: a short error line, never a blank where it used to be.
  if (failed) {
    return (
      <CompactModule id="track-record" title="Your track record" parts={[{ key: 'err', text: 'Could not load right now', strong: true }]} testID="track-record-error">
        <AppText style={styles.secondary}>Your track record could not load. Try again in a moment.</AppText>
      </CompactModule>
    );
  }
  return record ? <TrackRecordView record={record} onUpgrade={() => navigation.navigate('Paywall')} /> : null;
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
