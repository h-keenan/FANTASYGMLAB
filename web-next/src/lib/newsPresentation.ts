import type { NewsItem } from "./api";

/**
 * Ports modules/general_news_ui.py's day-then-event-type grouping for the
 * general News feed (Revision 10) — mirrors mobile's NewsScreen.tsx
 * (groupByDate / groupByEventType) exactly so all three surfaces read the
 * same way.
 *
 * eventTypeLabel / eventTypeColorVar / relativeTime are NOT redeclared
 * here: AlertsContent's adjacent roster-scoped feed already defines them in
 * alertsPresentation.ts against the identical event_type taxonomy and
 * relative-time contract (both feeds read event_type/published_ts off the
 * same NewsItem base — see api.ts), so News imports those three directly
 * instead of a second copy. Only the News-specific date-bucket grouping
 * (a dimension Alerts' feed doesn't have) lives here.
 */

const DATE_BUCKET_ORDER = ["Today", "Yesterday", "Earlier"] as const;
export type NewsDateBucket = (typeof DATE_BUCKET_ORDER)[number];

export function newsDateBucket(publishedTs: number | null, nowMs: number = Date.now()): NewsDateBucket {
  if (!publishedTs) return "Earlier";
  const now = new Date(nowMs);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  const published = new Date(publishedTs * 1000);
  if (published >= startOfToday) return "Today";
  if (published >= startOfYesterday) return "Yesterday";
  return "Earlier";
}

export interface NewsEventGroup {
  eventType: string | null;
  items: NewsItem[];
}

export interface NewsDateSection {
  bucket: NewsDateBucket;
  groups: NewsEventGroup[];
}

/**
 * Clusters consecutive items sharing one event_type into one group within
 * a date bucket — chronological order is preserved, only adjacent runs of
 * the same type merge (same contract as alertsPresentation's
 * groupAlertsByType, just scoped to the items of one date bucket here).
 */
function groupConsecutiveByEventType(items: NewsItem[]): NewsEventGroup[] {
  const groups: NewsEventGroup[] = [];
  for (const item of items) {
    const last = groups[groups.length - 1];
    if (last && last.eventType === item.event_type) {
      last.items.push(item);
    } else {
      groups.push({ eventType: item.event_type, items: [item] });
    }
  }
  return groups;
}

export function groupNewsByDate(items: NewsItem[], nowMs: number = Date.now()): NewsDateSection[] {
  const buckets = new Map<NewsDateBucket, NewsItem[]>();
  for (const item of items) {
    const bucket = newsDateBucket(item.published_ts, nowMs);
    const existing = buckets.get(bucket);
    if (existing) existing.push(item);
    else buckets.set(bucket, [item]);
  }
  return DATE_BUCKET_ORDER.filter((bucket) => buckets.has(bucket)).map((bucket) => ({
    bucket,
    groups: groupConsecutiveByEventType(buckets.get(bucket) ?? []),
  }));
}

export interface NewsDaySection {
  /** "Today", "Yesterday", or a calendar date such as "Tue, Oct 28". */
  label: string;
  items: NewsItem[];
}

/** Per-calendar-day label for one story. Undated stories fall to "Earlier". */
export function newsDayLabel(publishedTs: number | null, nowMs: number = Date.now()): string {
  if (!publishedTs) return "Earlier";
  const now = new Date(nowMs);
  const published = new Date(publishedTs * 1000);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  if (published >= startOfToday) return "Today";
  if (published >= startOfYesterday) return "Yesterday";
  return published.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    ...(published.getFullYear() !== now.getFullYear() ? { year: "numeric" } : {}),
  });
}

/** Groups a newest-first list by calendar day, preserving order. Appending a
 * later page keeps working because a day that spans pages merges. */
export function groupNewsByDay(items: NewsItem[], nowMs: number = Date.now()): NewsDaySection[] {
  const sections: NewsDaySection[] = [];
  for (const item of items) {
    const label = newsDayLabel(item.published_ts, nowMs);
    const last = sections[sections.length - 1];
    if (last && last.label === label) last.items.push(item);
    else sections.push({ label, items: [item] });
  }
  return sections;
}

/** Concatenates a further page onto a list without repeating a story. */
export function appendNewsPage(existing: NewsItem[], next: NewsItem[]): NewsItem[] {
  const seen = new Set(existing.map((item) => `${item.link ?? ""}|${item.title ?? ""}`));
  return [...existing, ...next.filter((item) => !seen.has(`${item.link ?? ""}|${item.title ?? ""}`))];
}
