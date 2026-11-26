"use client";

import { useEffect, useRef, useState } from "react";

import { trackSampleLeague } from "@/lib/analytics";

import { BottomDock } from "@/components/ui/BottomDock";
import { DashboardContent } from "@/components/DashboardContent";
import { PillRow } from "@/components/PillRow";
import { PresenceSwap } from "@/components/ui/Presence";
import { BottomTabBar } from "@/components/ui/BottomTabBar";
import { SampleConnectModule, SampleLeagueBanner } from "@/components/SampleLeagueBanner";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { SAMPLE_DASHBOARD_LEAGUE_ID, sampleDashboardResponse, sampleTeamRankings } from "@/lib/sampleDashboard";
import {
  SAMPLE_BLOCKED_MESSAGE,
  SAMPLE_DASHBOARD_NOTE,
  SAMPLE_GAME_PLAN,
  SAMPLE_LEAGUE_NAME,
  SAMPLE_ROSTER,
  SAMPLE_TABS,
  SAMPLE_TEAM_NAME,
  SAMPLE_TRADE,
  sampleTradeVerdict,
  type SamplePlayer,
  type SampleTab,
} from "@/lib/sampleLeague";
import { CompactModule } from "@/components/ui/CompactModule";
import { PlayerAccordionRow, usePlayerAccordion } from "@/components/ui/PlayerAccordionRow";
import { StatusHeader } from "@/components/ui/StatusHeader";
import { TradeCompactCard, type TradeCardAsset } from "@/components/ui/TradeCompactCard";
import type { StatusHeaderModel } from "@/lib/statusHeader";
import { SAMPLE_ACTIVE_EVENT, SAMPLE_SELECT_EVENT } from "@/lib/sampleSidebar";

/** Fictional players have no photo: id null keeps the shared avatar slot on initials instead of a failing request. */
function samplePlayerRef(player: SamplePlayer) {
  return { id: null, name: player.name, position: player.position, age: player.age };
}

/** One roster row on the shipped player template (avatar, position badge, meta, trailing value; tap for the note). */
function SamplePlayerRow({ player, acc }: { player: SamplePlayer; acc: ReturnType<typeof usePlayerAccordion> }) {
  return (
    <PlayerAccordionRow
      player={samplePlayerRef(player)}
      mode="desk"
      value={player.value}
      metaText={`Age ${player.age}`}
      open={acc.isOpen(player.id)}
      onToggle={() => acc.toggle(player.id)}
      testId="sample-player"
    >
      <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{player.note}</p>
    </PlayerAccordionRow>
  );
}

function tradeAsset(player: SamplePlayer): TradeCardAsset {
  return { key: player.id, player: samplePlayerRef(player), detail: `Age ${player.age} · ${player.note}`, value: player.value };
}

/** The real Dashboard modules fed static fictional data; links are inert. */
function DashboardTab() {
  const [data] = useState(sampleDashboardResponse);
  const [teamRankings] = useState(sampleTeamRankings);
  const [blocked, setBlocked] = useState(false);
  return (
    <section className="flex flex-col gap-4" aria-label="Sample dashboard">
      <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
        {SAMPLE_DASHBOARD_NOTE}
      </p>
      {blocked ? (
        <p role="status" className="text-xs font-bold" style={{ color: "var(--color-accent)" }} data-testid="sample-blocked">
          {SAMPLE_BLOCKED_MESSAGE}
        </p>
      ) : null}
      <DashboardContent
        leagueId={SAMPLE_DASHBOARD_LEAGUE_ID}
        leagueName={SAMPLE_LEAGUE_NAME}
        data={data}
        teamRankings={teamRankings}
        sample={{ onBlockedLink: () => setBlocked(true) }}
      />
    </section>
  );
}

function RosterTab() {
  const acc = usePlayerAccordion();
  const avgAge = SAMPLE_ROSTER.reduce((sum, p) => sum + p.age, 0) / SAMPLE_ROSTER.length;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-roster-heading">
      <SectionHeading id="sample-roster-heading" note="Sample scores are made-up 0-100 numbers.">
        Roster
      </SectionHeading>
      <CompactModule id="sample.roster" title="Roster" parts={[{ key: "n", text: `${SAMPLE_ROSTER.length} players`, strong: true }, { key: "age", text: `Avg age ${avgAge.toFixed(1)}` }]} defaultOpen persist={false}>
        <div className="flex min-w-0 flex-col">
          {SAMPLE_ROSTER.map((player) => (
            <SamplePlayerRow key={player.id} player={player} acc={acc} />
          ))}
        </div>
      </CompactModule>
    </section>
  );
}

function GamePlanTab({ onNavigate }: { onNavigate: (tab: SampleTab) => void }) {
  const [first, ...rest] = SAMPLE_GAME_PLAN;
  const model: StatusHeaderModel = {
    kicker: first.kicker,
    headline: first.headline,
    context: "Sample moves for Demo Squad",
    ring: null,
    stats: [
      { key: "moves", label: "Moves", value: String(SAMPLE_GAME_PLAN.length) },
      { key: "sell", label: "Sell", value: "1", tone: "warning" },
      { key: "add", label: "Add", value: "1", tone: "success" },
    ],
    attention: SAMPLE_GAME_PLAN.map((item, index) => {
      const player = SAMPLE_ROSTER.find((p) => p.id === item.playerId) ?? SAMPLE_ROSTER[0];
      return {
        key: `${item.kicker}-${index}`,
        playerId: null,
        name: player.name,
        position: player.position,
        team: null,
        meta: item.kicker,
        stat: { value: String(player.value), label: "VALUE" },
        detail: item.reason,
      };
    }),
    primary: { label: first.cta === "trade" ? "Open sample trade" : "Open sample roster", actionKey: first.cta },
  };
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-plan-heading">
      <SectionHeading id="sample-plan-heading">Today</SectionHeading>
      <StatusHeader model={model} attentionTitle="Top moves" onAction={(key) => onNavigate(key === "trade" ? "trade" : "roster")}>
        {rest.map((item) => (
          <CompactModule key={item.headline} id={`sample.plan.${item.playerId}`} title={item.kicker} parts={[{ key: "h", text: item.headline, strong: true }]} persist={false}>
            <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{item.reason}</p>
            <button type="button" onClick={() => onNavigate(item.cta === "trade" ? "trade" : "roster")} className="self-start text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}>
              {item.cta === "trade" ? "Open sample trade" : "Open sample roster"} →
            </button>
          </CompactModule>
        ))}
      </StatusHeader>
    </section>
  );
}

function TradeTab() {
  const verdict = sampleTradeVerdict(SAMPLE_TRADE);
  const tone = `var(--color-${verdict.tone})`;
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-trade-heading">
      <SectionHeading id="sample-trade-heading" note={`Sample offer with ${SAMPLE_TRADE.partner}`}>
        Trade
      </SectionHeading>
      <div className="flex items-center gap-2">
        <ToneBadge label={verdict.label} color={tone} testId="sample-verdict" />
        <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          You send {verdict.giveTotal}, you get {verdict.getTotal}
        </span>
      </div>
      <TradeCompactCard title={`Offer with ${SAMPLE_TRADE.partner}`} give={SAMPLE_TRADE.give.map(tradeAsset)} get={SAMPLE_TRADE.get.map(tradeAsset)} netValue={verdict.gap} defaultOpen testId="sample-trade-card">
        <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Sample verdict: a real one weighs your roster needs, league scoring and what this manager tends to accept.
        </p>
      </TradeCompactCard>
      {/* On desktop the same module lives in the right rail (SampleLeagueContent). */}
      <div className="lg:hidden">
        <SampleConnectModule />
      </div>
    </section>
  );
}

/**
 * Static sample league: no network calls, no auth, no analytics. It wears the
 * same chrome as a real league: a sticky tab strip under a slim sample bar on
 * wider screens, and on phones the shared fixed, portaled `BottomDock` with
 * the shared BottomTabBar (the one bottom mechanism: fixed dock + content clearance).
 */
export function SampleLeagueContent() {
  const [tab, setTab] = useState<SampleTab>("dashboard");
  const tabs = SAMPLE_TABS.map((t) => ({ key: t.value, label: t.label, glyph: t.glyph }));
  // The desktop sidebar drives the views through a window event and mirrors the active one back.
  useEffect(() => {
    const onSelect = (event: Event) => setTab((event as CustomEvent<SampleTab>).detail);
    window.addEventListener(SAMPLE_SELECT_EVENT, onSelect);
    return () => window.removeEventListener(SAMPLE_SELECT_EVENT, onSelect);
  }, []);
  useEffect(() => {
    window.dispatchEvent(new CustomEvent(SAMPLE_ACTIVE_EVENT, { detail: tab }));
  }, [tab]);
  // Demo usage analytics (demo=true; see lib/analytics.ts trackSampleLeague): one view per session, then tab changes.
  const firstTab = useRef(true);
  useEffect(() => {
    if (firstTab.current) {
      firstTab.current = false;
      trackSampleLeague("viewed", tab);
      return;
    }
    trackSampleLeague("tab", tab);
  }, [tab]);
  return (
    <>
      <main className="page-shell page-shell-wide">
        <SampleLeagueBanner />
        <div className="flex flex-col gap-1">
          <h1 style={{ font: "var(--font-page-title)" }}>{SAMPLE_TEAM_NAME}</h1>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {SAMPLE_LEAGUE_NAME} (sample)
          </p>
        </div>
        {/* Phone: one column. From lg: the view on the left, a sticky rail on the right with the one way to get the real thing. */}
        <div className="sample-grid">
          <div className="flex min-w-0 flex-col gap-[var(--page-gap)]">
            <div className="sticky z-20 max-md:hidden" style={{ top: "3.25rem" }} data-testid="sample-tab-strip">
              <PillRow
                glass
                variant="scroll"
                ariaLabel="Sample league views"
                options={SAMPLE_TABS.map((t) => ({ label: t.label, value: t.value, glyph: t.glyph }))}
                active={tab}
                onSelect={(value) => setTab(value as SampleTab)}
              />
            </div>
            {/* Tab bodies cross-fade (fade out, then rise in) instead of one hard cut. */}
            <PresenceSwap swapKey={tab} className="flex min-w-0 flex-col gap-[var(--page-gap)]">
              {tab === "dashboard" ? <DashboardTab /> : null}
              {tab === "roster" ? <RosterTab /> : null}
              {tab === "game_plan" ? <GamePlanTab onNavigate={setTab} /> : null}
              {tab === "trade" ? <TradeTab /> : null}
            </PresenceSwap>
          </div>
          <aside className="sample-rail max-lg:hidden" aria-label="Connect your league">
            <SampleConnectModule />
          </aside>
        </div>
      </main>
      <BottomDock className="md:hidden" testId="sample-bottom-stack">
        <BottomTabBar ariaLabel="Sample league views" tabs={tabs} active={tab} testId="sample-tab-bar" onSelect={(key) => setTab(key as SampleTab)} />
      </BottomDock>
    </>
  );
}
