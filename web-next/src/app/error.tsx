"use client";

import Image from "next/image";
import { useEffect } from "react";

import { trackClientError } from "@/lib/analytics";
import { BRAND_NAME } from "@/lib/brand";
import { Button } from "@/components/Button";

/**
 * Launch-readiness pass, 2026-10-18: without this, an uncaught render
 * error anywhere in the app fell through to Next.js's default unstyled
 * error screen with zero server-side trace of what broke — the same
 * invisible-failure gap found and fixed in three backend services earlier
 * this session (services/stripe_webhook_service.py, revenuecat_webhook_
 * service.py) and in page.tsx's saved-leagues fetch. console.error here is
 * the same minimum fix: makes the real error visible in whoever's browser
 * hits it, instead of a dead end with no trace anywhere.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled app error", error);
    // Team-visible signal: error constructor name + sanitized route only.
    trackClientError("application_error", error);
  }, [error]);

  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center" style={{ background: "var(--color-bg)" }}>
      <Image src="/brand-mark.png" alt="" width={100} height={100} className="brand-mark-icon" />
      <h1 className="text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
        {BRAND_NAME}
      </h1>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Something went wrong. It&apos;s been logged.
      </p>
      <Button
        type="button"
        onClick={reset}
        style={{ alignSelf: "auto" }}
      >
        Try again
      </Button>
    </main>
  );
}
