import type { Metadata } from "next";

import { SampleLeagueContent } from "@/components/SampleLeagueContent";

// Fictional demo data only; keep it out of search.
export const metadata: Metadata = {
  title: "Sample league",
  robots: { index: false, follow: false, nocache: true },
};

export default function SampleLeaguePage() {
  return <SampleLeagueContent />;
}
