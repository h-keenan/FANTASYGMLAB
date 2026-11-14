import React from 'react';
import { Text, type StyleProp, type TextStyle } from 'react-native';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { splitMoney } from '../lib/money';

/**
 * The ONE place dollar amounts get their color (theme `colors.money`). Pass
 * text; every "$81" / "$12–$18" inside it renders in the semantic money green
 * and everything else keeps the surrounding color. `all` paints the whole
 * text (a percent-of-pool FAAB bid is still money). Fantasy points and other
 * numbers never use this. Amounts are built with `formatMoney` from
 * lib/money.ts. Web twin: web-next/src/components/Money.tsx. Banned
 * elsewhere by src/components/moneyShared.test.ts.
 *
 * Two modes. With `style` / `numberOfLines` / `testID` it IS the text line
 * (an AppText). With none of them it is inline: drop it inside a parent
 * <AppText> and it colors just the amounts, inheriting the parent's Inter
 * weight (a nested AppText would reset it to regular).
 */
export default function Money({
  children,
  all = false,
  style,
  numberOfLines,
  testID,
}: {
  children: string;
  all?: boolean;
  style?: StyleProp<TextStyle>;
  numberOfLines?: number;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const text = String(children ?? '');
  const standalone = style != null || numberOfLines != null || testID != null;
  const inner = all ? (
    <Text style={{ color: colors.money }}>{text}</Text>
  ) : (
    splitMoney(text).map((s, i) =>
      s.money ? (
        <Text key={i} style={{ color: colors.money }}>
          {s.text}
        </Text>
      ) : (
        s.text
      ),
    )
  );
  if (!standalone) return <>{inner}</>;
  return (
    <AppText style={style} numberOfLines={numberOfLines} testID={testID}>
      {inner}
    </AppText>
  );
}
