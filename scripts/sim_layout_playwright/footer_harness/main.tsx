import React, { useState } from "react";
import { createRoot } from "react-dom/client";

import { OverlayRuntime } from "@/components/OverlayRuntime";
import { SimGameOrb } from "@/components/SimGameOrb";
import { Button } from "@/components/Button";
import { SimGlyph } from "@/components/SimGlyph";
import { PillMorph } from "@/components/ui/PillMorph";
import { Sheet } from "@/components/ui/Sheet";

import "./tw.css";
import "./tokens.css";

// Harness for scripts/sim_layout_playwright/footer_sheet_audit.mjs: the REAL Fantasy Sim bar markup (SimActionBar's one row: orb | Sim to | Advance, inside .action-pill in a docked .bottom-stack), the real SimGameOrb + Sheet + OverlayRuntime over a long page.
// ?inbox=3 (badge), ?tab=trades|players|..., ?sheet=search (a Sheet with a text field), ?big=1 (huge text).
const q = new URLSearchParams(location.search);
const tab = (q.get("tab") || "trades") as any;

function App() {
  const [search, setSearch] = useState(q.get("sheet") === "search");
  return (
    <div className="min-h-dvh" style={{ display: "flex", flexDirection: "column", flex: "auto", fontSize: q.get("big") ? "1.5rem" : undefined }}>
      <OverlayRuntime />
      <div style={{ padding: 16, flex: "auto" }}>
        {Array.from({ length: 40 }, (_, i) => (
          <div key={i} style={{ padding: 14, marginBottom: 8, border: "1px solid var(--color-border)", borderRadius: 14 }}>Row {i}</div>
        ))}
      </div>
      <Sheet open={search} onClose={() => setSearch(false)} title="Filter" description="Search">
        <input type="search" data-testid="sheet-search" placeholder="Search players" style={{ height: 44, fontSize: 16 }} />
        {Array.from({ length: 12 }, (_, i) => <div key={i} style={{ minHeight: 48 }}>Option {i}</div>)}
      </Sheet>
      <div className="bottom-stack md:hidden" data-dock="fixed" data-testid="stack" style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}>
        <div className="sim-action-bar action-pill" data-testid="sim-action-bar">
          <PillMorph segment={null} orb={<SimGameOrb tab={tab} offseason={false} inbox={Number(q.get("inbox") ?? 3)} onTab={() => {}} onMore={() => {}} onHub={() => {}} onSimTo={() => {}} />}>
            <div className="mx-auto flex max-w-3xl items-center gap-2 max-md:p-0" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <Button variant="secondary" size="sm" className="min-w-0 shrink-0 max-md:flex-col max-md:gap-0 max-md:self-stretch max-md:px-2" aria-label="Sim to..." data-testid="sim-to-button">
                <SimGlyph name="matchup" size={16} />
                <span className="text-xs leading-4 md:ml-1.5">Sim to</span>
              </Button>
              <Button className="min-w-0 whitespace-nowrap max-md:flex-1 max-md:self-stretch" data-testid="advance">Advance Wk 1 &rarr; 2</Button>
            </div>
          </PillMorph>
        </div>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
