import type { NewsItem, NewsPlayerIdentity, NewsResponse } from "@/lib/api";
import { PositionBadge } from "@/components/PositionBadge";
import { eventTypeColorVar, eventTypeLabel, relativeTime } from "@/lib/alertsPresentation";
import { groupNewsByDate } from "@/lib/newsPresentation";

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
 * HTML with no native DOM event model. A real React tree doesn't have that
 * problem — the identity chip below is purely decorative (there is no
 * player-detail destination anywhere in web-next yet, same gap
 * AlertsContent.tsx's own identity display already has), so it carries no
 * click handler at all and simply sits inside the card's outer <a> with no
 * tap ambiguity to resolve. If a player destination is ever added here,
 * giving the chip its own onClick with event.stopPropagation() is the
 * normal React fix — no delegation hack needed.
 */

function NewsIdentityRow({ identity }: { identity: NewsPlayerIdentity }) {
  return (
    <div className="flex items-center gap-2">
      <PositionBadge position={identity.matched_player_position} />
      <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
        {identity.matched_player}
      </span>
      {identity.matched_player_team ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {identity.matched_player_team}
        </span>
      ) : null}
    </div>
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

function NewsCard({ item }: { item: NewsItem }) {
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

      <p className="text-sm font-bold mt-1" style={{ color: "var(--color-text-primary)" }}>
        {item.title}
      </p>

      {item.summary ? (
        <p className="text-sm mt-1" style={{ font: "var(--type-caption-emphasis)", color: "var(--color-text-secondary)" }}>
          {item.summary}
        </p>
      ) : null}
    </>
  );

  const rowStyle = { borderBottom: "var(--border-width-default) solid var(--color-border)" } as const;

  if (hasLink) {
    return (
      <a href={item.link ?? "#"} target="_blank" rel="noopener noreferrer" className="block py-3" style={rowStyle}>
        {body}
      </a>
    );
  }

  return (
    <div className="block py-3" style={rowStyle}>
      {body}
    </div>
  );
}

export function NewsContent({ data }: { data: NewsResponse }) {
  const sections = groupNewsByDate(data.items);

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Around the league
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>News</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          General NFL news — injury, role, transaction, and off-field signal only. Not filtered to your rosters.
        </p>
      </header>

      {sections.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          No news right now. Check back later for injury, role, transaction, and off-field updates.
        </p>
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
                      {group.items.map((item, itemIndex) => (
                        <NewsCard key={item.link ?? `${item.title ?? "item"}-${itemIndex}`} item={item} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </section>
          ))}
        </div>
      )}
    </main>
  );
}
