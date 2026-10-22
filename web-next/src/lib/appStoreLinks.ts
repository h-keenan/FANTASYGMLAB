/**
 * Public store listings for the native FantasyDesk apps.
 *
 * Neither app is publicly live yet, so both URLs are null and the landing
 * page's AppStoreModules renders a "Coming soon" state with no link at all
 * (never a dead or placeholder link). Going live is a one-line change: set
 * the real listing URL here and that slot becomes a real link.
 *
 * `*BadgeSrc` is the hook for the official "Download on the App Store" /
 * "Get it on Google Play" badge artwork. Apple's and Google's badge
 * guidelines only allow those badges for an app that is actually
 * downloadable, so they stay null until the matching URL is set. Once an
 * app is live, drop the unmodified official badge file into web-next/public/
 * and point the matching field at it (e.g. "/badges/app-store.svg"). A badge
 * is ignored while its URL is null.
 */
export interface AppStoreLinks {
  appStoreUrl: string | null;
  playStoreUrl: string | null;
  appStoreBadgeSrc: string | null;
  playStoreBadgeSrc: string | null;
}

export const APP_STORE_LINKS: AppStoreLinks = {
  appStoreUrl: null,
  playStoreUrl: null,
  appStoreBadgeSrc: null,
  playStoreBadgeSrc: null,
};
