import { APP_STORE_LINKS, type AppStoreLinks } from "@/lib/appStoreLinks";

/**
 * App Store + Google Play slots for the logged-out landing page.
 *
 * Neither native app is publicly live yet, so by default (see
 * lib/appStoreLinks.ts) both slots render a plain "Coming soon" module:
 * store name, a generic device glyph, no link, no date, no download claim.
 * The official "Download on the App Store" / "Get it on Google Play" badges
 * are deliberately NOT used for that state: Apple's and Google's badge
 * guidelines reserve them for apps that are actually downloadable, and the
 * Apple logo / Google Play logo themselves aren't ours to draw in a custom
 * module either, hence the neutral phone glyph instead of either mark.
 *
 * Once a store URL is set, that slot becomes a real outbound link. If the
 * matching official badge artwork has also been dropped into public/ and
 * pointed at from lib/appStoreLinks.ts, the badge image is rendered as-is
 * (unmodified, per both guidelines); otherwise the same module renders as a
 * link with the store's own call-to-action text.
 *
 * Reuses the landing page's existing .onboarding-glass surface (the same
 * forced-dark rounded glass the sign-in card and onboarding carousel use)
 * and design tokens; no new per-page colors. No client-side state, so this
 * renders on the server as plain HTML.
 */
export function AppStoreModules({ links = APP_STORE_LINKS }: { links?: AppStoreLinks }) {
  return (
    <section aria-labelledby="app-store-modules-heading" className="w-full max-w-sm flex flex-col gap-3">
      <h2
        id="app-store-modules-heading"
        className="text-xs font-bold uppercase text-center"
        style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
      >
        Mobile apps
      </h2>
      <ul className="grid grid-cols-2 gap-3">
        <li>
          <StoreSlot
            storeName="App Store"
            platform="iPhone"
            liveCallToAction="Download on the App Store"
            url={links.appStoreUrl}
            badgeSrc={links.appStoreBadgeSrc}
          />
        </li>
        <li>
          <StoreSlot
            storeName="Google Play"
            platform="Android"
            liveCallToAction="Get it on Google Play"
            url={links.playStoreUrl}
            badgeSrc={links.playStoreBadgeSrc}
          />
        </li>
      </ul>
    </section>
  );
}

function StoreSlot({
  storeName,
  platform,
  liveCallToAction,
  url,
  badgeSrc,
}: {
  storeName: string;
  platform: string;
  liveCallToAction: string;
  url: string | null;
  badgeSrc: string | null;
}) {
  if (url && badgeSrc) {
    return (
      <a href={url} target="_blank" rel="noopener noreferrer" className="flex items-center justify-center h-full">
        {/* Official badge artwork must render unmodified, so a plain <img>
            rather than next/image's optimizer (which can re-encode it). */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={badgeSrc} alt={liveCallToAction} className="h-11 w-auto" />
      </a>
    );
  }

  const body = (
    <>
      <span aria-hidden="true" style={{ color: url ? "var(--color-accent)" : "var(--color-text-muted)" }}>
        <DeviceGlyph />
      </span>
      <span className="flex flex-col min-w-0">
        <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {storeName}
        </span>
        <span className="text-xs" style={{ color: url ? "var(--color-accent)" : "var(--color-text-muted)" }}>
          {url ? "Download" : "Coming soon"}
        </span>
      </span>
    </>
  );

  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={liveCallToAction}
        className="onboarding-glass flex items-center gap-3 px-4 py-3 h-full"
      >
        {body}
      </a>
    );
  }

  return (
    <div
      className="onboarding-glass flex items-center gap-3 px-4 py-3 h-full"
      aria-label={`${storeName} app for ${platform}: coming soon`}
      role="group"
    >
      {body}
    </div>
  );
}

function DeviceGlyph({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <rect x="6.5" y="2.5" width="11" height="19" rx="2.5" />
      <path d="M10.5 18.5h3" />
    </svg>
  );
}
