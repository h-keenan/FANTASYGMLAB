/**
 * Season in Review share card (Fantasy Sim final grade): the grade, the record
 * line, four highlight awards and four season numbers. Satori only, like
 * multiTradeCard.tsx; no network and no quota. Model: lib/simReview.ts
 * buildReviewShareModel (the app draws the same model with react-native).
 */

import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";
import type { ReviewShareModel, ReviewTone } from "@/lib/simReview";

import { ShareFrame, ShareQr, eyebrowStyle, glassStyle, type ShareBrandAssets } from "./frame";
import { SHARE_TOKEN_HEX as T, withAlpha } from "./tokens";

function toneHex(tone: ReviewTone): string {
  switch (tone) {
    case "success": return T["--color-success"];
    case "danger": return T["--color-danger"];
    case "warning": return T["--color-warning"];
    case "accent": return T["--color-accent"];
    default: return T["--color-text-secondary"];
  }
}

export function SeasonReviewShareCard({ model, brand, width, height }: { model: ReviewShareModel; brand: ShareBrandAssets; width: number; height: number }) {
  const gradeColor = toneHex(model.gradeTone);
  return (
    <ShareFrame brand={brand} kind={model.title} width={width} height={height} footer={false}>
      <div style={{ ...glassStyle(), flexDirection: "row", alignItems: "center", gap: 40, padding: "36px 44px", border: `2px solid ${withAlpha(gradeColor, 0.5)}` }}>
        <div style={{ display: "flex", fontSize: 220, fontWeight: 900, lineHeight: 1, color: gradeColor }}>{model.letter || "-"}</div>
        <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: 10 }}>
          <div style={{ display: "block", fontSize: 44, fontWeight: 900, lineHeight: 1.1, lineClamp: 2 }}>{model.headline}</div>
          {model.subline ? <div style={{ display: "block", fontSize: 26, fontWeight: 600, color: T["--color-text-secondary"], lineClamp: 2 }}>{model.subline}</div> : null}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, flexGrow: 1 }}>
        {model.highlights.map((h, i) => (
          <div key={i} style={{ ...glassStyle(), flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 20, padding: "18px 28px", borderLeft: `8px solid ${toneHex(h.tone)}` }}>
            <div style={{ display: "flex", flexDirection: "column", minWidth: 0, flexShrink: 1, gap: 4 }}>
              <div style={{ ...eyebrowStyle(toneHex(h.tone), 20), letterSpacing: "0.14em" }}>{h.label}</div>
              <div style={{ display: "block", fontSize: 32, fontWeight: 800, lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.text}</div>
            </div>
            {h.delta ? <div style={{ display: "flex", flexShrink: 0, fontSize: 36, fontWeight: 900, color: toneHex(h.tone) }}>{h.delta}</div> : null}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "row", gap: 14 }}>
        {model.stats.map((s, i) => (
          <div key={i} style={{ ...glassStyle(), flexGrow: 1, flexBasis: 0, flexDirection: "column", padding: "14px 18px", gap: 2 }}>
            <div style={{ ...eyebrowStyle(T["--color-text-muted"], 15), letterSpacing: "0.1em" }}>{s.label}</div>
            <div style={{ display: "flex", fontSize: 34, fontWeight: 900 }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", fontSize: 26, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
          <div style={{ display: "flex", fontSize: 18, fontWeight: 500, color: T["--color-text-muted"] }}>{`Play Fantasy Sim in ${BRAND_NAME}`}</div>
        </div>
        <ShareQr brand={brand} size={92} />
      </div>
    </ShareFrame>
  );
}
