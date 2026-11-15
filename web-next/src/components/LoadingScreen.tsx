import type { PageTabFamilyKey } from "@/lib/pageFamilies";
import { SkeletonPage, type SkeletonLayout } from "@/components/Skeleton";

/**
 * A route's loading state while auth or its first fetch resolves: a content-shaped skeleton of the page that is about
 * to appear (header, optional tab strip, then the layout for its family), never a splash or a "Loading…" line.
 * `label` is the page's name and becomes the one screen-reader status ("Loading Players"). Mobile twin:
 * mobile/src/screens/LoadingScreen.tsx. The pieces live in components/Skeleton.tsx (docs/ui-patterns.md, "Loading identity").
 */
export function LoadingScreen({ label = "page", layout = "dashboard", family }: { label?: string; layout?: SkeletonLayout; family?: PageTabFamilyKey }) {
  return <SkeletonPage label={label} layout={layout} family={family} />;
}
