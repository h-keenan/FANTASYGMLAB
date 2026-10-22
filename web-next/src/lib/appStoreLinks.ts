/**
 * Public store listings for the native FantasyDesk apps.
 *
 * A null URL means that app isn't publicly live, and the landing page's
 * AppStoreModules renders a "Coming soon" state for it with no link at all
 * (never a dead or placeholder link). Going live is a one-line change: set
 * the real listing URL here and that slot becomes a real link.
 *
 * Status (2026-10-21): the Android app is live on Google Play. The iOS app
 * is still in App Store review with no public listing (the iTunes lookup
 * for com.fantasygmlab.app returns zero results), so appStoreUrl stays null.
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
  playStoreUrl: "https://play.google.com/store/apps/details?id=com.fantasygmlab.app",
  appStoreBadgeSrc: null,
  playStoreBadgeSrc: null,
};
