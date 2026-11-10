"use client";

import { useEffect } from "react";

import { reportError } from "@/lib/errorReporter";

/**
 * Last-resort boundary: catches errors thrown in the root layout itself
 * (where app/error.tsx cannot). It replaces the whole document, so it is
 * self-contained: no providers, no global CSS dependency, no raw error text.
 */
export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error("Unhandled root error", error);
    reportError(error, { source: "app/global-error.tsx", digest: error.digest });
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 16,
          padding: 24,
          textAlign: "center",
          fontFamily: "system-ui, -apple-system, sans-serif",
          background: "#0b0d10",
          color: "#f7f8fa",
        }}
      >
        <h1 style={{ fontSize: 20, margin: 0 }}>Something went wrong</h1>
        <p style={{ margin: 0, color: "#a8adb7", maxWidth: 360 }}>
          FantasyDesk hit an unexpected problem. It has been logged. Try again, or reload the page.
        </p>
        {error?.digest ? <p style={{ margin: 0, fontSize: 12, color: "#777879" }}>Reference: {error.digest}</p> : null}
        <button
          type="button"
          onClick={reset}
          style={{ minHeight: 44, padding: "0 24px", borderRadius: 12, border: 0, background: "#67e8f9", color: "#0b1220", fontWeight: 700, fontSize: 16, cursor: "pointer" }}
        >
          Try again
        </button>
      </body>
    </html>
  );
}
