import type { NewsItem } from './api';

/** Pure helpers for the full player profile's News tab. Mirrors
 * web-next/src/lib/newsPresentation.ts (groupNewsByDay / appendNewsPage). */

export const PLAYER_NEWS_PAGE_SIZE = 10;

export interface NewsDaySection {
  /** "Today", "Yesterday", or a calendar date such as "Tue, Oct 28". */
  label: string;
  items: NewsItem[];
}

export function newsDayLabel(publishedTs: number | null, nowMs: number = Date.now()): string {
  if (!publishedTs) return 'Earlier';
  const now = new Date(nowMs);
  const published = new Date(publishedTs * 1000);
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startOfYesterday = new Date(startOfToday);
  startOfYesterday.setDate(startOfYesterday.getDate() - 1);
  if (published >= startOfToday) return 'Today';
  if (published >= startOfYesterday) return 'Yesterday';
  return published.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    ...(published.getFullYear() !== now.getFullYear() ? { year: 'numeric' as const } : {}),
  });
}

/** Groups a newest-first list by calendar day, preserving order. */
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

const storyKey = (item: NewsItem) => `${item.link ?? ''}|${item.title ?? ''}`;

/** Concatenates pages without repeating a story. */
export function flattenNewsPages(pages: { items: NewsItem[] }[]): NewsItem[] {
  const seen = new Set<string>();
  const out: NewsItem[] = [];
  for (const page of pages) {
    for (const item of page.items) {
      const key = storyKey(item);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(item);
    }
  }
  return out;
}

export function sameStory(a: NewsItem | null | undefined, b: NewsItem | null | undefined): boolean {
  return Boolean(a && b && a.link === b.link && a.title === b.title);
}

/** "Also reported by ESPN, RotoWire", or '' when the story has no duplicates. */
export function alsoReportedLine(item: NewsItem): string {
  const sources = (item.also_reported_by ?? []).map((other) => other.source).filter(Boolean);
  return sources.length > 0 ? `Also reported by ${sources.join(', ')}` : '';
}
