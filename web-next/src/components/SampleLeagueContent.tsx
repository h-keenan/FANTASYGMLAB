"use client";

import { useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { DashboardContent } from "@/components/DashboardContent";
import { PillRow } from "@/components/PillRow";
import { PositionBadge } from "@/components/PositionBadge";
import { SampleLeagueBanner } from "@/components/SampleLeagueBanner";
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

function SamplePlayerRow({ player }: { player: SamplePlayer }) {
  return (
    <li className="flex items-center gap-3 py-2 min-h-[var(--touch-target-min)]" style={{ borderTop: "1px solid var(--color-border)" }}>
      <span className="flex w-10 shrink-0 justify-start">
        <PositionBadge position={player.position} />
      </span>
      <span className="min-w-0 flex-1 flex flex-col">
        <span className="text-sm font-bold">{player.name}</span>
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
    <section className="flex flex-col gap-3" aria-label="Sample dashboard">
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
          {SAMPLE_ROSTER.map((player) => (
            <SamplePlayerRow key={player.id} player={player} />
          ))}
        </ul>
      </AccentCard>
    </section>
  );
}

function GamePlanTab({ onNavigate }: { onNavigate: (tab: SampleTab) => void }) {
  return (
    <section className="flex flex-col gap-2" aria-labelledby="sample-plan-heading">
      <SectionHeading id="sample-plan-heading">Game Plan</SectionHeading>
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
              {side.players.map((player) => (
                <SamplePlayerRow key={player.id} player={player} />
              ))}
            </ul>
          </div>
        ))}
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          Sample verdict: a real one weighs your roster needs, league scoring and what this manager tends to accept.
        </p>
      </AccentCard>
    </section>
  );
}

/** Static sample league: no network calls, no auth, no analytics. */
export function SampleLeagueContent() {
  const [tab, setTab] = useState<SampleTab>("dashboard");
  return (
    <main className="flex-1 flex flex-col gap-4 px-4 py-4 w-full max-w-2xl mx-auto">
      <SampleLeagueBanner />
      <div className="flex flex-col gap-1">
        <h1 style={{ font: "var(--font-page-title)" }}>{SAMPLE_TEAM_NAME}</h1>
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {SAMPLE_LEAGUE_NAME} (sample)
        </p>
      </div>
      <PillRow
        fullWidth
        ariaLabel="Sample league views"
        options={SAMPLE_TABS.map((t) => ({ label: t.label, value: t.value }))}
        active={tab}
        onSelect={(value) => setTab(value as SampleTab)}
      />
      {tab === "dashboard" ? <DashboardTab /> : null}
      {tab === "roster" ? <RosterTab /> : null}
      {tab === "game_plan" ? <GamePlanTab onNavigate={setTab} /> : null}
      {tab === "trade" ? <TradeTab /> : null}
    </main>
  );
}
