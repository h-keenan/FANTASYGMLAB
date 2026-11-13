"use client";

import type { CSSProperties, ElementType } from "react";

import { PlayerName } from "@/components/PlayerName";

/**
 * Deprecated alias of PlayerName (kept so older call sites keep compiling).
 * `threshold` is ignored: shortening is decided by measured overflow only.
 */
export function PlayerNameText(props: {
  name: string | null | undefined;
  threshold?: number;
  as?: ElementType;
  className?: string;
  style?: CSSProperties;
}) {
  const { threshold: _threshold, ...rest } = props;
  return <PlayerName {...rest} />;
}
