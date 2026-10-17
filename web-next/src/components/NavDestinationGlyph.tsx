export type NavGlyphName =
  | "dashboard"
  | "home"
  | "portfolio"
  | "news"
  | "tradeHistory"
  | "collegeScouting"
  | "myTeam"
  | "matchup"
  | "tradeHub"
  | "waivers"
  | "leagueRankings"
  | "alerts"
  | "gmPlan"
  | "gmTargets"
  | "leagueRecaps"
  | "draftCenter"
  | "tradeAnalyzer"
  | "tradeFinder"
  | "players"
  | "liveDraft"
  | "teamSituation";

/**
 * One icon per nav destination, shared by Dashboard's Explore grid
 * (DashboardContent.tsx) and GmOrb's destination sheet — every row in both
 * was plain text with no icon at all (coridian_, 2026-10-16: "the dashboard
 * needs more glyph icons... so people can quickly scan the page"; brand
 * continuity audit, 2026-10-17: GmOrb has no icons either, unlike mobile's
 * version of the same sheet).
 *
 * Paths are the exact outline-style Ionicons glyphs the mobile app already
 * uses for these same destinations (mobile/src/components/GmOrb.tsx,
 * mobile/src/screens/MoreScreen.tsx) — copied in as static inline SVG
 * (`ionicons` installed only to read the source paths, not as a runtime
 * dependency) rather than redrawn, so a destination reads as the same icon
 * on both platforms. Trade Finder/Trade Analyzer/Live Draft have no mobile
 * equivalent (mobile collapses Trade Hub/Finder/Analyzer into one "Trades"
 * destination, and never surfaces Live Draft as quick-nav) — those three
 * use their own Ionicons pick instead of inventing new iconography.
 */
export function NavDestinationGlyph({ name, size = 18 }: { name: NavGlyphName; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 512 512",
    "aria-hidden": true,
  };
  const stroke = {
    fill: "none" as const,
    stroke: "currentColor",
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    strokeWidth: 32,
  };

  switch (name) {
    case "dashboard":
      return (
        <svg {...common}>
          <path d="M315.27 33 96 304h128l-31.51 173.23a2.36 2.36 0 0 0 2.33 2.77h0a2.36 2.36 0 0 0 1.89-.95L416 208H288l31.66-173.25a2.45 2.45 0 0 0-2.44-2.75h0a2.42 2.42 0 0 0-1.95 1" {...stroke} />
        </svg>
      );
    case "home":
      return (
        <svg {...common}>
          <path d="M80 212v236a16 16 0 0 0 16 16h96V328a24 24 0 0 1 24-24h80a24 24 0 0 1 24 24v136h96a16 16 0 0 0 16-16V212" {...stroke} />
          <path d="M480 256 266.89 52c-5-5.28-16.69-5.34-21.78 0L32 256M400 179V64h-48v69" {...stroke} />
        </svg>
      );
    case "portfolio":
      return (
        <svg {...common}>
          <path d="m434.8 137.65-149.36-68.1c-16.19-7.4-42.69-7.4-58.88 0L77.3 137.65c-17.6 8-17.6 21.09 0 29.09l148 67.5c16.89 7.7 44.69 7.7 61.58 0l148-67.5c17.52-8 17.52-21.1-.08-29.09M160 308.52l-82.7 37.11c-17.6 8-17.6 21.1 0 29.1l148 67.5c16.89 7.69 44.69 7.69 61.58 0l148-67.5c17.6-8 17.6-21.1 0-29.1l-79.94-38.47" {...stroke} />
          <path d="m160 204.48-82.8 37.16c-17.6 8-17.6 21.1 0 29.1l148 67.49c16.89 7.7 44.69 7.7 61.58 0l148-67.49c17.7-8 17.7-21.1.1-29.1L352 204.48" {...stroke} />
        </svg>
      );
    case "news":
      return (
        <svg {...common}>
          <path d="M256 48C141.13 48 48 141.13 48 256s93.13 208 208 208 208-93.13 208-208S370.87 48 256 48Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="M256 48c-58.07 0-112.67 93.13-112.67 208S197.93 464 256 464s112.67-93.13 112.67-208S314.07 48 256 48Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="M117.33 117.33c38.24 27.15 86.38 43.34 138.67 43.34s100.43-16.19 138.67-43.34M394.67 394.67c-38.24-27.15-86.38-43.34-138.67-43.34s-100.43 16.19-138.67 43.34" {...stroke} />
          <path d="M256 48v416M464 256H48" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
        </svg>
      );
    case "tradeHistory":
      return (
        <svg {...common}>
          <path d="M256 64C150 64 64 150 64 256s86 192 192 192 192-86 192-192S362 64 256 64Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="M256 128v144h96" {...stroke} />
        </svg>
      );
    case "collegeScouting":
      return (
        <svg {...common}>
          <path d="M32 192 256 64l224 128-224 128z" {...stroke} />
          <path d="M112 240v128l144 80 144-80V240M480 368V192M256 320v128" {...stroke} />
        </svg>
      );
    case "myTeam":
      return (
        <svg {...common}>
          <path d="M314.56 48s-22.78 8-58.56 8-58.56-8-58.56-8a32 32 0 0 0-10.57 1.8L32 104l16.63 88 48.88 5.52a24 24 0 0 1 21.29 24.58L112 464h288l-6.8-241.9a24 24 0 0 1 21.29-24.58l48.88-5.52L480 104 325.13 49.8a32 32 0 0 0-10.57-1.8" {...stroke} />
          <path d="M333.31 52.66a80 80 0 0 1-154.62 0" {...stroke} />
        </svg>
      );
    case "matchup":
      return (
        <svg {...common}>
          <ellipse cx="256" cy="256" rx="267.57" ry="173.44" transform="rotate(-45 256 256.002)" {...stroke} />
          <path d="M334.04 177.96 177.96 334.04M278.3 278.3l-44.6-44.6M322.89 233.7l-44.59-44.59M456.68 211.4 300.6 55.32M211.4 456.68 55.32 300.6M233.7 322.89l-44.59-44.59" {...stroke} />
        </svg>
      );
    case "tradeHub":
      return (
        <svg {...common}>
          <path d="m400 304 48 48-48 48M400 112l48 48-48 48M64 352h85.19a80 80 0 0 0 66.56-35.62L256 256" {...stroke} />
          <path d="M64 160h85.19a80 80 0 0 1 66.56 35.62l80.5 120.76A80 80 0 0 0 362.81 352H416M416 160h-53.19a80 80 0 0 0-66.56 35.62L288 208" {...stroke} />
        </svg>
      );
    case "waivers":
      return (
        <svg {...common}>
          <path d="m304 48 112 112-112 112M398.87 160H96M208 464 96 352l112-112M114 352h302" {...stroke} />
        </svg>
      );
    case "leagueRankings":
      return (
        <svg {...common}>
          <path d="M256 464c-114.69 0-208-93.31-208-208S141.31 48 256 48s208 93.31 208 208-93.31 208-208 208m0-384c-97 0-176 79-176 176s79 176 176 176 176-78.95 176-176S353.05 80 256 80" fill="currentColor" />
          <path d="M323.67 292c-17.4 0-34.21-7.72-47.34-21.73a83.76 83.76 0 0 1-22-51.32c-1.47-20.7 4.88-39.75 17.88-53.62S303.38 144 323.67 144c20.14 0 38.37 7.62 51.33 21.46s19.47 33 18 53.51a84 84 0 0 1-22 51.3C357.86 284.28 341.06 292 323.67 292M163.82 295.36c-29.76 0-55.93-27.51-58.33-61.33-1.23-17.32 4.15-33.33 15.17-45.08s26.22-18 43.15-18 32.12 6.44 43.07 18.14 16.5 27.82 15.25 45c-2.44 33.77-28.6 61.27-58.31 61.27M420.37 355.28c-1.59-4.7-5.46-9.71-13.22-14.46-23.46-14.33-52.32-21.91-83.48-21.91-30.57 0-60.23 7.9-83.53 22.25-26.25 16.17-43.89 39.75-51 68.18-1.68 6.69-4.13 19.14-1.51 26.11a192.18 192.18 0 0 0 232.75-80.17ZM163.63 401.37c7.07-28.21 22.12-51.73 45.47-70.75a8 8 0 0 0-2.59-13.77c-12-3.83-25.7-5.88-42.69-5.88-23.82 0-49.11 6.45-68.14 18.17-5.4 3.33-10.7 4.61-14.78 5.75a192.84 192.84 0 0 0 77.78 86.64l1.79-.14a103 103 0 0 1 3.16-20.02" fill="currentColor" />
        </svg>
      );
    case "alerts":
      return (
        <svg {...common}>
          <path d="M427.68 351.43C402 320 383.87 304 383.87 217.35 383.87 138 343.35 109.73 310 96c-4.43-1.82-8.6-6-9.95-10.55C294.2 65.54 277.8 48 256 48s-38.21 17.55-44 37.47c-1.35 4.6-5.52 8.71-9.95 10.53-33.39 13.75-73.87 41.92-73.87 121.35C128.13 304 110 320 84.32 351.43 73.68 364.45 83 384 101.61 384h308.88c18.51 0 27.77-19.61 17.19-32.57M320 384v16a64 64 0 0 1-128 0v-16" {...stroke} />
        </svg>
      );
    case "gmPlan":
      return (
        <svg {...common}>
          <path d="M313.27 124.64 198.73 51.36a32 32 0 0 0-29.28.35L56.51 127.49A16 16 0 0 0 48 141.63v295.8a16 16 0 0 0 23.49 14.14l97.82-63.79a32 32 0 0 1 29.5-.24l111.86 73a32 32 0 0 0 29.27-.11l115.43-75.94a16 16 0 0 0 8.63-14.2V74.57a16 16 0 0 0-23.49-14.14l-98 63.86a32 32 0 0 1-29.24.35M328 128v336M184 48v336" {...stroke} />
        </svg>
      );
    case "gmTargets":
      return (
        <svg {...common}>
          <path d="M352 48H160a48 48 0 0 0-48 48v368l144-128 144 128V96a48 48 0 0 0-48-48" {...stroke} />
        </svg>
      );
    case "leagueRecaps":
      return (
        <svg {...common}>
          <path d="M368 415.86V72a24.07 24.07 0 0 0-24-24H72a24.07 24.07 0 0 0-24 24v352a40.12 40.12 0 0 0 40 40h328" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth={32} />
          <path d="M416 464a48 48 0 0 1-48-48V128h72a24 24 0 0 1 24 24v264a48 48 0 0 1-48 48Z" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth={32} />
          <path d="M240 128h64M240 192h64M112 256h192M112 320h192M112 384h192" {...stroke} />
          <path d="M176 208h-64a16 16 0 0 1-16-16v-64a16 16 0 0 1 16-16h64a16 16 0 0 1 16 16v64a16 16 0 0 1-16 16" fill="currentColor" />
        </svg>
      );
    case "draftCenter":
      return (
        <svg {...common}>
          <rect width="384" height="256" x="64" y="176" rx="28.87" ry="28.87" fill="none" stroke="currentColor" strokeLinejoin="round" strokeWidth={32} />
          <path d="M144 80h224M112 128h288" stroke="currentColor" strokeLinecap="round" strokeMiterlimit={10} strokeWidth={32} />
        </svg>
      );
    case "tradeAnalyzer":
      return (
        <svg {...common}>
          <rect width="288" height="416" x="112" y="48" rx="32" ry="32" {...stroke} />
          <path d="M160.01 112H352v64H160.01z" {...stroke} />
          <circle cx="168" cy="248" r="24" fill="currentColor" />
          <circle cx="256" cy="248" r="24" fill="currentColor" />
          <circle cx="344" cy="248" r="24" fill="currentColor" />
          <circle cx="168" cy="328" r="24" fill="currentColor" />
          <circle cx="256" cy="328" r="24" fill="currentColor" />
          <circle cx="168" cy="408" r="24" fill="currentColor" />
          <circle cx="256" cy="408" r="24" fill="currentColor" />
          <rect width="48" height="128" x="320" y="304" rx="24" ry="24" fill="currentColor" />
        </svg>
      );
    case "tradeFinder":
      return (
        <svg {...common}>
          <path d="M221.09 64a157.09 157.09 0 1 0 157.09 157.09A157.1 157.1 0 0 0 221.09 64Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="M338.29 338.29 448 448" fill="none" stroke="currentColor" strokeLinecap="round" strokeMiterlimit={10} strokeWidth={32} />
        </svg>
      );
    case "players":
      return (
        <svg {...common}>
          <path d="M402 168c-2.93 40.67-33.1 72-66 72s-63.12-31.32-66-72c-3-42.31 26.37-72 66-72s69 30.46 66 72" {...stroke} />
          <path d="M336 304c-65.17 0-127.84 32.37-143.54 95.41-2.08 8.34 3.15 16.59 11.72 16.59h263.65c8.57 0 13.77-8.25 11.72-16.59C463.85 335.36 401.18 304 336 304Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="M200 185.94c-2.34 32.48-26.72 58.06-53 58.06s-50.7-25.57-53-58.06C91.61 152.15 115.34 128 147 128s55.39 24.77 53 57.94" {...stroke} />
          <path d="M206 306c-18.05-8.27-37.93-11.45-59-11.45-52 0-102.1 25.85-114.65 76.2-1.65 6.66 2.53 13.25 9.37 13.25H154" fill="none" stroke="currentColor" strokeLinecap="round" strokeMiterlimit={10} strokeWidth={32} />
        </svg>
      );
    case "liveDraft":
      return (
        <svg {...common}>
          <circle cx="256" cy="256.02" r="32" fill="currentColor" />
          <path d="M184.25 192.25a96 96 0 0 0 0 127.52M327.77 319.77a96 96 0 0 0 0-127.52M133.28 141.28a168 168 0 0 0 0 229.44M378.72 370.72a168 168 0 0 0 0-229.44" {...stroke} />
          <path d="M435 416a240.34 240.34 0 0 0 0-320M77 96a240.34 240.34 0 0 0 0 320" {...stroke} />
        </svg>
      );
    case "teamSituation":
      return (
        <svg {...common}>
          <path d="M448 256c0-106-86-192-192-192S64 150 64 256s86 192 192 192 192-86 192-192Z" fill="none" stroke="currentColor" strokeMiterlimit={10} strokeWidth={32} />
          <path d="m350.67 150.93-117.2 46.88a64 64 0 0 0-35.66 35.66l-46.88 117.2a8 8 0 0 0 10.4 10.4l117.2-46.88a64 64 0 0 0 35.66-35.66l46.88-117.2a8 8 0 0 0-10.4-10.4M256 280a24 24 0 1 1 24-24 24 24 0 0 1-24 24" fill="currentColor" />
        </svg>
      );
    default:
      return null;
  }
}
