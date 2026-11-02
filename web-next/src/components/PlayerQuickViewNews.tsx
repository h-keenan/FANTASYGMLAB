import Link from "next/link";

import type { NewsItem, PlayerAvailability } from "@/lib/api";
import { SkeletonBlock } from "@/components/Skeleton";
import {
  availabilityDetailParts,
  newsAgeLabel,
  newsPageHref,
} from "@/lib/playerAvailabilityPresentation";

function SourceLine({ item }: { item: NewsItem }) {
  const parts = [item.source, newsAgeLabel(item.published_ts)].filter(Boolean);
  return parts.length > 0 ? <span className="pqv-news-meta">{parts.join(" · ")}</span> : null;
}

function Headline({ item }: { item: NewsItem }) {
  const title = item.title || "Untitled report";
  return item.link ? (
    <a className="pqv-news-title" href={item.link} target="_blank" rel="noopener noreferrer">
      {title}
    </a>
  ) : (
    <span className="pqv-news-title">{title}</span>
  );
}

/** Non-healthy status: clean label, body part, honest return note, and
 * (when the news pool has one) the latest injury headline. The headline is
 * labelled "Latest injury report", never as the cause. */
export function AvailabilityBlock({
  availability,
  injuryItem,
  newsLoading,
}: {
  availability: PlayerAvailability;
  injuryItem: NewsItem | null;
  newsLoading: boolean;
}) {
  const detail = availabilityDetailParts(availability);
  return (
    <section
      className={`pqv-availability pqv-availability--${availability.unavailable ? "danger" : "warning"}`}
      aria-label="Availability"
      data-testid="pqv-availability"
    >
      <p className="pqv-availability-label">{availability.label}</p>
      <p className="pqv-availability-detail">{detail.join(" · ")}</p>
      {availability.report ? <p className="pqv-availability-detail">{availability.report}</p> : null}
      {injuryItem ? (
        <div className="pqv-news-item" data-testid="pqv-injury-news">
          <span className="pqv-news-kicker">Latest injury report</span>
          <Headline item={injuryItem} />
          <SourceLine item={injuryItem} />
        </div>
      ) : newsLoading ? (
        <div aria-hidden="true">
          <SkeletonBlock width="80%" height="0.7rem" />
        </div>
      ) : null}
    </section>
  );
}

/** Up to 3 recent items. `items === null` while loading (skeleton); a failed
 * load renders nothing; a real empty result is one muted line. */
export function LatestNewsSection({
  items,
  loading,
  playerId,
  name,
  hideItem,
}: {
  hideItem?: NewsItem | null;
  items: NewsItem[] | null;
  loading: boolean;
  playerId: string;
  name: string;
}) {
  if (loading) {
    return (
      <section className="pqv-news" aria-hidden="true" data-testid="pqv-news-skeleton">
        <SkeletonBlock width="30%" height="0.6rem" />
        <SkeletonBlock height="0.7rem" />
        <SkeletonBlock width="70%" height="0.7rem" />
      </section>
    );
  }
  if (items === null) return null;
  // The injury headline already shows in the availability block.
  const rest = hideItem ? items.filter((item) => !(item.link === hideItem.link && item.title === hideItem.title)) : items;
  if (rest.length === 0 && hideItem && items.length > 0) return null;
  if (rest.length === 0) {
    return (
      <section className="pqv-news" aria-label="Latest news">
        <h3 className="pqv-news-heading">Latest news</h3>
        <p className="pqv-status-text">No recent news</p>
      </section>
    );
  }
  return (
    <section className="pqv-news" aria-label="Latest news" data-testid="pqv-news">
      <h3 className="pqv-news-heading">Latest news</h3>
      {rest.slice(0, 3).map((item, index) => (
        <div className="pqv-news-item" key={`${item.link ?? item.title}-${index}`}>
          <Headline item={item} />
          <SourceLine item={item} />
          {item.summary ? <p className="pqv-news-summary">{item.summary}</p> : null}
        </div>
      ))}
      <Link className="pqv-action-link" href={newsPageHref(playerId, name)}>
        See all news
      </Link>
    </section>
  );
}
