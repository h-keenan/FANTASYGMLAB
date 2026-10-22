"use client";

import { useEffect, useMemo, useState } from "react";

import type { AlertItem, AlertsResponse } from "@/lib/api";
import { markAlertReadSynced, overlayPendingAlertReads, reconcileAlertReads } from "@/lib/alertReadSync";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import {
  ROSTER_RELATIONSHIP_LABEL,
  alertsReasonMessage,
  eventTypeColorVar,
  eventTypeLabel,
  groupAlertsByType,
  relativeTime,
  rosterRelationshipColorVar,
} from "@/lib/alertsPresentation";

/**
 * Ports mobile's AlertsScreen.tsx (mobile/src/screens) for Revision 7 —
 * the "LEAGUE" nav destination's notification/alert feed. Reads from the
 * exact same GET .../alerts endpoint that screen already calls (see that
 * endpoint's docstring in services/mobile_api_service.py) — nothing added
 * there, every field this page uses (items, categories via `event_type`,
 * `read`, matched-player identity) was already returned.
 *
 * Deliberately NOT ported: Streamlit's richer `alerts_activity_ui.py`
 * timeline — "Needs Your Attention" / "My Players" / "Around the League"
 * tiers, the Priority/My Players/News/League/Decisions filter pills, and
 * per-row Dismiss. That surface also folds in the Dashboard-style action
 * inbox (modules/notification_center.py), which carries real
 * trade_hub/waivers/my_team/rankings page destinations — unlike this
 * roster-news feed, whose only two CTAs (source article link, matched
 * player identity) match mobile's screen exactly. Porting the tiered
 * timeline would mean a new, session-state-shaped backend surface, not a
 * thin wrapper over this one — left for a future revision rather than
 * guessed at here. Any alert destination that DID match an already-built
 * page (Dashboard/My Team/Trade Hub/Waivers/Matchup/League Rankings) would
 * route there via Next <Link>, same contract as GamePlanCard.tsx — there
 * is just no such field on this feed's items today.
 *
 * Also NOT ported: the recap-ready header card (mobile's RecapReadyCard) —
 * League Recaps has no Next.js page yet, nothing to link it to.
 */

// coridian_: "you need to be able to click on the players (needs to be
// compact player card)" — the whole row is also a link/button (source
// article, or mark-as-read), so this can't just nest a second <button>
// inside it (invalid HTML inside the <a> case, and would fight the row's
// own click handler either way). AlertRow below instead uses the standard
// "stretched link" layout: the row's own link/button is an absolutely-
// positioned full-cover sibling with no z-index, and this chip gets
// `relative z-10` so it paints above that overlay and intercepts its own
// taps first — tapping the chip opens the player card, tapping anywhere
// else on the row still hits the row's own link/button underneath.
function AlertIdentityChip({ alert }: { alert: AlertItem }) {
  const row = (
    <>
      <PositionBadge position={alert.matched_player_position} />
      <PlayerAvatar playerId={alert.matched_player_id} tier={alert.matched_player_tier} size={28} />
      <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
        {alert.matched_player}
      </span>
      {alert.matched_player_team ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {alert.matched_player_team}
        </span>
      ) : null}
    </>
  );
  if (!alert.matched_player_id) {
    return <div className="flex items-center gap-2 mt-1">{row}</div>;
  }
  return (
    <PlayerIdentityTrigger
      identity={{
        player_id: alert.matched_player_id,
        name: alert.matched_player,
        position: alert.matched_player_position,
        team: alert.matched_player_team,
        tier: alert.matched_player_tier,
        sourceLabel: "Alerts",
      }}
      className="flex items-center gap-2 mt-1 relative z-10"
    >
      {row}
    </PlayerIdentityTrigger>
  );
}

function AlertRow({ alert, onOpen }: { alert: AlertItem; onOpen: (alert: AlertItem) => void }) {
  const relationship = alert.roster_relationship;
  const sourceBit = alert.source ? `Source: ${alert.source}` : null;
  const time = relativeTime(alert.published_ts);
  const hasLink = Boolean(alert.link);

  const body = (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        {!alert.read ? (
          <span
            aria-label="Unread"
            className="inline-block"
            style={{ width: "7px", height: "7px", borderRadius: "50%", background: "var(--color-accent)" }}
          />
        ) : null}
        {relationship ? (
          <span
            className="px-1.5 py-0.5 text-xs font-extrabold uppercase"
            style={{
              borderRadius: "var(--radius-pill)",
              background: `color-mix(in srgb, ${rosterRelationshipColorVar(relationship)} 15%, transparent)`,
              color: rosterRelationshipColorVar(relationship),
              letterSpacing: "var(--letter-spacing-badge)",
            }}
          >
            {ROSTER_RELATIONSHIP_LABEL[relationship]}
          </span>
        ) : null}
        <span className="flex-1" />
        {time ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {time}
          </span>
        ) : null}
        {hasLink ? (
          <span style={{ color: "var(--color-text-muted)" }} aria-hidden="true">
            →
          </span>
        ) : null}
      </div>

      {alert.matched_player ? (
        <AlertIdentityChip alert={alert} />
      ) : null}

      <p
        className="text-sm font-bold mt-1"
        style={{ color: alert.read ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}
      >
        {alert.title}
      </p>

      {alert.summary ? (
        <p className="text-sm mt-1" style={{ font: "var(--type-caption-emphasis)", color: "var(--color-text-secondary)" }}>
          {alert.summary}
        </p>
      ) : null}

      {alert.speculative ? (
        <p className="text-xs font-bold mt-1" style={{ color: "var(--color-warning)" }}>
          Unconfirmed / speculative
        </p>
      ) : null}

      {sourceBit ? (
        <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }}>
          {sourceBit}
        </p>
      ) : null}
    </>
  );

  const rowStyle = { opacity: alert.read ? 0.65 : 1 } as const;

  if (hasLink) {
    // A <button> (the identity chip) can't nest inside a real <a> — invalid
    // HTML. The link becomes an absolutely-positioned full-cover sibling
    // instead (no z-index, so the chip's own `relative z-10` paints above
    // it and wins the tap), same "stretched link" layout noted on
    // AlertIdentityChip above.
    return (
      <div className="relative block py-3" style={{ ...rowStyle, borderBottom: "var(--border-width-default) solid var(--color-border)" }}>
        {body}
        <a
          href={alert.link ?? "#"}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => onOpen(alert)}
          aria-label={alert.title ?? "Open article"}
          className="absolute inset-0"
        />
      </div>
    );
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onOpen(alert)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") onOpen(alert);
      }}
      className="block py-3 cursor-pointer"
      style={{ ...rowStyle, borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      {body}
    </div>
  );
}

export function AlertsContent({
  leagueId,
  leagueName,
  data,
  userId = "",
}: {
  leagueId: string;
  leagueName: string;
  data: AlertsResponse;
  /** Scopes this browser's not-yet-synced reads to the signed-in account. */
  userId?: string;
}) {
  // `read` comes from the server's cross-device read table (the same one
  // the mobile app writes), overlaid with any read tapped here that hasn't
  // reached the server yet — see lib/alertReadSync.ts.
  const [tappedRead, setTappedRead] = useState<ReadonlySet<string>>(() => new Set());
  useEffect(() => {
    // Side effects only: drop pending reads the server now confirms and
    // re-send the rest. Rendering below already shows them as read.
    reconcileAlertReads(userId, leagueId, data.items);
  }, [userId, leagueId, data]);
  const items = useMemo(
    () =>
      overlayPendingAlertReads(userId, leagueId, data.items).map((row) =>
        !row.read && tappedRead.has(row.alert_key) ? { ...row, read: true } : row,
      ),
    [userId, leagueId, data, tappedRead],
  );

  const notice = data.reason ? alertsReasonMessage(data.reason) : null;
  if (notice) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p className="text-sm text-center" style={{ color: "var(--color-text-muted)" }}>
          {notice}
        </p>
      </main>
    );
  }

  const openAndMarkRead = (alert: AlertItem) => {
    if (!alert.read) {
      setTappedRead((prev) => new Set(prev).add(alert.alert_key));
      // Never blocks or errors the tap: the read is remembered locally and
      // retried on the next load if this POST fails or the backend answers
      // ok: false (see mark_league_alert_read's docstring).
      void markAlertReadSynced(userId, leagueId, alert.alert_key);
    }
  };

  const groups = groupAlertsByType(items);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Alerts
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          Recent news about players on your roster — injury, role, transaction, and off-field signal only.
        </p>
      </header>

      {groups.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          All quiet. No relevant news for your roster right now.
        </p>
      ) : (
        <div className="flex flex-col gap-5">
          {groups.map((group, index) => {
            const accent = eventTypeColorVar(group.eventType);
            return (
              <section key={`${group.eventType ?? "other"}-${index}`} className="flex flex-col gap-2">
                <div className="flex items-center gap-2">
                  <span className="inline-block" style={{ width: "3px", height: "0.8rem", background: accent }} />
                  <span
                    className="uppercase font-extrabold text-xs"
                    style={{ color: accent, letterSpacing: "var(--letter-spacing-badge)" }}
                  >
                    {eventTypeLabel(group.eventType)}
                  </span>
                </div>
                <div
                  className="glass-surface px-3"
                >
                  {group.alerts.map((alert) => (
                    <AlertRow key={alert.alert_key} alert={alert} onOpen={openAndMarkRead} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </main>
  );
}
