import type { Metadata } from "next";
import { Inter_Tight } from "next/font/google";
import { Suspense, type ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/context/AuthContext";
import { PlayerQuickViewProvider } from "@/context/PlayerQuickViewContext";
import { ValuationLensProvider } from "@/context/ValuationLensContext";
import { GmOrb } from "@/components/GmOrb";
import { Header } from "@/components/Header";
import { BRAND_NAME } from "@/lib/brand";

// FantasyDesk brand sheet (2026-10-17) — next/font self-hosts the font
// (no runtime request to Google Fonts, no layout shift) and exposes it as
// a CSS variable that --font-family-sans (globals.css) reads, same
// "token, not a literal" pattern as every other value in that file.
const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-inter-tight",
  display: "swap",
});

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: "Dynasty fantasy football GM assistant.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`h-full antialiased ${interTight.variable}`}>
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <ValuationLensProvider>
            <PlayerQuickViewProvider>
              {/* Header handles its own internal Suspense boundary now
                  (just around its league-aware sub-piece), so the brand
                  mark/wordmark render synchronously on every page instead
                  of waiting on hydration — a real new-user-UX-audit finding,
                  2026-10-17 (the header was invisible in the server-rendered
                  HTML of every single page). GmOrb still needs its own
                  Suspense wrap for useSearchParams — this app's static pages
                  (/, /news, /portfolio, ...) would otherwise fail to
                  prerender — but a floating button popping in a beat after
                  first paint is far less noticeable than a missing header. */}
              <Header />
              {children}
              <Suspense fallback={null}>
                <GmOrb />
              </Suspense>
            </PlayerQuickViewProvider>
          </ValuationLensProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
