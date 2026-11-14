"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { BottomDock } from "@/components/ui/BottomDock";
import { DashboardContent } from "@/components/DashboardContent";
import { PillRow } from "@/components/PillRow";
import { BottomTabBar } from "@/components/ui/BottomTabBar";
import { PositionBadge } from "@/components/PositionBadge";
import { SampleConnectModule, SampleLeagueBanner } from "@/components/SampleLeagueBanner";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueStat } from "@/components/ValueStat";
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
import { PlayerName } from "@/components/PlayerName";
import { SAMPLE_ACTIVE_EVENT, SAMPLE_SELECT_EVENT } from "@/lib/sampleSidebar";

function SamplePlayerRow({ player, first = false }: { player: SamplePlayer; first?: boolean }) {
  return (
    <li className="flex items-center gap-3 py-2 min-h-[var(--touch-target-min)]" style={first ? undefined : { borderTop: "1px solid var(--color-border)" }}>
      <span className="flex w-10 shrink-0 justify-start">
        <PositionBadge position={player.position} />
      </span>
      <span className="min-w-0 flex-1 flex flex-col">
        <PlayerName name={player.name} className="text-sm font-bold" />
        <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Age {player.age} · {player.note}
        </span>
      </span>
      <ValueStat value={player.value} />
    </li>
  );
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
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-roster-heading">
      <SectionHeading id="sample-roster-heading" note="Sample scores are made-up 0-100 numbers.">
        Roster
      </SectionHeading>
      <AccentCard accent="var(--color-accent)" compact>
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {SAMPLE_ROSTER.map((player, index) => (
            <SamplePlayerRow key={player.id} player={player} first={index === 0} />
          ))}
        </ul>
      </AccentCard>
    </section>
  );
}

function GamePlanTab({ onNavigate }: { onNavigate: (tab: SampleTab) => void }) {
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-plan-heading">
      <SectionHeading id="sample-plan-heading">Today</SectionHeading>
      {SAMPLE_GAME_PLAN.map((item) => (
        <AccentCard key={item.headline} accent="var(--color-accent)">
          <span className="uppercase" style={{ font: "var(--type-badge-size)", letterSpacing: "var(--letter-spacing-badge)", color: "var(--color-accent)" }}>
            {item.kicker}
          </span>
          <h3 style={{ font: "var(--font-card-title)" }}>{item.headline}</h3>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {item.reason}
          </p>
          <button
            type="button"
            onClick={() => onNavigate(item.cta === "trade" ? "trade" : "roster")}
            className="self-start text-sm font-bold mt-1 min-h-[var(--touch-target-min)]"
            style={{ color: "var(--color-accent)" }}
          >
            {item.cta === "trade" ? "Open sample trade" : "Open sample roster"} →
          </button>
        </AccentCard>
      ))}
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
      <AccentCard accent={tone}>
        <div className="flex items-center gap-2">
          <ToneBadge label={verdict.label} color={tone} testId="sample-verdict" />
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            You send {verdict.giveTotal}, you get {verdict.getTotal}
          </span>
        </div>
        {[
          { title: "You give", players: SAMPLE_TRADE.give },
          { title: "You get", players: SAMPLE_TRADE.get },
        ].map((side) => (
          <div key={side.title}>
            <p className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
              {side.title}
            </p>
            <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {side.players.map((player, index) => (
                <SamplePlayerRow key={player.id} player={player} first={index === 0} />
              ))}
            </ul>
          </div>
        ))}
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Sample verdict: a real one weighs your roster needs, league scoring and what this manager tends to accept.
        </p>
      </AccentCard>
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
            {tab === "dashboard" ? <DashboardTab /> : null}
            {tab === "roster" ? <RosterTab /> : null}
            {tab === "game_plan" ? <GamePlanTab onNavigate={setTab} /> : null}
            {tab === "trade" ? <TradeTab /> : null}
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
