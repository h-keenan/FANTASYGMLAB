/**
 * Season in Review share card (Fantasy Sim final grade): the team crest and
 * grade, the outcome and record, four highlight awards (with player photos)
 * and four season numbers. Satori only, like multiTradeCard.tsx. Model:
 * lib/simReview.ts buildReviewShareModel (the app draws the same model with
 * react-native). Photos arrive pre-fetched as data URIs (clientRender.tsx);
 * a missing one falls back to initials.
 */

import type { CSSProperties } from "react";

import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";
import { simCrestArt, simCrestSpec } from "@/lib/simCrest";
import { splitReviewGrade, type ReviewGlyph, type ReviewShareModel, type ReviewTone } from "@/lib/simReview";

import { ShareFrame, ShareQr, eyebrowStyle, glassStyle, initials, type ShareBrandAssets } from "./frame";
import { SHARE_TOKEN_HEX as T, mixHex, positionHex, withAlpha } from "./tokens";

export interface SeasonReviewImages {
  /** headshot id -> data URI (absent or null: initials). */
  headshots: Record<string, string | null | undefined>;
}

function toneHex(tone: ReviewTone): string {
  switch (tone) {
    case "success": return T["--color-success"];
    case "danger": return T["--color-danger"];
    case "warning": return T["--color-warning"];
    case "accent": return T["--color-accent"];
    default: return T["--color-text-secondary"];
  }
}

const GOLD = T["--color-action"];
const GOLD_SOFT = "#fde68a";

/** SimReviewGlyph.tsx's stroke glyphs, as explicit-color SVG (Satori draws svg as an image). */
const GLYPH_PATHS: Record<ReviewGlyph | "stats", string> = {
  lineup: "M5.5 3H4v10.5h8V3h-1.5M6 2h4v2H6zM6 7.5h4M6 10h3",
  waiver: "M8 2.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM8 5.5v5M5.5 8h5",
  trade: "M3 5.5h9.5M10 3l2.5 2.5L10 8M13 10.5H3.5M6 8l-2.5 2.5L6 13",
  draft: "M2.5 5.5h11v2a1 1 0 000 2v2h-11v-2a1 1 0 000-2zM6.5 5.5v6",
  injury: "M8 2.5v11M2.5 8h11",
  boom: "M3 12l3.5-3.5 2 2L13 5M9.5 5H13v3.5",
  bust: "M3 4l3.5 3.5 2-2L13 11M9.5 11H13V7.5",
  game: "M8 4.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9zM8 9V6.5M6.5 2h3",
  trophy: "M5 2.5h6v3.5a3 3 0 01-6 0zM5 4H2.5c0 2 1 3 2.5 3M11 4h2.5c0 2-1 3-2.5 3M8 9v2.5M5.5 13.5h5",
  rank: "M2.5 3v10.5H13.5M4.5 10l3-3 2 2 3.5-4.5",
  leader: "M3.5 13V9M8 13V3M12.5 13V6",
  path: "M4 2v12M4 3h7.5l-1.8 2.5L11.5 8H4",
  stats: "M3 13V8M6.5 13V4M10 13V7M13.5 13V10",
};

export function ReviewGlyphSvg({ glyph, size, color, strokeWidth = 1.5 }: { glyph: ReviewGlyph; size: number; color: string; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
      <path d={GLYPH_PATHS[glyph] ?? GLYPH_PATHS.stats} />
    </svg>
  );
}

/** The team's generated crest (lib/simCrest.ts). The letter is a real text
 * node over the shape: text inside an svg image would not get the card fonts. */
export function ShareCrest({ name, size }: { name: string; size: number }) {
  const spec = simCrestSpec(name);
  const art = simCrestArt(spec);
  const clip = "crest-clip";
  const fontSize = Math.round((art.letterSize / 64) * size);
  const top = Math.round(((art.letterY - art.letterSize * 0.74) / 64) * size);
  return (
    <div style={{ display: "flex", position: "relative", width: size, height: size, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={art.viewBox} style={{ position: "absolute", top: 0, left: 0 }}>
        <defs>
          <clipPath id={clip}>
            <path d={art.outline} />
          </clipPath>
        </defs>
        <path d={art.outline} fill={spec.primary} />
        {art.pattern ? (
          <g clipPath={`url(#${clip})`}>
            <path d={art.pattern} fill={spec.secondary} opacity={0.92} />
          </g>
        ) : null}
        <path d={art.outline} fill="none" stroke={spec.secondary} strokeWidth={3} strokeLinejoin="round" />
      </svg>
      <div
        style={{
          position: "absolute",
          top,
          left: 0,
          width: size,
          display: "flex",
          justifyContent: "center",
          fontSize,
          lineHeight: 1,
          fontWeight: 900,
          color: spec.ink,
          textShadow: `0 0 ${Math.max(2, Math.round(size / 24))}px ${spec.halo}, 0 0 ${Math.max(2, Math.round(size / 24))}px ${spec.halo}`,
        }}
      >
        {art.letter}
      </div>
    </div>
  );
}

/** Letter big, +/- as a small raised glyph, in a box whose width never changes. */
export function GradeLockup({ letter, color, size, width }: { letter: string; color: string; size: number; width: number }) {
  const { base, modifier } = splitReviewGrade(letter);
  const badge = Math.round(size * 0.4);
  return (
    <div style={{ display: "flex", flexDirection: "row", alignItems: "flex-start", justifyContent: "center", gap: Math.round(size * 0.06), width, flexShrink: 0 }}>
      <div style={{ display: "flex", fontSize: size, fontWeight: 900, lineHeight: 1, color }}>{base}</div>
      {modifier ? (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: badge,
            height: badge,
            borderRadius: badge,
            border: `${Math.max(3, Math.round(size * 0.02))}px solid ${color}`,
            backgroundColor: withAlpha(color, 0.16),
            marginTop: Math.round(size * 0.08),
            flexShrink: 0,
            fontSize: Math.round(badge * 0.78),
            fontWeight: 900,
            lineHeight: 1,
            color,
          }}
        >
          {modifier === "-" ? "\u2212" : "+"}
        </div>
      ) : null}
    </div>
  );
}

function Headshot({ src, name, pos, size }: { src: string | null; name: string; pos: string; size: number }) {
  const ring = positionHex(pos) ?? T["--color-border-strong"];
  const style: CSSProperties = {
    width: size,
    height: size,
    borderRadius: size,
    border: `4px solid ${ring}`,
    backgroundColor: T["--color-surface-primary"],
  };
  if (src) {
    // eslint-disable-next-line @next/next/no-img-element, jsx-a11y/alt-text
    return <img src={src} width={size} height={size} style={{ ...style, objectFit: "cover", objectPosition: "top", flexShrink: 0 }} />;
  }
  return (
    <div style={{ ...style, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, fontSize: Math.round(size * 0.34), fontWeight: 800, color: mixHex(ring, T["--color-text-primary"], 60), backgroundColor: withAlpha(ring, 0.16) }}>
      {initials(name)}
    </div>
  );
}

export function SeasonReviewShareCard({
  model,
  brand,
  width,
  height,
  images,
}: {
  model: ReviewShareModel;
  brand: ShareBrandAssets;
  width: number;
  height: number;
  images?: SeasonReviewImages;
}) {
  const tall = height > 1500;
  const champion = model.outcome === "champion";
  const gradeColor = toneHex(model.gradeTone);
  const accent = champion ? GOLD : gradeColor;
  const heroBorder = champion ? withAlpha(GOLD, 0.85) : withAlpha(gradeColor, 0.5);
  const avatar = tall ? 112 : 76;
  return (
    <ShareFrame brand={brand} kind={model.title} width={width} height={height} footer={false}>
      <div
        style={{
          ...glassStyle(),
          flexDirection: "column",
          gap: tall ? 30 : 16,
          padding: tall ? "40px 44px" : "24px 40px",
          border: `${champion ? 3 : 2}px solid ${heroBorder}`,
          ...(champion ? { backgroundImage: `linear-gradient(165deg, ${withAlpha(GOLD, 0.2)}, rgba(24, 26, 30, 0.92) 62%)` } : {}),
        }}
      >
        {model.teamName ? (
          <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 20 }}>
            <ShareCrest name={model.teamName} size={tall ? 96 : 72} />
            <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: 4 }}>
              <div style={{ ...eyebrowStyle(T["--color-text-muted"], 18), letterSpacing: "0.14em" }}>Your team</div>
              <div style={{ display: "block", fontSize: 38, fontWeight: 800, lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{model.teamName}</div>
            </div>
          </div>
        ) : null}
        <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 28 }}>
          <GradeLockup letter={model.letter} color={gradeColor} size={tall ? 250 : 190} width={tall ? 300 : 250} />
          <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 14 }}>
              {champion ? <ReviewGlyphSvg glyph="trophy" size={52} color={GOLD} strokeWidth={1.3} /> : null}
              <div style={{ display: "block", fontSize: 46, fontWeight: 900, lineHeight: 1.05, color: champion ? GOLD_SOFT : T["--color-text-primary"], lineClamp: 2, flexShrink: 1, minWidth: 0 }}>{model.headline}</div>
            </div>
            {model.subline ? <div style={{ display: "block", fontSize: 27, fontWeight: 700, lineHeight: 1.2, color: T["--color-text-secondary"], lineClamp: 2 }}>{model.subline}</div> : null}
            {model.tags.length ? (
              <div style={{ display: "flex", flexDirection: "row", flexWrap: "wrap", gap: 10 }}>
                {model.tags.map((tag, i) => (
                  <div key={i} style={{ display: "flex", padding: "5px 14px", borderRadius: 999, border: `1.5px solid ${withAlpha(accent, 0.4)}`, backgroundColor: withAlpha(accent, 0.1), fontSize: 20, fontWeight: 700, color: T["--color-text-secondary"] }}>{tag}</div>
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: tall ? 18 : 14, flexGrow: 1, justifyContent: "space-between" }}>
        {model.highlights.map((h, i) => {
          const tone = toneHex(h.tone);
          const shot = h.player?.headshotId ? images?.headshots[h.player.headshotId] ?? null : null;
          const posColor = positionHex(h.player?.pos);
          return (
            <div key={i} style={{ ...glassStyle(), flexDirection: "row", alignItems: "center", gap: 22, padding: tall ? "20px 30px 20px 24px" : "10px 28px 10px 22px", borderLeft: `8px solid ${tone}`, flexGrow: 1 }}>
              {h.player ? (
                <Headshot src={shot} name={h.player.name} pos={h.player.pos} size={avatar} />
              ) : (
                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", width: avatar, height: avatar, borderRadius: avatar, backgroundColor: withAlpha(tone, 0.15), flexShrink: 0 }}>
                  <ReviewGlyphSvg glyph={h.glyph} size={Math.round(avatar * 0.5)} color={tone} />
                </div>
              )}
              <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: 6 }}>
                <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 10 }}>
                  <ReviewGlyphSvg glyph={h.glyph} size={24} color={tone} strokeWidth={1.7} />
                  <div style={{ ...eyebrowStyle(tone, 20), letterSpacing: "0.14em" }}>{h.label}</div>
                </div>
                <div style={{ display: "block", fontSize: 34, fontWeight: 800, lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{h.text}</div>
                {h.player ? (
                  <div style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: 10, fontSize: 20, fontWeight: 700, color: T["--color-text-muted"] }}>
                    {h.player.pos ? <div style={{ display: "flex", color: posColor ?? T["--color-text-muted"], fontWeight: 800 }}>{h.player.pos}</div> : null}
                    {h.player.team ? <div style={{ display: "flex" }}>{h.player.team}</div> : null}
                  </div>
                ) : null}
              </div>
              {h.delta ? <div style={{ display: "flex", flexShrink: 0, fontSize: 36, fontWeight: 900, color: tone }}>{h.delta}</div> : null}
            </div>
          );
        })}
      </div>
      <div style={{ display: "flex", flexDirection: "row", gap: 14 }}>
        {model.stats.map((s, i) => (
          <div key={i} style={{ ...glassStyle(), flexGrow: 1, flexBasis: 0, flexDirection: "column", justifyContent: "space-between", padding: "12px 18px", gap: 4 }}>
            <div style={{ ...eyebrowStyle(T["--color-text-muted"], 15), letterSpacing: "0.1em" }}>{s.label}</div>
            <div style={{ display: "flex", fontSize: 34, fontWeight: 900 }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", fontSize: 28, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
          <div style={{ display: "flex", fontSize: 20, fontWeight: 500, color: T["--color-text-muted"] }}>{`Play Fantasy Sim in ${BRAND_NAME}`}</div>
        </div>
        <ShareQr brand={brand} size={84} />
      </div>
    </ShareFrame>
  );
}
