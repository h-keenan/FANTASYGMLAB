"use client";

import { useEffect } from "react";

import { trackTryLink } from "@/lib/analytics";
import type { TryTopic } from "@/lib/tryLinks";

/** Counts one demo view per topic per session (feature_use feature=try_link, demo=true: never engagement). */
export function TryTracker({ topic }: { topic: TryTopic }) {
  useEffect(() => {
    trackTryLink("viewed", topic);
  }, [topic]);
  return null;
}
