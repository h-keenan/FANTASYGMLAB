"use client";

import { useMemo, useState } from "react";

import type { DraftCard, DraftCenterResponse, DraftPickAsset } from "@/lib/api";
import { PickRow } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { SnapshotTile, formatRank } from "@/components/SnapshotTile";
import { streamlitPageUrl } from "@/lib/streamlitLink";
import {
  POSTURE_REASON_MESSAGE,
  groupPicksBySeason,
  visibleDraftPicks,
  type PickScope,
} from "@/lib/draftCenterPresentation";

/**
 * Ports mobile's DraftCenterScreen.tsx (the GM_TOOLS "Draft Center" nav
 * destination) for Revision 14 — same two endpoints, same scope: your own
 * draft posture, pick values with a My Picks/League toggle, and the
 * league-wide decision/partner cards. Streamlit's Draft Center has three
 * more panes (Current Draft/History — a live draft board with manual pick
 * overrides, PR #1015 — and Scouting); none of those have a mobile
 * reference implementation or a backing endpoint (see GET
 * .../draft-center's own docstring), so inventing them here would be
 * guessed scope, not a thin wrapper over something real. They stay on the
 * classic page via the deep link at the bottom of this one, same
 * "not yet ported" contract LeagueRecapsContent.tsx's Storylines tab uses.
 */
export function DraftCenterContent({
  leagueName,
  data,
  picks,
  myRosterId,
}: {
  leagueName: string;
  data: DraftCenterResponse;
  picks: DraftPickAsset[];
  myRosterId: string;
}) {
  // Nothing to scope to without a resolved roster — don't strand the user
  // on an empty "My Picks" tab they can't fill, same guard mobile's screen
  // applies to its own initial pickScope.
  const [pickScope, setPickScope] = useState<PickScope>(myRosterId ? "mine" : "league");

  const visiblePicks = useMemo(
    () => visibleDraftPicks(picks, pickScope, myRosterId),
    [picks, pickScope, myRosterId],
  );
  const pickSeasons = useMemo(() => groupPicksBySeason(visiblePicks), [visiblePicks]);

  const { posture, posture_reason: postureReason, decision_cards: decisionCards, partner_cards: partnerCards } = data;

  return (
    <main className="flex-1 flex flex-col gap-8 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Draft Center
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Your draft posture, pick values, and who to call before you open Trade Hub.
        </p>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="posture-heading">
        <h2 id="posture-heading" style={{ font: "var(--type-section-title)" }}>
          Your Draft Posture
        </h2>
        {posture ? (
          <>
            <div className="flex flex-wrap gap-3">
              <SnapshotTile
                label="Draft Capital"
                value={formatRank(posture.draft_capital_rank, posture.draft_capital_rank_tied)}
                note={posture.draft_capital != null ? `${Math.round(posture.draft_capital)} total capital` : undefined}
                tone={posture.draft_capital_rank === 1 ? "premium" : "neutral"}
              />
              <SnapshotTile
                label="Future Capital"
                value={formatRank(posture.future_draft_capital_rank, posture.future_draft_capital_rank_tied)}
                note={
                  posture.future_draft_capital != null
                    ? `${Math.round(posture.future_draft_capital)} beyond this draft`
                    : undefined
                }
                tone={posture.future_draft_capital_rank === 1 ? "premium" : "neutral"}
              />
              <SnapshotTile
                label="Strategy"
                value={posture.strategy_display || "—"}
                note={`Roster Power ${formatRank(posture.power_rank, posture.power_rank_tied)} · Franchise ${formatRank(
                  posture.franchise_rank,
                  posture.franchise_rank_tied,
                )}`}
              />
            </div>
            <div className={`tone-${posture.tone} p-4 flex flex-col gap-2`}>
              <span
                className="tone-value text-sm font-extrabold uppercase self-start"
                style={{ letterSpacing: "var(--letter-spacing-badge)" }}
              >
                {posture.label}
              </span>
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {posture.note}
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {posture.first_rounders ?? 0} tracked first-rounders · {posture.pick_count ?? 0} total picks
              </p>
            </div>
          </>
        ) : (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            {POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now."}
          </p>
        )}
      </section>

      {picks.length > 0 ? (
        <section className="flex flex-col gap-3" aria-labelledby="pick-values-heading">
          <h2 id="pick-values-heading" style={{ font: "var(--type-section-title)" }}>
            Pick Values
          </h2>
          {myRosterId ? (
            <PillRow
              options={[
                { label: "My Picks", value: "mine" },
                { label: "League", value: "league" },
              ]}
              active={pickScope}
              onSelect={(value) => setPickScope(value as PickScope)}
            />
          ) : null}
          {pickSeasons.length > 0 ? (
            pickSeasons.map(([season, seasonPicks]) => (
              <div key={season} className="flex flex-col gap-2">
                <span
                  className="text-xs font-bold uppercase"
                  style={{ color: "var(--color-text-secondary)", letterSpacing: "0.04em" }}
                >
                  {season || "Future"}
                </span>
                <div
                  style={{
                    background: "var(--color-surface-secondary)",
                    border: "var(--border-width-default) solid var(--color-border)",
                  }}
                >
                  {seasonPicks.map((pick, index) => (
                    <PickRow
                      key={pick.pick_id}
                      pick={pick}
                      showOwner={pickScope === "league"}
                      showDivider={index < seasonPicks.length - 1}
                    />
                  ))}
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              {pickScope === "mine"
                ? "You don't hold any tracked picks in this league right now."
                : "No draft pick assets available for this league yet."}
            </p>
          )}
        </section>
      ) : null}

      <DraftCardSection id="decision-signals-heading" title="League Draft Decision Signals" cards={decisionCards} />
      <DraftCardSection id="partner-discovery-heading" title="Draft Partner Discovery" cards={partnerCards} />

      <section className="flex flex-col gap-2" aria-labelledby="classic-draft-heading">
        <h2 id="classic-draft-heading" style={{ font: "var(--type-section-title)" }}>
          More Draft Tools
        </h2>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          The live draft board (with manual pick overrides), draft history, and future-class scouting still live on
          the classic page.
        </p>
        <a
          href={streamlitPageUrl("draft_summary")}
          target="_blank"
          rel="noopener noreferrer"
          className="self-start text-xs font-bold uppercase px-3 py-2"
          style={{ background: "var(--color-accent)", color: "var(--color-bg)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          Open classic Draft Center
        </a>
      </section>
    </main>
  );
}

/**
 * League Draft Decision Signals / Draft Partner Discovery — reuses the
 * `tone-${tone}`/`.tone-value` CSS utility classes MyTeamContent.tsx's
 * Strength & Pressure cards already use (globals.css, ported from
 * modules/card_hierarchy_styles.py) instead of a bespoke tone->color map,
 * since draft_center_ui.py's card tones are that same vocabulary.
 */
function DraftCardSection({ id, title, cards }: { id: string; title: string; cards: DraftCard[] }) {
  if (cards.length === 0) return null;
  return (
    <section className="flex flex-col gap-3" aria-labelledby={id}>
      <h2 id={id} style={{ font: "var(--type-section-title)" }}>
        {title}
      </h2>
      <div className="flex flex-col gap-3">
        {cards.map((card) => (
          <div key={card.label} className={`tone-${card.tone} p-4 flex flex-col gap-2`}>
            <span
              className="tone-value text-xs font-bold uppercase self-start"
              style={{ letterSpacing: "var(--letter-spacing-badge)" }}
            >
              {card.label}
            </span>
            <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
              {card.title}
            </p>
            <ul className="flex flex-col gap-1">
              {card.items.map((item, index) => (
                <li key={index} className="text-sm flex gap-2" style={{ color: "var(--color-text-secondary)" }}>
                  <span aria-hidden="true">•</span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
