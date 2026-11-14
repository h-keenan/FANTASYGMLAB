import React from 'react';
import { View } from 'react-native';

import PickAvatar from './PickAvatar';

/** Draft-pick avatar ("R1" over "#3") in the round player-photo slot. Kept under its old name for existing callers; see PickAvatar. */
export default function PickPlate({ round, pickNo, size = 38 }: { round?: number | null; pickNo?: number | null; size?: number }) {
  return (
    <View style={{ marginRight: 8 }}>
      <PickAvatar round={round} pickNo={pickNo} size={size} />
    </View>
  );
}
