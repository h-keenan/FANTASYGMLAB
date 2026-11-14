/**
 * Soft halo for the prestige-ring glow. A single solid-colour disc a few px larger than the avatar reads as a second,
 * hard-edged ring ("you can see the border around the glow"). React Native has no blurred box-shadow that works on
 * both platforms, so the halo is a stack of concentric discs: each one is faint on its own and they add up to an
 * alpha that falls off smoothly from the ring outward, with no single visible edge. Web uses a blurred box-shadow
 * (globals.css .prestige-glow), which has no edge either.
 */
export interface GlowLayer {
  /** How far this disc extends past the avatar edge, in px. */
  spread: number;
  /** Opacity of this disc alone (they stack). */
  opacity: number;
}

export const GLOW_LAYER_COUNT = 8;

export function glowLayers(spread: number, peakOpacity: number, count = GLOW_LAYER_COUNT): GlowLayer[] {
  const layers: GlowLayer[] = [];
  for (let i = 0; i < count; i += 1) {
    // Outer discs are wider, and only the first few overlap near the ring, so alpha is highest at the ring.
    layers.push({ spread: spread * ((i + 1) / count), opacity: (peakOpacity / count) * 1.4 });
  }
  return layers;
}
