import Image from "next/image";
import Link from "next/link";

import { BRAND_NAME } from "@/lib/brand";

/**
 * Launch-readiness pass, 2026-10-18: Next.js's default 404 is a bare,
 * unstyled white page — jarring against the app's dark theme everywhere
 * else. Mirrors LoadingScreen's own branded-splash treatment (brand mark,
 * title, status line) rather than inventing a new one.
 */
export default function NotFound() {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center" style={{ background: "var(--color-bg)" }}>
      <Image src="/brand-mark.png" alt="" width={100} height={100} className="brand-mark-icon" />
      <h1 className="text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
        {BRAND_NAME}
      </h1>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        That page doesn&apos;t exist.
      </p>
      <Link
        href="/"
        className="px-4 py-2 text-sm font-bold"
        style={{
          background: "var(--color-accent-strong)",
          color: "var(--color-on-accent)",
          fontWeight: "var(--font-weight-button)",
        }}
      >
        Back to FantasyDesk
      </Link>
    </main>
  );
}
