"use client";

import { loadStripe } from "@stripe/stripe-js";
import { EmbeddedCheckout, EmbeddedCheckoutProvider } from "@stripe/react-stripe-js";

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
 * The publishable key is intentionally public (safe to ship in the client
 * bundle, unlike the secret key services/mobile_api_service.py uses) --
 * loadStripe() is called once at module scope, matching Stripe's own
 * guidance, not inside the component (which would re-create the Stripe.js
 * instance on every render).
 */
const stripePromise = process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY
  ? loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY)
  : null;

export function EmbeddedCheckoutModal({ clientSecret, onClose }: { clientSecret: string; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ background: "rgba(0, 0, 0, 0.6)", zIndex: 60 }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className="flex flex-col gap-2 w-full max-w-lg"
        style={{
          background: "var(--color-surface-raised)",
          border: "var(--border-width-default) solid var(--color-border)",
          maxHeight: "90vh",
          overflowY: "auto",
        }}
      >
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
