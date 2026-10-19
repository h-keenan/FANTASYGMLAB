"use client";

import { useState } from "react";

import type { AlertItem, AlertsResponse } from "@/lib/api";
import { api } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
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
        <div className="flex items-center gap-2 mt-1">
          <PositionBadge position={alert.matched_player_position} />
          {/* coridian_, 2026-10-19 (screenshot): "why is there no player
              card on these?" — this row had a position badge and a name
              but no photo, unlike News/Portfolio's identity chips, which
              already use this exact PlayerAvatar. The whole row is a link
              to the source article (or a mark-as-read trigger), so this
              stays a plain image, not its own nested PlayerIdentityTrigger
              — a second interactive element here would be invalid HTML
              and would fight the row's own click/keydown handler. */}
          <PlayerAvatar playerId={alert.matched_player_id} tier={alert.matched_player_tier} size={28} />
          <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
            {alert.matched_player}
          </span>
          {alert.matched_player_team ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {alert.matched_player_team}
            </span>
          ) : null}
        </div>
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
    return (
      <a
        href={alert.link ?? "#"}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => onOpen(alert)}
        className="block py-3"
        style={{ ...rowStyle, borderBottom: "var(--border-width-default) solid var(--color-border)" }}
      >
        {body}
      </a>
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
}: {
  leagueId: string;
  leagueName: string;
  data: AlertsResponse;
}) {
  const [items, setItems] = useState<AlertItem[]>(data.items);

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
      setItems((prev) => prev.map((row) => (row.alert_key === alert.alert_key ? { ...row, read: true } : row)));
      // Fire-and-forget: read state is a soft-fail nicety (the backend
      // "fails closed" on this write — see mark_league_alert_read's
      // docstring), never worth blocking or erroring the tap on.
      api.markAlertRead(leagueId, alert.alert_key).catch(() => {});
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
                  className="px-3"
                  style={{
                    background: "var(--color-surface-secondary)",
                    border: "var(--border-width-default) solid var(--color-border)",
                  }}
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
