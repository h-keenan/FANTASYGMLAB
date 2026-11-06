/**
 * The one page heading for league pages. The persistent top bar
 * (Header.tsx HeaderPageTitle) already shows the page name and the league
 * switcher already shows the league, so repeating a big visible title plus a
 * league-name line pushed the real content ~90px down the phone viewport
 * (coridian_, 2026-11-06). The <h1> stays in the DOM, visually hidden, so
 * screen readers and the document outline still hear the page name; the
 * league name is deliberately not repeated (it is in the switcher).
 * Render inside the page's own <header>; a header with no other visible
 * child takes no space (see `.page-header-empty` in globals.css).
 */
export function PageTitle({ page }: { page: string; leagueName?: string }) {
  return <h1 className="sr-only">{page}</h1>;
}
