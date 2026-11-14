import React, { useState } from "react";
import { createRoot } from "react-dom/client";

import { BottomTabBar } from "@/components/ui/BottomTabBar";
import { PillMorph } from "@/components/ui/PillMorph";
import { familyPillContext } from "@/lib/pageFamilyPill";
import { shellTabs } from "@/lib/shellNav";

import "./tokens.css";

// Geometry harness for scripts/sim_layout_playwright/pill_geometry.mjs: the REAL BottomTabBar / PillMorph + ui.css,
// over a long page, with route (link) tabs like the live Team page. ?family=team|trades|league, ?primary=1, ?ctx=0, ?sim=1.
const q = new URLSearchParams(location.search);
const family = (q.get("family") || "team") as "team" | "trades" | "league";
const activeKey = { team: "roster", trades: "trade_hub", league: "rankings" }[family];
const tabs = shellTabs({ leagueId: "1", leagueName: "L" });

function App() {
  const ctx = q.get("ctx") === "0" ? null : familyPillContext(family, activeKey, "1", "L", q.get("primary") === "1" ? { primary: { key: "p", label: "Go", glyph: "recommended", onPress: () => {} } } : {});
  return (
    <div className="min-h-dvh" style={{ display: "flex", flexDirection: "column", flex: "auto" }}>
      <div style={{ padding: 16, flex: "auto" }}>
        {Array.from({ length: 40 }, (_, i) => (
          <div key={i} style={{ padding: 14, marginBottom: 8, border: "1px solid var(--color-border)", borderRadius: 14 }}>Row {i}</div>
        ))}
      </div>
      <div className="bottom-stack md:hidden" data-bare data-testid="stack">
        {q.get("sim") === "1" ? (
          <div className="action-pill" data-testid="sim-pill">
            <PillMorph context={ctx}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, padding: 4 }}>
                <button className="pill-icon-btn">S</button>
                <button className="pill-icon-btn">O</button>
                <button style={{ flex: 1, minHeight: 44, borderRadius: 999 }}>Advance</button>
              </div>
            </PillMorph>
          </div>
        ) : (
          <BottomTabBar ariaLabel="League sections" tabs={tabs} active="team" context={ctx} />
        )}
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
