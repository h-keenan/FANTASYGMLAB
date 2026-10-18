import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/context/AuthContext";
import { PlayerQuickViewProvider } from "@/context/PlayerQuickViewContext";
import { ValuationLensProvider } from "@/context/ValuationLensContext";
import { DesktopSidebar } from "@/components/DesktopSidebar";
import { GmOrb } from "@/components/GmOrb";
import { Header } from "@/components/Header";
import { BRAND_NAME } from "@/lib/brand";

// Launch-readiness pass, 2026-10-18: no Open Graph/Twitter Card tags meant
// a shared link (Discord, Twitter, iMessage) rendered as a bare URL with no
// title/description preview. No og:image yet — the only image asset on
// hand (icon.png, 180x180) is the wrong shape for a 1200x630 OG preview;
// stretching it would look worse than no image. Add one once a real
// 1200x630 asset exists (same blocker as the FD logomark).
const DESCRIPTION = "Dynasty fantasy football GM assistant. Real recommendations across your Trade Hub, Waivers, and Next Move — not raw data you have to interpret yourself.";

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: DESCRIPTION,
  openGraph: {
    title: BRAND_NAME,
    description: DESCRIPTION,
    siteName: BRAND_NAME,
    type: "website",
  },
  twitter: {
    card: "summary",
    title: BRAND_NAME,
    description: DESCRIPTION,
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <ValuationLensProvider>
            <PlayerQuickViewProvider>
              {/* Desktop-width persistent left nav (coridian_, 2026-10-17:
                  "desktop side menu") — fixed-position, so it sits outside
                  this flex flow; the wrapper below pushes the real content
                  clear of it via md:pl-60 instead. */}
              <Suspense fallback={null}>
                <DesktopSidebar />
              </Suspense>
              <div className="flex flex-col flex-1 md:pl-60">
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
              </div>
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
