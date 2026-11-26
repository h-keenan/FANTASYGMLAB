import type { MetadataRoute } from "next";

import { BRAND_NAME } from "@/lib/brand";

/** Web app manifest (served at /manifest.webmanifest) so FantasyDesk installs to a phone Home Screen / launcher. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: BRAND_NAME,
    short_name: BRAND_NAME,
    description: "Roster-aware dynasty trades, waivers and a weekly game plan built from your real league.",
    start_url: "/?utm_source=pwa&utm_medium=home_screen",
    scope: "/",
    display: "standalone",
    background_color: "#000000",
    theme_color: "#000000",
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
