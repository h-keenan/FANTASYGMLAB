"use client";

import dynamic from "next/dynamic";

import { CompactModule } from "@/components/ui/CompactModule";
import { ExpandRow } from "@/components/ui/ExpandRow";

// Below-the-fold modules load as their own chunks, after the above-the-fold content has hydrated.
const GuessThePlayerCard = dynamic(() => import("@/components/GuessThePlayerCard").then((m) => m.GuessThePlayerCard), { loading: () => null });
const GuessThePlayerNameMatchCard = dynamic(() => import("@/components/GuessThePlayerNameMatchCard").then((m) => m.GuessThePlayerNameMatchCard), { loading: () => null });
const LeaguePulseCard = dynamic(() => import("@/components/LeaguePulseCard").then((m) => m.LeaguePulseCard), { loading: () => null });

/**
 * League activity and the two mini-games, collapsed to ONE line each, on the League tab (they are play and league color,
 * not decisions, so they no longer sit on Today). A line opens its full card. Mobile twin: the same modules on the
 * Teams screen (screens/TeamsScreen.tsx).
 */
export function LeagueMore({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  return (
    <CompactModule
      id="league.more"
      title="League extras"
      testId="league-more"
      tone="muted"
      parts={[
        { key: "a", text: "League activity" },
        { key: "g", text: "2 mini-games" },
      ]}
    >
      <ul className="m-0 flex list-none flex-col p-0 [&>li+li]:border-t [&>li+li]:border-[var(--color-border)]">
        <ExpandRow label="League activity" title="League activity" caption="Most active manager, streaks" testId="more-league-activity">
          <LeaguePulseCard leagueId={leagueId} leagueName={leagueName} />
        </ExpandRow>
        <ExpandRow label="Guess the Player" title="Guess the Player" caption="Today's round" testId="more-guess-player">
          <GuessThePlayerCard leagueId={leagueId} leagueName={leagueName} />
        </ExpandRow>
        <ExpandRow label="Name match" title="Name match" caption="Match names to faces" testId="more-name-match">
          <GuessThePlayerNameMatchCard leagueId={leagueId} leagueName={leagueName} />
        </ExpandRow>
      </ul>
    </CompactModule>
  );
}
