import type { ReactNode } from "react";

/**
 * Route transition (docs/audits/2026-11-motion-audit.md, candidate 2): a template
 * remounts on every navigation, so the new page fades in instead of hard-cutting.
 * Opacity only (a transform here would become the containing block of every
 * `position: fixed` chrome piece), `backwards` fill so nothing is left applied
 * after the 240ms (`--motion-base`) fade. The wrapper keeps the flex chain the
 * pages rely on (`flex flex-col flex-auto` under AppContentShell). Off under
 * prefers-reduced-motion (see `.route-fade` in globals.css).
 */
export default function Template({ children }: { children: ReactNode }) {
  return <div className="route-fade flex flex-col flex-auto">{children}</div>;
}
