"use client";

import type { ComponentProps } from "react";

import { ButtonLink } from "@/components/Button";
import { trackFeatureUse } from "@/lib/analytics";

/**
 * A ButtonLink that counts the click as `seo_cta_clicked` with a fixed snake_case `source_surface`
 * (which page family) and `destination` (which demo or tool). No ids, names or free text. The
 * href itself carries utm_medium=site_cta tags (lib/seasonalLanding.withUtm).
 */
export function TrackedCtaLink({
  surface,
  destination,
  onClick,
  ...rest
}: ComponentProps<typeof ButtonLink> & { surface: string; destination: string }) {
  return (
    <ButtonLink
      {...rest}
      onClick={(event) => {
        trackFeatureUse("seo_cta_clicked", { dedupe: false, props: { source_surface: surface, destination } });
        onClick?.(event);
      }}
    />
  );
}
