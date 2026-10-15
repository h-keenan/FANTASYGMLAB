import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
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
