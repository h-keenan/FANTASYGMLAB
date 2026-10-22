/**
 * Player share card: the Player Profile hero (photo in its tier ring,
 * square position badge, OVR ring, league value and ranks) as an image.
 * Every field comes off the server's own RankedPlayer
 * (GET .../players/{id}/rank), the same row the profile page renders.
 */

import type { RankedPlayer } from "@/lib/api";
import { resolvePlayerTier } from "@/lib/playerTier";

import {
  ShareAvatar,
  ShareChip,
  ShareFrame,
  ShareOvrRing,
  SharePositionBadge,
  type ShareBrandAssets,
  eyebrowStyle,
  formatValue,
  glassStyle,
  initials,
} from "./frame";
import { SHARE_TOKEN_HEX as T, tierHex } from "./tokens";

function StatCell({ label, value, valueSize = 60 }: { label: string; value: string; valueSize?: number }) {
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", flexGrow: 1, flexBasis: 0, padding: "26px 28px", gap: 10 }}>
      <div style={eyebrowStyle(T["--color-text-muted"], 20)}>{label}</div>
      <div style={{ fontSize: valueSize, fontWeight: 900, lineHeight: 1.05 }}>{value}</div>
    </div>
  );
}

export function PlayerShareCard({
  player,
  brand,
  headshot,
  lens,
  width,
  height,
}: {
  player: RankedPlayer;
  brand: ShareBrandAssets;
  headshot: string | null;
  lens: string;
  width: number;
  height: number;
}) {
  const name = player.name || `Player ${player.player_id}`;
  const tierColor = tierHex(player.tier);
  const cells: { label: string; value: string }[] = [];
  const value = formatValue(player.score);
  if (value) cells.push({ label: `${lens} value`, value });
  if (player.overall_rank) cells.push({ label: "Overall rank", value: `#${player.overall_rank}` });
  if (player.position_rank) cells.push({ label: "Position rank", value: `${player.position || ""}${player.position_rank}` });
  const meta = [player.team || "FA", player.age !== null && player.age !== undefined ? `Age ${Math.round(player.age)}` : ""].filter(Boolean);

  return (
    <ShareFrame brand={brand} kind="Player card" width={width} height={height}>
      <div style={{ ...glassStyle(), flexDirection: "column", alignItems: "center", padding: "40px 40px 40px", gap: 20 }}>
        <ShareAvatar src={headshot} tier={player.tier} size={240} fallbackText={initials(name)} />
        {player.tier && tierColor ? <ShareChip label={resolvePlayerTier(player.tier).semanticLabel} color={tierColor} size={24} /> : null}
        <div style={{ display: "flex", fontSize: 76, fontWeight: 900, lineHeight: 1.02, textAlign: "center", justifyContent: "center" }}>{name}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 18, fontSize: 32, fontWeight: 600, color: T["--color-text-muted"] }}>
          <SharePositionBadge position={player.position} size={30} />
          <span>{meta.join(" · ")}</span>
        </div>
      </div>

      <div style={{ display: "flex", gap: 20, alignItems: "stretch" }}>
        {player.overall_rating !== null && player.overall_rating !== undefined ? (
          <div style={{ ...glassStyle(), flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "20px 28px", gap: 10 }}>
            <ShareOvrRing rating={player.overall_rating} size={124} />
            <div style={eyebrowStyle(T["--color-text-muted"], 20)}>Overall</div>
          </div>
        ) : null}
        <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, gap: 20 }}>
          <div style={{ display: "flex", gap: 20 }}>
            {cells.slice(0, 2).map((cell) => (
              <StatCell key={cell.label} label={cell.label} value={cell.value} />
            ))}
          </div>
          {cells[2] ? (
            <div style={{ display: "flex", gap: 20 }}>
              <StatCell label={cells[2].label} value={cells[2].value} />
              {player.opportunity_label ? <StatCell label="Role" value={player.opportunity_label} valueSize={38} /> : null}
            </div>
          ) : null}
        </div>
      </div>
    </ShareFrame>
  );
}
