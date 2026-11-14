import { pickBadge, type PickBadgeInput } from "@/lib/pickBadge";

/**
 * THE draft-pick avatar: a round badge ("R1", pick number small underneath) in the same circular slot a player photo
 * takes, so a pick reads like a player in every list. Never an illustration. Every pick render uses it (trade cards,
 * trade pickers, pick lists, draft board, inbox, sim and real). Mobile twin: components/PickAvatar.tsx.
 */
export function PickAvatar({ size = 36, ...input }: PickBadgeInput & { size?: number }) {
  const badge = pickBadge(input);
  const small = badge.bottom != null;
  return (
    <span
      className="relative flex shrink-0 flex-col items-center justify-center rounded-full font-extrabold uppercase leading-none"
      style={{
        width: size,
        height: size,
        gap: 1,
        background: "var(--color-surface-muted)",
        border: `${size >= 40 ? 3 : 2}px solid var(--color-accent)`,
        color: "var(--color-accent)",
        fontSize: Math.max(9, Math.round(size * (small ? 0.3 : 0.34))),
      }}
      role="img"
      aria-label={badge.a11y}
      data-testid="pick-avatar"
    >
      <span aria-hidden="true">{badge.top}</span>
      {small ? <span aria-hidden="true" style={{ fontSize: Math.max(7, Math.round(size * 0.22)), opacity: 0.8 }}>{badge.bottom}</span> : null}
    </span>
  );
}
