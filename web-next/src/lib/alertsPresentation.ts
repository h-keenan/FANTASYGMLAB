import type { AlertItem, RosterRelationship } from "./api";
import { notReadyReasonMessage } from "./notReadyMessages";

export function alertsReasonMessage(reason: string): string | null {
  return notReadyReasonMessage(reason, {
    linkAccount: "Link your Sleeper username on the web app first — Alerts needs to know which players are yours.",
    emptyRoster: "Your roster in this league is empty.",
  });
}

// Event-type taxonomy straight off modules/news_signal.py's EVENT_INJURY/
// EVENT_ROLE/EVENT_TRANSACTION/EVENT_OFF_FIELD string constants (the exact
// values GET .../alerts' `event_type` field carries) — same four buckets
// mobile's AlertsScreen.tsx groups by (EVENT_BADGE_ICONS/EVENT_TYPE_LABELS),
// kept here as the single shared source instead of a second copy.
export const EVENT_TYPE_LABELS: Record<string, string> = {
  "injury/status": "Injury / Status",
  transaction: "Transaction",
  "role/depth chart": "Role / Depth Chart",
  "off-field/drama": "Off-Field",
};

export function eventTypeLabel(eventType: string | null): string {
  if (!eventType) return "Update";
  return (
    EVENT_TYPE_LABELS[eventType] ??
    eventType
      .split("/")
      .filter(Boolean)
      .map((part) => part.replace(/\b\w/g, (c) => c.toUpperCase()))
      .join(" / ")
  );
}

// Same red = injury/risk, cyan = transaction, green = role upside, slate =
// everything else semantic mapping mobile's eventBadgeColors uses, and the
// identical accent mobile/web Streamlit's own type-color accents
// (modules/alerts_activity_styles.py's `.dg-alerts-row--injury/--
// transaction/--role/--other`) already carry — reusing the same four
// existing tokens here, not inventing a fifth.
export function eventTypeColorVar(eventType: string | null): string {
  if (eventType === "injury/status") return "var(--color-danger)";
  if (eventType === "transaction") return "var(--color-accent)";
  if (eventType === "role/depth chart") return "var(--color-success)";
  return "var(--color-text-secondary)";
}

export const ROSTER_RELATIONSHIP_LABEL: Record<Exclude<RosterRelationship, null>, string> = {
  starter: "Starter",
  bench: "Bench",
  taxi: "Taxi",
  ir: "IR",
};

export function rosterRelationshipColorVar(relationship: RosterRelationship): string {
  if (relationship === "starter") return "var(--color-success)";
  if (relationship === "ir") return "var(--color-danger)";
  if (relationship === "taxi") return "var(--color-accent)";
  return "var(--color-text-secondary)";
}

export function relativeTime(publishedTs: number | null): string {
  if (!publishedTs) return "";
  const seconds = Date.now() / 1000 - publishedTs;
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export interface AlertGroup {
  eventType: string | null;
  alerts: AlertItem[];
}

/**
 * Clusters consecutive alerts that share the same event_type into one
 * group, mirroring mobile's groupAlertsByType (AlertsScreen.tsx) exactly:
 * keeps the feed's existing relevance order intact (only adjacent runs
 * merge) instead of re-sorting the whole list by type.
 */
export function groupAlertsByType(items: AlertItem[]): AlertGroup[] {
  const groups: AlertGroup[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.eventType === item.event_type) {
      last.alerts.push(item);
    } else {
      groups.push({ eventType: item.event_type, alerts: [item] });
    }
  }
  return groups;
}
