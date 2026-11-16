"use client";

import { RetiredLeagueRoute } from "@/components/RetiredLeagueRoute";

// Retired route (2026-11-16 nav consolidation): forwards to its new home, see lib/retiredRoutes.ts.
export default function RetiredLeagueRecapsPage() {
  return <RetiredLeagueRoute segment="league-recaps" label="News" layout="detail" />;
}
