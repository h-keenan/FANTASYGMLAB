import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { spacing } from '../theme';

// Single source of truth for GmOrb's footprint, shared with every scrollable
// screen so their bottom padding can actually clear it. Duplicated here
// instead of imported from GmOrb.tsx to avoid a screen-to-component import
// cycle; GmOrb.tsx imports these back so the two can never drift apart.
export const ORB_SIZE = 48;

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
 * a fixed constant.
 *
 * No ceiling on insets.bottom here (there used to be one — see GmOrb.tsx's
 * own history comment for why it was removed): a device with a legitimately
 * larger inset than some hardcoded cap deserves that much real clearance,
 * not a quietly truncated one.
 */
// Widened from spacing.md after coridian_ still saw the orb's scrim
// overlapping the last card on Trade Hub and Player Detail on a real device
// — the prior margin (12pt) left almost no buffer above the scrim's opaque
// zone. Doubling it is a safe, unconditional improvement regardless of
// whatever device-specific rounding ate the old margin.
export function useOrbClearance(extraBreathingRoom: number = spacing.xl): number {
  const insets = useSafeAreaInsets();
  const safeBottom = Math.max(insets.bottom, 0);
  return ORB_SCRIM_BASE_HEIGHT + safeBottom + extraBreathingRoom;
}
