import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

import { AuthProvider } from "@/context/AuthContext";
import { PlayerQuickViewProvider } from "@/context/PlayerQuickViewContext";
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
          </PlayerQuickViewProvider>
        </AuthProvider>
      </body>
    </html>
  );
}
