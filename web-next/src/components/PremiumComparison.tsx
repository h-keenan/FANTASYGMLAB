import { FALLBACK_PREMIUM_COMPARISON, type PremiumComparisonRow } from "@/lib/premiumComparison";

/** Concrete Free-vs-Premium table. Rows come from the server's enforced
 * limits (see lib/premiumComparison.ts). Semantic table so it reads on
 * phones and to screen readers; no new colors (premium token on the
 * Premium column). Labeled "Premium" (not the specific "Pro" plan name) to
 * match the site's one consistent umbrella term for the paid tier in every
 * non-plan-selection surface — see PR's P0 UX audit naming-consistency fix,
 * 2026-10-27. */
export function PremiumComparison({ rows = FALLBACK_PREMIUM_COMPARISON }: { rows?: PremiumComparisonRow[] }) {
  return (
    <table className="w-full text-sm" style={{ borderCollapse: "collapse" }}>
      <caption className="sr-only">Free compared with Premium</caption>
      <thead>
        <tr className="text-xs uppercase" style={{ color: "var(--color-text-muted)" }}>
          <th scope="col" className="text-left font-bold py-1 pr-2">
            What you get
          </th>
          <th scope="col" className="text-left font-bold py-1 px-2">
            Free
          </th>
          <th scope="col" className="text-left font-bold py-1 pl-2" style={{ color: "var(--color-premium)" }}>
            Premium
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} style={{ borderTop: "1px solid var(--color-border)" }}>
            <th scope="row" className="text-left font-bold py-2 pr-2 align-top">
              {row.label}
            </th>
            <td className="py-2 px-2 align-top" style={{ color: "var(--color-text-secondary)" }}>
              {row.free}
            </td>
            <td className="py-2 pl-2 align-top font-bold">{row.pro}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
