import type { ConnectPlatformKey } from "@/lib/connectFlow";

/** Brand-color tokens (globals.css --color-platform-*). Monograms only: no platform logo files. */
const PLATFORM_BADGE: Record<ConnectPlatformKey, { letter: string; color: string }> = {
  sleeper: { letter: "S", color: "var(--color-platform-sleeper)" },
  yahoo: { letter: "Y", color: "var(--color-platform-yahoo)" },
  espn: { letter: "E", color: "var(--color-platform-espn)" },
  fleaflicker: { letter: "F", color: "var(--color-platform-fleaflicker)" },
  mfl: { letter: "M", color: "var(--color-platform-mfl)" },
};

/**
 * A league platform's monogram badge: a rounded square in the platform's brand color with its initial. Shared by the
 * connect tiles and the stepper headers. Mobile twin: mobile/src/components/PlatformBadge.tsx.
 */
export function PlatformBadge({ platform, size = 40 }: { platform: ConnectPlatformKey; size?: number }) {
  const { letter, color } = PLATFORM_BADGE[platform];
  return (
    <span
      aria-hidden="true"
      data-testid={`platform-badge-${platform}`}
      className="inline-flex shrink-0 items-center justify-center font-extrabold"
      style={{
        width: size,
        height: size,
        borderRadius: Math.round(size * 0.3),
        background: color,
        color: "var(--color-platform-on)",
        fontSize: Math.round(size * 0.46),
        lineHeight: 1,
      }}
    >
      {letter}
    </span>
  );
}
