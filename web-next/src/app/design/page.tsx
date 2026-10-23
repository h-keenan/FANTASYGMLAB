import type { Metadata } from "next";

import { DesignSystemContent } from "./DesignSystemContent";

// Hidden owner-review page: not linked in nav, not in sitemap.ts, disallowed
// in robots.ts, and noindex here so a direct hit never lands in search.
export const metadata: Metadata = {
  title: "Design system reference",
  robots: { index: false, follow: false, nocache: true },
};

export default function DesignPage() {
  return <DesignSystemContent />;
}
