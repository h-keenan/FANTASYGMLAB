/**
 * Small pill-style segmented control for a scope/filter toggle (e.g.
 * League Recaps/History's filter pills, Draft Center's My Picks/League
 * toggle). Extracted from LeagueRecapsContent's local `PillRow` (Revision
 * 13) so Revision 14's Draft Center doesn't redefine the same four style
 * rules a second time — visual output is unchanged from the original.
 */
export function PillRow({
  options,
  active,
  onSelect,
}: {
  options: { label: string; value: string }[];
  active: string;
  onSelect: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-0" style={{ border: "var(--border-width-default) solid var(--color-border)" }}>
      {options.map((option) => {
        const isActive = option.value === active;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onSelect(option.value)}
            aria-pressed={isActive}
            className="px-3 py-2 text-xs font-bold uppercase"
            style={{
              letterSpacing: "0.03em",
              background: isActive ? "var(--color-information-soft)" : "var(--color-surface-muted)",
              color: isActive ? "var(--color-text-primary)" : "var(--color-text-secondary)",
              boxShadow: isActive ? "inset 0 -2px 0 var(--color-information)" : "none",
              border: "var(--border-width-default) solid var(--color-border)",
              marginLeft: "-1px",
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
