/**
 * Shared between the server-rendered landing page (app/page.tsx) and its
 * client auth island (components/LandingAuthIsland.tsx).
 *
 * The landing page's marketing content is server-rendered so crawlers that
 * don't run JS see it. A returning signed-in visitor, though, is about to
 * be auto-redirected to their Dashboard/Portfolio, and they should keep
 * seeing the branded LoadingScreen (as they always have) rather than a
 * flash of marketing copy first. `data-landing-pending` on the landing
 * root element switches the visible content from the marketing view to
 * that LoadingScreen (see the matching rules in globals.css).
 *
 * Two places set it:
 * - LANDING_PENDING_SCRIPT, inline in the server HTML, runs before first
 *   paint on a hard load. It can't know the session for certain without
 *   supabase-js, so it uses the same cheap signals supabase-js itself
 *   reads on startup: a persisted `sb-<project-ref>-auth-token` entry in
 *   localStorage (supabase-js's default browser storage key), or an
 *   OAuth/email-link redirect landing here with the session in the URL
 *   (`#access_token=...` or `?code=...`, picked up by detectSessionInUrl).
 * - LandingAuthIsland, once auth has actually resolved, sets or clears it
 *   from the real session/saved-leagues state. That also covers
 *   client-side navigations to "/", where the inline script never runs.
 */
export const LANDING_ROOT_ID = "fd-landing-root";
export const LANDING_PENDING_ATTR = "data-landing-pending";

export const LANDING_PENDING_SCRIPT = `(function(){try{var r=document.getElementById(${JSON.stringify(
  LANDING_ROOT_ID,
)});if(!r)return;var p=false;for(var i=0;i<localStorage.length;i++){var k=localStorage.key(i);if(k&&/^sb-.+-auth-token$/.test(k)){p=true;break}}if(!p&&(/access_token=/.test(location.hash)||/[?&]code=/.test(location.search)))p=true;if(p)r.setAttribute(${JSON.stringify(
  LANDING_PENDING_ATTR,
)},"")}catch(e){}})()`;

export function setLandingPending(pending: boolean) {
  const root = document.getElementById(LANDING_ROOT_ID);
  if (!root) return;
  if (pending) root.setAttribute(LANDING_PENDING_ATTR, "");
  else root.removeAttribute(LANDING_PENDING_ATTR);
}
