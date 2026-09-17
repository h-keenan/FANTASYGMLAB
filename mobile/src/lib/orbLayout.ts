import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { spacing } from '../theme';

// Single source of truth for GmOrb's footprint, shared with every scrollable
// screen so their bottom padding can actually clear it. Duplicated here
// instead of imported from GmOrb.tsx to avoid a screen-to-component import
// cycle; GmOrb.tsx imports these back so the two can never drift apart.
export const ORB_SIZE = 64;
export const ORB_INSET_CEILING = 100;

// GmOrb also renders a LinearGradient scrim behind the orb, absolutely
// positioned at the screen bottom with height `ORB_SCRIM_BASE_HEIGHT +
// insets.bottom`, fading to near-opaque at the very bottom edge. The scrim is
// taller than the orb itself, so it — not the orb's own footprint — is what a
// scrollable screen actually needs to clear: content that stops right at the
// orb's edge still lands inside the darkest part of the gradient and reads as
// nearly invisible.
export const ORB_SCRIM_BASE_HEIGHT = 112;

/**
 * Minimum bottom padding a scrollable screen needs so its last item neither
 * renders behind GmOrb nor lands inside its scrim gradient. Depends on
 * insets.bottom, which varies by device, so this has to be a hook rather than
 * a fixed constant — a hardcoded number would be right on whichever phone it
 * was tested on and wrong everywhere else, the same mistake the orb's own
 * inset clamp made once already (see PR #513's history).
 */
export function useOrbClearance(extraBreathingRoom: number = spacing.md): number {
  const rawInsets = useSafeAreaInsets();
  const safeBottom = Math.min(Math.max(rawInsets.bottom, 0), ORB_INSET_CEILING);
  return ORB_SCRIM_BASE_HEIGHT + safeBottom + extraBreathingRoom;
}
