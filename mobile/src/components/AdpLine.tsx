import React from 'react';
import { Alert, Linking } from 'react-native';

import AppText from './AppText';
import { ADP_CREDIT, ADP_CREDIT_URL, EST_SF_NOTE, adpParts, type AdpFields } from '../lib/adpPresentation';

/**
 * "1QB ADP 4.2 · Est. SF 2.0 ?" (mirrors web-next AdpInline). The superflex number is a model,
 * so it is always labelled "Est. SF" and the "?" explains it; real ADP is always "1QB ADP".
 */
export default function AdpLine({
  adp,
  note = EST_SF_NOTE,
  style,
}: {
  adp: AdpFields;
  note?: string;
  style?: React.ComponentProps<typeof AppText>['style'];
}) {
  const { real, est } = adpParts(adp);
  if (!real) return null;
  return (
    <AppText style={style}>
      {real}
      {est ? (
        <>
          {' · '}
          {est}{' '}
          <AppText
            accessibilityRole="button"
            accessibilityLabel="What is Est. SF?"
            onPress={() => Alert.alert('Est. SF ADP', note)}
            style={style}
          >
            (?)
          </AppText>
        </>
      ) : null}
    </AppText>
  );
}

export function AdpCredit({ asOf, style }: { asOf?: string | null; style?: React.ComponentProps<typeof AppText>['style'] }) {
  return (
    <AppText
      accessibilityRole="link"
      onPress={() => void Linking.openURL(ADP_CREDIT_URL)}
      style={style}
    >
      {ADP_CREDIT}
      {asOf ? ` (as of ${asOf})` : ''}
    </AppText>
  );
}
