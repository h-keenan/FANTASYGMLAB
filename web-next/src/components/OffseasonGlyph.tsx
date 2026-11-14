import type { OffseasonIcon } from "@/lib/simOffseasonSummary";

/**
 * Section-header and stepper glyphs for the Fantasy Sim offseason (the "consistent section headers with an icon" rule of the
 * Visual identity spec). 16px line icons on `currentColor`, same drawing style as SimDraftGlyph. App twin: Ionicons through
 * OFFSEASON_IONICON in mobile/src/components/OffseasonGlyph.tsx.
 */
export function OffseasonGlyph({ name, size = 16 }: { name: OffseasonIcon; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 16 16", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true, focusable: false };
  switch (name) {
    case "review":
      return (
        <svg {...common}>
          <rect x="3" y="2.5" width="10" height="11" rx="1.6" />
          <path d="M5.5 6h5M5.5 8.5h5M5.5 11h3" />
        </svg>
      );
    case "draft":
      return (
        <svg {...common}>
          <circle cx="8" cy="8" r="5.5" />
          <path d="M8 4.8V8l2.2 1.4" />
        </svg>
      );
    case "roster":
      return (
        <svg {...common}>
          <circle cx="6" cy="5.5" r="2.2" />
          <path d="M2.2 13c.4-2.2 1.9-3.4 3.8-3.4s3.4 1.2 3.8 3.4M11 4.2a2 2 0 010 3.8M12.2 9.8c1 .5 1.6 1.5 1.8 3" />
        </svg>
      );
    case "season":
      return (
        <svg {...common}>
          <path d="M5 2.5h6v3.2a3 3 0 01-6 0zM5 4H2.8c0 2 .8 3 2.4 3.2M11 4h2.2c0 2-.8 3-2.4 3.2M8 8.7V12M5.5 13.5h5" />
        </svg>
      );
    case "retire":
      return (
        <svg {...common}>
          <path d="M3 13.5V6.5l5-3.5 5 3.5v7M6.5 13.5V9.5h3v4" />
        </svg>
      );
    case "aging":
      return (
        <svg {...common}>
          <path d="M2.5 11.5l3.5-4 2.5 2.5 5-5.5M10 4.5h3.5V8" />
        </svg>
      );
    case "picks":
      return (
        <svg {...common}>
          <path d="M3 3.5h10v7.2L8 13.5l-5-2.8zM3 6.5h10" />
        </svg>
      );
    case "log":
      return (
        <svg {...common}>
          <path d="M3 4.5h10M3 8h10M3 11.5h6" />
        </svg>
      );
    case "reserve":
      return (
        <svg {...common}>
          <path d="M8 2.5v11M2.5 8h11" />
          <rect x="2.5" y="2.5" width="11" height="11" rx="2.4" />
        </svg>
      );
    case "trade":
      return (
        <svg {...common}>
          <path d="M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13" />
        </svg>
      );
    case "team":
      return (
        <svg {...common}>
          <path d="M4 3.5h8l1.5 3L8 13.5 2.5 6.5z" />
        </svg>
      );
  }
}
