import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  // Launch-readiness pass, 2026-10-18: the checked-in Caddyfile only sets
  // X-Content-Type-Options/Referrer-Policy on the Streamlit route block,
  // not confirmed for web-next, and that file's own header comment says
  // production's real Caddy config is generated server-side — not
  // something to edit blind. Setting a baseline here instead applies
  // regardless of what the reverse proxy does. No Content-Security-Policy
  // yet — getting one wrong silently breaks functionality (blocked
  // scripts/styles/images), and that needs a real browser to audit against
  // every external resource this app actually loads, not a guess.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
  // This app is a fully client-auth-gated SPA (every route reads the
  // Supabase session at runtime) — Next 16's Cache Components/PPR default
  // wants routes to be statically prerenderable up to a Suspense boundary,
  // which doesn't fit a page whose entire content depends on "am I signed
  // in," so every route is plain dynamic rendering instead.
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
