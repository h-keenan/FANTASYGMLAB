/**
 * One Season Wrapped card as a share image (Satori only, like seasonReviewCard.tsx): the card's eyebrow and title, its big number
 * and chip, up to four detail rows and the player photos (pre-fetched as data URIs; a missing one draws initials).
 * Model: lib/wrapped.ts wrappedShareModel (the app draws the same model with react-native).
 */

import { wrappedShortName, type WrappedShareModel } from "@/lib/wrapped";

import { ShareFrame, ShareQr, eyebrowStyle, glassStyle, initials, type ShareBrandAssets } from "./frame";
import { SHARE_TOKEN_HEX as T, positionHex, withAlpha } from "./tokens";

export interface WrappedCardImages {
  /** headshot id -> data URI (absent or null: initials). */
  headshots: Record<string, string | null | undefined>;
}

function Face({ src, name, pos, size }: { src: string | null; name: string; pos: string; size: number }) {
  const ring = positionHex(pos) ?? T["--color-border-strong"];
  const style = { width: size, height: size, borderRadius: size, border: `4px solid ${ring}`, backgroundColor: T["--color-surface-primary"] };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return <img src={src} width={size} height={size} style={{ ...style, objectFit: "cover", objectPosition: "top", flexShrink: 0 }} />;
  }
  return (
    <div style={{ ...style, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: Math.round(size * 0.34), fontWeight: 800, backgroundColor: withAlpha(ring, 0.16) }}>
      {initials(name)}
    </div>
  );
}

export function WrappedShareCard({ model, brand, width, height, images }: { model: WrappedShareModel; brand: ShareBrandAssets; width: number; height: number; images?: WrappedCardImages }) {
  const rows = model.rows.slice(0, 4);
  const hero = model.headline.length > 14 ? 96 : 190;
  return (
    <ShareFrame brand={brand} kind="Season Wrapped" width={width} height={height} footer={false}>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ ...eyebrowStyle(T["--color-accent"], 24), letterSpacing: "0.16em" }}>{model.eyebrow}</div>
        <div style={{ display: "block", fontSize: 68, fontWeight: 900, lineHeight: 1.05, lineClamp: 2 }}>{model.title}</div>
        {model.sub ? <div style={{ display: "block", fontSize: 30, fontWeight: 600, color: T["--color-text-secondary"] }}>{model.sub}</div> : null}
      </div>
      <div style={{ ...glassStyle(), flexDirection: "column", alignItems: "center", gap: 22, padding: "44px 48px", flexGrow: 1, justifyContent: "center" }}>
        {model.players.length ? (
          <div style={{ display: "flex", flexDirection: "row", gap: 28, alignItems: "center" }}>
            {model.players.slice(0, 2).map((p) => (
              <div key={p.id} style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 18 }}>
                <Face src={p.headshot_id ? images?.headshots[p.headshot_id] ?? null : null} name={p.name} pos={p.pos} size={96} />
                <div style={{ display: "flex", flexDirection: "column" }}>
                  <div style={{ display: "block", fontSize: 38, fontWeight: 800 }}>{wrappedShortName(p.name)}</div>
                  <div style={{ display: "block", fontSize: 24, color: T["--color-text-muted"] }}>{[p.pos, p.team].filter(Boolean).join(" · ")}</div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
        <div style={{ display: "flex", flexDirection: "row", alignItems: "flex-end", gap: 14 }}>
          <div style={{ display: "block", fontSize: hero, fontWeight: 900, lineHeight: 1 }}>{model.headline}</div>
          {model.unit ? <div style={{ display: "block", fontSize: 34, fontWeight: 700, color: T["--color-text-muted"], paddingBottom: 16 }}>{model.unit}</div> : null}
        </div>
        {model.chip ? (
          <div style={{ display: "flex", padding: "8px 24px", borderRadius: 999, border: `2px solid ${withAlpha(T["--color-success"], 0.5)}`, backgroundColor: withAlpha(T["--color-success"], 0.12), fontSize: 28, fontWeight: 700, color: T["--color-success"] }}>{model.chip}</div>
        ) : null}
        {rows.length ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12, width: "100%", marginTop: 12 }}>
            {rows.map((r, i) => (
              <div key={i} style={{ display: "flex", flexDirection: "row", justifyContent: "space-between", gap: 20, fontSize: 30 }}>
                <div style={{ display: "block", color: T["--color-text-muted"], fontWeight: 700 }}>{r.label}</div>
                <div style={{ display: "block", fontWeight: 800, textAlign: "right" }}>{r.value}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
      <div style={{ display: "flex", flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "block", fontSize: 30, fontWeight: 800 }}>{model.teamName}</div>
          <div style={{ display: "block", fontSize: 24, color: T["--color-text-muted"] }}>{model.seasonLabel}</div>
        </div>
        <ShareQr brand={brand} size={96} />
      </div>
    </ShareFrame>
  );
}
