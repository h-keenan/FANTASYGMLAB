/**
 * Opt-in "Share to community" helpers (pure, no React). Mirrors web-next's
 * communityTradesPresentation.ts / ShareToCommunityToggle payload.
 */

export interface SharedTradeAssetInput {
  asset_type: 'player' | 'pick';
  name: string;
  position?: string;
  player_id?: string;
}

export interface ShareableVerdict {
  ui_verdict: string;
  band: string;
  rationale: string;
}

export const SHARE_WHY_MAX = 280;
export const SHARE_NAME_MAX = 24;
const SHAREABLE_GRADES = new Set(['ACCEPT', 'DECLINE', 'COUNTER', 'FAIR']);

export function isShareableGrade(grade: string): boolean {
  return SHAREABLE_GRADES.has(grade);
}

export function buildShareBody(
  verdict: ShareableVerdict,
  send: SharedTradeAssetInput[],
  receive: SharedTradeAssetInput[],
  displayName: string,
) {
  return {
    send,
    receive,
    grade: verdict.ui_verdict,
    band: verdict.band,
    why: (verdict.rationale || '').slice(0, SHARE_WHY_MAX),
    display_name: displayName.trim().slice(0, SHARE_NAME_MAX),
  };
}

export type GradeTone = 'success' | 'danger' | 'accent' | 'neutral';

export function gradeTone(grade: string): GradeTone {
  if (grade === 'ACCEPT') return 'success';
  if (grade === 'DECLINE') return 'danger';
  if (grade === 'COUNTER') return 'accent';
  return 'neutral';
}

export function assetLabel(asset: SharedTradeAssetInput): string {
  return asset.position ? `${asset.name} · ${asset.position}` : asset.name;
}
