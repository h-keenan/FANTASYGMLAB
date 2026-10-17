import type { Metadata } from "next";
import { Suspense, type ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/context/AuthContext";
import { PlayerQuickViewProvider } from "@/context/PlayerQuickViewContext";
import { GmOrb } from "@/components/GmOrb";
import { Header } from "@/components/Header";

export const metadata: Metadata = {
  title: "FantasyGM Lab",
  description: "Dynasty fantasy football GM assistant.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <PlayerQuickViewProvider>
            <Header />
            {children}
            {/* useSearchParams (via GmOrb's leagueName lookup) opts a page
                into client-side rendering unless wrapped in Suspense — this
                app's static pages (/, /news, /portfolio, ...) would
                otherwise fail to prerender. */}
            <Suspense fallback={null}>
              <GmOrb />
            </Suspense>
          </PlayerQuickViewProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
