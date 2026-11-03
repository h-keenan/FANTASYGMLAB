import Link from "next/link";

import { NavDestinationGlyph } from "@/components/NavDestinationGlyph";
import { NavProMarker } from "@/components/NavProMarker";
import { SectionHeading } from "@/components/SectionHeading";
import { FEATURE_GROUPS, FEATURE_ITEMS, featureHref, type FeatureLeague } from "@/lib/featureCatalog";

/**
 * "What FantasyDesk can do": every feature, grouped by what the user wants to
 * do, one line each, opening for their current league. The list lives in
 * lib/featureCatalog.ts. `isPro` follows the nav rule: the Pro marker shows
 * only when the person is known not to be on Pro (`false`).
 */
export function FeaturesContent({ league, isPro }: { league: FeatureLeague | null; isPro: boolean | null }) {
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-6 max-w-2xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <h1 style={{ font: "var(--font-page-title)" }}>What FantasyDesk can do</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="features-subtitle">
          {league ? (
            <>
              Tap anything to open it for <strong>{league.name}</strong>.
            </>
          ) : (
            <>Pick a league on Home first. League tools open for the league you choose.</>
          )}
        </p>
      </header>

      {FEATURE_GROUPS.map((group) => {
        const items = FEATURE_ITEMS.filter((item) => item.group === group.id);
        return (
          <section key={group.id} className="flex flex-col gap-2" aria-labelledby={`features-${group.id}`}>
            <SectionHeading id={`features-${group.id}`}>{group.title}</SectionHeading>
            <ul className="glass-surface flex flex-col" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {items.map((item, index) => (
                <li key={item.id} style={index > 0 ? { borderTop: "1px solid var(--color-border)" } : undefined}>
                  <Link
                    href={featureHref(item, league)}
                    className="flex items-center gap-3 px-3 py-2 min-h-[var(--touch-target-min)]"
                    data-testid={`feature-${item.id}`}
                  >
                    <span className="shrink-0" style={{ color: item.color }}>
                      <NavDestinationGlyph name={item.glyph} size={20} />
                    </span>
                    <span className="min-w-0 flex-1 flex flex-col">
                      <span className="flex items-center gap-2 text-sm font-bold">
                        {item.name}
                        {item.pro && isPro === false ? <NavProMarker /> : null}
                      </span>
                      <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                        {item.line}
                      </span>
                      {item.extra && isPro === false ? (
                        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                          {item.extra}
                        </span>
                      ) : null}
                    </span>
                    <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                      →
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </main>
  );
}
