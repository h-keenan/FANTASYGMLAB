import type { Metadata } from "next";

import { BRAND_NAME } from "@/lib/brand";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";

/**
 * Tab / history / bookmark title for an in-app route segment ("Waivers ·
 * FantasyDesk"). The in-app pages are client components, so the title comes
 * from a tiny server layout per segment; the label is the same one the header
 * and nav use (PAGE_TITLE_BY_SEGMENT) so the three can never drift apart.
 * Not a root-layout title template on purpose: the public SEO pages set their
 * own full titles and must not get a second brand suffix.
 */
export function pageMetadata(segment: string): Metadata {
  const label = PAGE_TITLE_BY_SEGMENT[segment];
  return { title: label ? `${label} · ${BRAND_NAME}` : BRAND_NAME };
}
