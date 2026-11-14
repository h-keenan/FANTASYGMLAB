import React from "react";
import { createRoot } from "react-dom/client";

import { PlayerQuickView } from "@/components/PlayerQuickView";

import "./globals.css";

// Geometry harness for pqv_peek_geometry.mjs: the REAL PlayerQuickView (no remote fetches) + the real globals.css rules.
const q = new URLSearchParams(location.search);
const identity = {
  player_id: "4017", name: q.get("name") || "Davante Adams", position: "WR", team: "LV", age: 33, tier: "Starter", score: 62.4, overall_rating: 64,
  overall_rank: 41, position_rank: 18, opportunity_label: "Clear WR1 role", sourceLabel: "My Team",
  tags: [{ key: "a", label: "Contributor", tone: "accent" as const }, { key: "b", label: "Aging", tone: "warning" as const }],
  injury_status: "Questionable",
};
createRoot(document.getElementById("root")!).render(<PlayerQuickView identity={identity} onClose={() => {}} remote={false} />);
