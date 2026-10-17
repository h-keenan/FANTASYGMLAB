import Image from "next/image";

/**
 * Branded loading state — matching the web app's actual splash (coridian_,
 * 2026-10-17: "the website needs a loading screen similar to the one from
 * the streamlit version"). Every web-next page previously showed a bare
 * "Loading…" text string with no branding at all. Mirrors mobile's own
 * LoadingScreen.tsx (same brand mark, title, status line, pulse) — that
 * component's own docstring says it was built to match this exact
 * Streamlit splash, so porting mobile's version here keeps all three
 * surfaces consistent instead of inventing a fourth treatment.
 */
export function LoadingScreen({ status = "Loading…" }: { status?: string }) {
  return (
    <main className="flex-1 flex flex-col items-center justify-center gap-3" style={{ background: "var(--color-background)" }}>
      <Image
        src="/brand-mark.png"
        alt=""
        width={120}
        height={81}
        style={{ animation: "brand-mark-pulse 900ms ease-in-out infinite" }}
      />
      <h1 className="text-lg font-bold" style={{ color: "var(--color-text-primary)" }}>
        FantasyGM Lab
      </h1>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {status}
      </p>
    </main>
  );
}
