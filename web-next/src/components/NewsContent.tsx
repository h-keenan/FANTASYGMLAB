import { EmptyState } from "@/components/EmptyState";
import { PageTitle } from "@/components/PageTitle";
import type { NewsItem, NewsPlayerIdentity, NewsResponse } from "@/lib/api";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { eventTypeColorVar, eventTypeLabel, relativeTime } from "@/lib/alertsPresentation";
import { groupNewsByDate } from "@/lib/newsPresentation";
import { LeagueLinkStep } from "@/components/LeagueLinkStep";
import { AccentCard } from "@/components/AccentCard";
import { EventTypePill } from "@/components/EventTypeGlyph";

/**
 * Ports modules/general_news_ui.py / mobile's NewsScreen.tsx for
 * Revision 10 — the general, non-roster-scoped NFL feed (injury/role/
 * transaction/off-field signal only), grouped by day then clustered by
 * consecutive event type. Reads GET /v1/news, extended this revision to
 * also carry single/two-player identity (see api.ts's NewsItem docstring)
 * so this page can show the same identity chips the Streamlit page
 * recently gained (PR #1040/#1042/#1062), reusing the shared PositionBadge
 * component rather than modules.compact_fantasy_assets' Streamlit chip
 * markup.
 *
 * Deliberately a separate surface from AlertsContent.tsx's roster-scoped
 * feed (same as the Streamlit/mobile split) and from Dashboard's own
 * 3-tile news digest — neither of those changes here.
 *
 * Navigation note: Streamlit needed modules.interaction_contract.
 * TAP_DELEGATION_JS to resolve "tap the chip vs. tap the article link"
 * because its whole card (including the chip) is one block of injected
 * HTML with no native DOM event model. The identity chip (NewsIdentityRow)
 * opens the shared PlayerQuickView modal via PlayerIdentityTrigger, which
 * is a real <button> — that can't nest inside the card's own wrapping <a>
 * (hasLink case, invalid HTML), so NewsCard below uses the standard
 * "stretched link" layout instead: the card's own <a>/<div> is an
 * absolutely-positioned full-cover sibling with no z-index, and the chip
 * gets `relative z-10` so it paints above that overlay and wins its own
 * taps (PlayerIdentityTrigger's own stopPropagation keeps the card's click
 * from also firing).
 */

function NewsIdentityRow({ identity }: { identity: NewsPlayerIdentity }) {
  const row = (
    <>
      <PlayerAvatar playerId={identity.matched_player_id} size={36} />
      <span className="flex flex-col min-w-0">
        <span className="text-sm font-bold break-words" style={{ color: "var(--color-text-primary)" }}>
          {identity.matched_player}
        </span>
        <span className="flex items-center gap-1.5">
          <PositionBadge position={identity.matched_player_position} />
          {identity.matched_player_team ? (
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {identity.matched_player_team}
            </span>
          ) : null}
        </span>
      </span>
    </>
  );
  if (!identity.matched_player_id) {
    return <div className="flex items-center gap-2">{row}</div>;
  }
  return (
    <PlayerIdentityTrigger
      identity={{
        player_id: identity.matched_player_id,
        name: identity.matched_player,
        position: identity.matched_player_position,
        team: identity.matched_player_team,
        sourceLabel: "News",
      }}
      className="flex items-center gap-2 relative z-10 tap-link"
    >
      {row}
    </PlayerIdentityTrigger>
  );
}

function NewsIdentity({ item }: { item: NewsItem }) {
  if (item.matched_players && item.matched_players.length === 2) {
    return (
      <div className="flex flex-col gap-1 mt-1">
        {item.matched_players.map((identity, index) => (
          <NewsIdentityRow key={identity.matched_player_id ?? index} identity={identity} />
        ))}
      </div>
    );
  }
  if (item.matched_player) {
    return (
      <div className="mt-1">
        <NewsIdentityRow
          identity={{
            matched_player: item.matched_player,
            matched_player_id: item.matched_player_id ?? null,
            matched_player_position: item.matched_player_position,
            matched_player_team: item.matched_player_team,
          }}
        />
      </div>
    );
  }
  return null;
}

/** Exported for the full profile's News tab (one card for every news list). */
export function NewsCard({
  item,
  showEventTag = false,
  hero = false,
}: {
  item: NewsItem;
  showEventTag?: boolean;
  /** The first story of a bucket: a raised accent card with a larger headline. */
  hero?: boolean;
}) {
  const time = relativeTime(item.published_ts);
  const hasLink = Boolean(item.link);

  const body = (
    <>
      <div className="flex items-center gap-2 flex-wrap">
        {time ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {time}
          </span>
        ) : null}
        {item.source ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {item.source}
          </span>
        ) : null}
        {showEventTag && item.event_type ? (
          <EventTypePill
            eventType={item.event_type}
            label={eventTypeLabel(item.event_type)}
            color={eventTypeColorVar(item.event_type)}
            testId="news-event-tag"
          />
        ) : null}
        {item.speculative ? (
          <span className="text-xs font-bold" style={{ color: "var(--color-warning)" }}>
            Unconfirmed / speculative
          </span>
        ) : null}
        <span className="flex-1" />
        {hasLink ? (
          <span style={{ color: "var(--color-text-muted)" }} aria-hidden="true">
            →
          </span>
        ) : null}
      </div>

      <NewsIdentity item={item} />

      <p className={`${hero ? "text-base" : "text-sm"} font-bold mt-1`} style={{ color: "var(--color-text-primary)" }}>
        {item.title}
      </p>

      {item.also_reported_by && item.also_reported_by.length > 0 ? (
        <p className="text-xs mt-1" style={{ color: "var(--color-text-muted)" }} data-testid="news-also-reported">
          Also reported by {item.also_reported_by.map((other) => other.source).filter(Boolean).join(", ")}
        </p>
      ) : null}

      {item.summary ? (
        <p className="text-sm mt-1" style={{ font: "var(--type-caption-emphasis)", color: "var(--color-text-secondary)" }}>
          {item.summary}
        </p>
      ) : null}
    </>
  );

  const rowStyle = { borderBottom: "var(--border-width-default) solid var(--color-border)" } as const;

  const link = hasLink ? (
    <a
      href={item.link ?? "#"}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={item.title ?? "Open article"}
      className="absolute inset-0"
    />
  ) : null;

  if (hero) {
    return (
      <AccentCard accent={eventTypeColorVar(item.event_type)} className="relative">
        {body}
        {link}
      </AccentCard>
    );
  }

  if (hasLink) {
    return (
      <div className="relative block py-3" style={rowStyle}>
        {body}
        {link}
      </div>
    );
  }

  return (
    <div className="block py-3" style={rowStyle}>
      {body}
    </div>
  );
}

export function NewsContent({ data, playerName }: { data: NewsResponse; playerName?: string | null }) {
  const sections = groupNewsByDate(data.items);

  return (
    <main className="page-shell">
      <header className="flex flex-col gap-1">
        <PageTitle page={playerName ? `News: ${playerName}` : "News"} />
        {playerName ? (
          <p className="text-sm font-bold">News: {playerName}</p>
        ) : null}
        {playerName ? (
          <a className="text-sm underline" href="/news">
            All news
          </a>
        ) : null}
      </header>

      {sections.length === 0 ? (
        <EmptyState
          title={playerName ? "No recent news for this player." : data.status?.state === "warming_up" ? "News is warming up." : "No news right now."}
          subtitle={data.status?.message || "Check back later for injury, role, transaction, and off-field updates."}
        />
      ) : (
        <div className="flex flex-col gap-6">
          {sections.map((section) => (
            <section key={section.bucket} className="flex flex-col gap-4">
              <h2
                className="uppercase font-extrabold text-xs"
                style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
              >
                {section.bucket}
              </h2>
              {section.groups.map((group, index) => {
                const accent = eventTypeColorVar(group.eventType);
                return (
                  <div key={`${group.eventType ?? "other"}-${index}`} className="flex flex-col gap-2">
                    <div className="flex items-center gap-2">
                      <EventTypePill eventType={group.eventType} label={eventTypeLabel(group.eventType)} color={accent} />
                    </div>
                    {index === 0 ? <NewsCard item={group.items[0]} hero /> : null}
                    {group.items.length > (index === 0 ? 1 : 0) ? (
                      <div className="glass-surface px-3">
                        {group.items.slice(index === 0 ? 1 : 0).map((item, itemIndex) => (
                          <NewsCard key={item.link ?? `${item.title ?? "item"}-${itemIndex}`} item={item} />
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </section>
          ))}
        </div>
      )}
      {playerName ? null : (
        <div className="flex flex-col gap-2" data-testid="news-next-step">
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            This is the league-wide feed. News on the players you own is in Alerts.
          </p>
          <div>
            <LeagueLinkStep step="alerts" label="See news on your players" pickLabel="Pick a league for your alerts" />
          </div>
        </div>
      )}
    </main>
  );
}
