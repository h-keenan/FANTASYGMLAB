"use client";

import { useEffect, useMemo } from "react";
import { loadStripe, type Stripe } from "@stripe/stripe-js";
import { EmbeddedCheckout, EmbeddedCheckoutProvider } from "@stripe/react-stripe-js";

import { SheetHandle } from "@/components/SheetHandle";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";

/**
 * Zach, 2026-10-19: "We need to try to embed stripe so theres not a
 * million redirectes" — mounts Stripe's own Checkout UI in an overlay on
 * top of this app instead of redirecting the whole browser to
 * checkout.stripe.com and back. Apple Pay / Google Pay show up
 * automatically inside it (handled by the Checkout product itself, same
 * as the hosted flow — no separate Payment Element build or manual Apple
 * Pay domain registration needed). Card entry and payment processing stay
 * entirely inside Stripe's own iframe; this app still never touches card
 * details, same contract as the hosted flow it's replacing.
 *
 * `publishableKey` comes from the backend (GET /v1/billing/plans), not a
 * NEXT_PUBLIC_ build-time env var — web-next isn't deployed on Render
 * (confirmed with Zach, 2026-10-19), so there's no build pipeline to bake
 * it into; it's intentionally public/safe to ship to the client either
 * way (unlike the secret key services/mobile_api_service.py uses).
 */
const stripePromiseCache = new Map<string, Promise<Stripe | null>>();

function stripePromiseFor(publishableKey: string): Promise<Stripe | null> | null {
  if (!publishableKey) return null;
  // Memoized by key (not module scope) so a dev hot-reload or a key
  // rotation never leaves a stale Stripe.js instance half-initialized,
  // while still never re-creating it on every render for the same key.
  let cached = stripePromiseCache.get(publishableKey);
  if (!cached) {
    cached = loadStripe(publishableKey);
    stripePromiseCache.set(publishableKey, cached);
  }
  return cached;
}

export function EmbeddedCheckoutModal({
  clientSecret,
  publishableKey,
  onClose,
}: {
  clientSecret: string;
  publishableKey: string;
  onClose: () => void;
}) {
  const stripePromise = useMemo(() => stripePromiseFor(publishableKey), [publishableKey]);
  // Swipe down (touch) and Esc close it like the X. Stripe's iframe keeps
  // its own touches, so the swipe starts from the header/handle area.
  const { sheetRef, sheetStyle } = useSheetDragDismiss({ onDismiss: onClose });
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);
  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ background: "rgba(0, 0, 0, 0.6)", zIndex: 60 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        ref={sheetRef}
        className="flex flex-col gap-2 w-full max-w-lg"
        style={{
          ...sheetStyle,
          background: "var(--color-surface-raised)",
          border: "var(--border-width-default) solid var(--color-border)",
          maxHeight: "90vh",
          overflowY: "auto",
          overscrollBehavior: "contain",
        }}
      >
        <SheetHandle />
        <div className="flex items-center justify-between px-4 pt-3">
          <span className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)" }}>
            Checkout
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close checkout"
            className="text-xl leading-none"
            style={{ color: "var(--color-text-muted)" }}
          >
            ×
          </button>
        </div>
        <div className="px-1 pb-1">
          {stripePromise ? (
            <EmbeddedCheckoutProvider stripe={stripePromise} options={{ clientSecret }}>
              <EmbeddedCheckout />
            </EmbeddedCheckoutProvider>
          ) : (
            <p className="text-sm p-4" style={{ color: "var(--color-danger)" }}>
              Checkout isn&apos;t configured in this environment.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
