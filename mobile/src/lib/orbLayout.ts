import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { spacing } from '../theme';

// Single source of truth for GmOrb's footprint, shared with every scrollable
// screen so their bottom padding can actually clear it. Duplicated here
// instead of imported from GmOrb.tsx to avoid a screen-to-component import
// cycle; GmOrb.tsx imports these back so the two can never drift apart.
export const ORB_SIZE = 64;

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
 * was tested on and wrong everywhere else, the same mistake an earlier
 * version of this file made with an inset-clamping ceiling (see PR #513's
 * history, and its removal once coridian_ confirmed the bug it was written
 * for was never actually an inset problem). Uses insets.bottom directly, no
 * clamp — GmOrb positions itself with the same unclamped value, and the two
 * have to agree or a screen can reserve less room than the orb actually
 * occupies.
 */
export function useOrbClearance(extraBreathingRoom: number = spacing.md): number {
  const insets = useSafeAreaInsets();
  return ORB_SCRIM_BASE_HEIGHT + insets.bottom + extraBreathingRoom;
}
