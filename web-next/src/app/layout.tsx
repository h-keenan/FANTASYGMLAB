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

export const metadata: Metadata = {
  title: BRAND_NAME,
  description: "Dynasty fantasy football GM assistant.",
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
