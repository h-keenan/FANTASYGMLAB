import Link from "next/link";
import type { ReactNode } from "react";
import type {
  GmPlanFocusArea,
  GmPlanFocusItem,
  GmPlanInjuryItem,
  GmPlanPlayoffOddsItem,
  GmPlanRankItem,
  GmPlanRecordItem,
  GmPlanResponse,
  GmPlanTradeItem,
} from "@/lib/api";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { formatTradeGain } from "@/lib/tradeHubPresentation";
import { gmPlanReasonMessage } from "@/lib/gmPlanPresentation";

/**
 * Ports modules/gm_plan_ui.py's render_gm_plan_workspace / mobile's
 * GmPlanScreen.tsx for Revision 9 — GM Plan's season-arc roadmap: a
 * phase/stance hero, then three focus-area sections (Where You Stand,
 * Trade Opportunities, Roster Construction). Reads the exact same
 * GET .../gm-plan endpoint both of those already call — no duplicated
 * aggregation or valuation logic here, only presentation. Trade
 * Opportunities' give/get identity (OvrGauge/PositionBadge, via the
 * shared TradeAssetExchange extracted from Trade Hub) reuses the same
 * send_assets/receive_assets TradeAsset dicts Trade Hub's own cards
 * render — modules.gm_plan's visual-identity fix (PR #1047) already put
 * these on the wire; mobile's own screen just hasn't been updated to
 * render them yet, so this page is actually ahead of mobile here, not
 * behind it.
 *
 * Deliberately not a hard premium gate: unlike Streamlit's own GM Plan
 * route (current_user_is_premium() blur+lock), GET .../gm-plan itself
 * returns no entitlement/premium field at all — the same ungated contract
 * mobile's screen already relies on. Inventing a client-side paywall
 * beyond what the shared API encodes would be a product decision this
 * page has no basis for, not a port.
 */

function focusItemKey(item: GmPlanFocusItem, index: number): string {
  if ("partner_team_name" in item) return `trade-${item.my_player_id || item.their_player_id || index}`;
  if ("injury_need_positions" in item) return `injury-${index}`;
  if ("rank" in item) return `rank-${item.label}`;
  if ("wins" in item) return "record";
  return "playoff-odds";
}

function FactCard({ accent, children }: { accent: string; children: ReactNode }) {
  return (
    <article
      className="flex flex-col gap-1 p-3"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `3px solid ${accent}`,
      }}
    >
      {children}
    </article>
  );
}

function RankFact({ item }: { item: GmPlanRankItem }) {
  const weakSpot = Boolean(item.relative_weak_spot);
  const tieNote = item.tied ? " (tied)" : "";
  return (
    <FactCard accent={weakSpot ? "var(--color-danger)" : "var(--color-accent)"}>
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {item.label}: {item.rank}
        {item.total_teams ? ` of ${item.total_teams}` : ""}
        {tieNote}
      </p>
      {weakSpot ? (
        <p className="text-xs" style={{ color: "var(--color-danger)" }}>
          Relative weak spot in this league.
        </p>
      ) : null}
    </FactCard>
  );
}

function RecordFact({ item }: { item: GmPlanRecordItem }) {
  return (
    <FactCard accent="var(--color-accent)">
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        Record: {item.wins ?? 0}-{item.losses ?? 0}
        {item.ties ? `-${item.ties}` : ""}
      </p>
    </FactCard>
  );
}

function PlayoffOddsFact({ item }: { item: GmPlanPlayoffOddsItem }) {
  const seedNote = item.median_seed ? `, projected ${item.median_seed}-seed` : "";
  const statusNote = item.clinched ? " · Clinched" : item.eliminated ? " · Eliminated" : "";
  return (
    <FactCard accent="var(--color-accent)">
      <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
        {Math.round(item.playoff_probability)}% to make the playoffs{seedNote}
        {statusNote}
      </p>
    </FactCard>
  );
}

function InjuryExposureFact({ item }: { item: GmPlanInjuryItem }) {
  const positions = item.injury_need_positions.join(", ");
  return (
    <FactCard accent="var(--color-danger)">
      <p className="text-sm font-bold" style={{ color: "var(--color-danger)" }}>
        {item.health_flag || item.label}
        {positions ? `: ${positions}` : ""}
      </p>
      <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
        {item.summary || `No healthy bench cover at ${positions}.`}
      </p>
      {item.injured_players.length > 0 ? (
        <div className="flex flex-col divide-y mt-1" style={{ borderColor: "var(--color-border)" }}>
          {item.injured_players.map((player) => (
            <div key={player.player_id} className="flex items-center gap-2 py-1">
              <PlayerIdentityTrigger identity={{ ...player, sourceLabel: "GM Plan" }} className="flex items-center gap-2 flex-1 min-w-0">
                <PositionBadge position={player.position} />
                <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
                  {player.name}
                </span>
                {player.team ? (
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {player.team}
                  </span>
                ) : null}
              </PlayerIdentityTrigger>
              {player.injury_status ? (
                <span className="ml-auto text-xs font-bold" style={{ color: "var(--color-danger)" }}>
                  {player.injury_status}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </FactCard>
  );
}

function TradeOpportunityCard({ item }: { item: GmPlanTradeItem }) {
  const hasAssets = item.send_assets.length > 0 || item.receive_assets.length > 0;
  const injuryDisplay = item.their_player_injury_display || "";
  const accent = injuryDisplay ? "var(--color-danger)" : "var(--color-accent)";
  const gain = item.trade_gain;
  const hasGain = gain !== null && gain !== undefined;
  const gainColor = hasGain && gain! > 0 ? "var(--color-success)" : hasGain && gain! < 0 ? "var(--color-danger)" : "var(--color-text-secondary)";
  const theirLabel = injuryDisplay ? `${item.their_player} (${injuryDisplay})` : item.their_player;

  return (
    <article
      className="flex flex-col gap-3 p-4"
      style={{
        background: "var(--color-surface-secondary)",
        border: "var(--border-width-default) solid var(--color-border)",
        borderLeft: `3px solid ${accent}`,
        boxShadow: "var(--shadow-card)",
      }}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <h3 className="text-base font-extrabold truncate" style={{ color: "var(--color-text-primary)" }}>
          {item.partner_team_name || "Trade idea"}
        </h3>
        {hasGain ? (
          <span className="text-sm font-bold shrink-0" style={{ color: gainColor, fontVariantNumeric: "tabular-nums" }}>
            {formatTradeGain(gain!)}
          </span>
        ) : null}
      </div>

      {hasAssets ? (
        <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
          <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={item.send_assets} />
          <div
            className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
            style={{ color: "var(--color-accent)" }}
            aria-hidden="true"
          >
            FOR
          </div>
          <ExchangeSide label="You get" dotColor="var(--color-success)" assets={item.receive_assets} />
        </div>
      ) : (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {item.my_player} → {theirLabel}
        </p>
      )}

      {item.rationale || item.trade_confidence_label ? (
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {item.rationale || item.trade_confidence_label}
        </p>
      ) : null}
    </article>
  );
}

function FocusItem({ item }: { item: GmPlanFocusItem }) {
  if ("partner_team_name" in item) return <TradeOpportunityCard item={item} />;
  if ("injury_need_positions" in item) return <InjuryExposureFact item={item} />;
  if ("rank" in item) return <RankFact item={item} />;
  if ("wins" in item) return <RecordFact item={item} />;
  if ("playoff_probability" in item) return <PlayoffOddsFact item={item} />;
  return null;
}

function FocusAreaSection({ area }: { area: GmPlanFocusArea }) {
  return (
    <section className="flex flex-col gap-3">
      <div className="flex flex-col gap-0.5">
        <h2 style={{ font: "var(--type-section-title)" }}>{area.title}</h2>
        {area.framing ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {area.framing}
          </p>
        ) : null}
      </div>

      {area.status === "no_signal" ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {area.watch_for || "Nothing to flag right now."}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {area.items.map((item, index) => (
            <FocusItem key={focusItemKey(item, index)} item={item} />
          ))}
        </div>
      )}
    </section>
  );
}

export function GmPlanContent({
  leagueId,
  leagueName,
  data,
}: {
  /** Optional only so this component's existing unit tests (which predate
   * Team Situation's Revision 19 link below) don't all need updating —
   * app/gm-plan/[leagueId]/page.tsx always has a real one to pass. */
  leagueId?: string;
  leagueName: string;
  data: GmPlanResponse;
}) {
  const notice = data.reason ? gmPlanReasonMessage(data.reason) : null;
  if (notice) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const quiet = data.quiet || !data.focus_areas || data.focus_areas.length === 0;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          GM Plan
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          A season-arc roadmap: where you stand, your best trade paths, and your roster construction — framed by
          your declared Team Situation.
        </p>
      </header>

      {quiet ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          We don&apos;t have enough to build a GM Plan for this league yet.
        </p>
      ) : (
        <>
          <section
            className="flex flex-col gap-2 p-4"
            style={{
              background: "var(--color-surface-secondary)",
              border: "var(--border-width-default) solid var(--color-border)",
              boxShadow: "var(--shadow-card)",
            }}
          >
            <div className="flex items-center gap-2 flex-wrap">
              {data.season_phase_label ? (
                <span
                  className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
                  style={{
                    color: "var(--color-information)",
                    background: "var(--color-information-soft)",
                    letterSpacing: "var(--letter-spacing-badge)",
                  }}
                >
                  {data.season_phase_label}
                </span>
              ) : null}
              {data.team_stance_label ? (
                <span
                  className="px-1.5 py-0.5 uppercase text-xs font-extrabold"
                  style={{
                    color: "var(--color-premium)",
                    background: "var(--color-action-soft)",
                    letterSpacing: "var(--letter-spacing-badge)",
                  }}
                >
                  {data.team_stance_label}
                </span>
              ) : null}
            </div>
            {data.headline ? (
              <p className="text-base font-bold" style={{ color: "var(--color-text-primary)" }}>
                {data.headline}
              </p>
            ) : null}
            {leagueId ? (
              <Link
                href={`/team-situation/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`}
                className="text-xs font-bold self-start"
                style={{ color: "var(--color-accent)" }}
              >
                {data.team_stance_label ? "Change your Team Situation" : "Declare your Team Situation"} →
              </Link>
            ) : null}
          </section>

          <div className="flex flex-col gap-6">
            {data.focus_areas.map((area) => (
              <FocusAreaSection key={area.key} area={area} />
            ))}
          </div>
        </>
      )}
    </main>
  );
}
