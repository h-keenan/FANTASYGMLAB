/**
 * The one page heading for league pages: the league name as a small kicker
 * and the page name (the same word the nav row uses) as the <h1>. Before
 * this, half the league pages made the league name the <h1> and the page
 * name a tiny kicker, so a screen reader (and the browser tab) heard
 * "Dynasty Overlords" instead of "Alerts" (UX utilization audit 2026-11-03,
 * section 5: "Page name as H1, league as kicker"). Render inside the page's
 * own <header className="flex flex-col gap-1">.
 */
export function PageTitle({ page, leagueName }: { page: string; leagueName?: string }) {
  return (
    <>
      {leagueName ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {leagueName}
        </span>
      ) : null}
      <h1 style={{ font: "var(--font-page-title)" }}>{page}</h1>
    </>
  );
}
