/**
 * Share-card QR visitors (utm_campaign=share_card, see modules/share_card_qr.py)
 * land on the normal landing page; only the hero line changes to acknowledge
 * the shared analysis. The page stays static (no per-request searchParams), so
 * the switch is a CSS flag set by an inline script before first paint, the
 * same pattern as lib/landingPending.ts. No data is carried by the URL.
 */
import { LANDING_ROOT_ID } from "@/lib/landingPending";

export const LANDING_SHARE_ATTR = "data-share-landing";
export const SHARE_CARD_CAMPAIGN = "share_card";

export function isShareCardVisit(search: string): boolean {
  try {
    return new URLSearchParams(search).get("utm_campaign") === SHARE_CARD_CAMPAIGN;
  } catch {
    return false;
  }
}

export const LANDING_SHARE_SCRIPT = `(function(){try{var r=document.getElementById(${JSON.stringify(
  LANDING_ROOT_ID,
)});if(r&&new URLSearchParams(location.search).get("utm_campaign")===${JSON.stringify(
  SHARE_CARD_CAMPAIGN,
)})r.setAttribute(${JSON.stringify(LANDING_SHARE_ATTR)},"")}catch(e){}})()`;
