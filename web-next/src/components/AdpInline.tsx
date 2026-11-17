import { ADP_CREDIT, ADP_CREDIT_URL, EST_SF_NOTE, adpParts, type AdpFields } from "@/lib/adpPresentation";

/** "1QB ADP 4.2 · Est. SF 2.0 ?" - the estimate is always labelled and explained. */
export function AdpInline({ adp, note = EST_SF_NOTE }: { adp: AdpFields; note?: string }) {
  const { real, est } = adpParts(adp);
  if (!real) return null;
  return (
    <span data-testid="adp-inline">
      {real}
      {est ? (
        <>
          {" · "}
          <span data-testid="adp-est-sf">{est}</span>{" "}
          <abbr title={note} aria-label={note} className="cursor-help" style={{ textDecoration: "none" }}>
            ?
          </abbr>
        </>
      ) : null}
    </span>
  );
}

export function AdpCredit({ asOf, className = "" }: { asOf?: string | null; className?: string }) {
  return (
    <p className={`text-xs ${className}`.trim()} style={{ color: "var(--color-text-muted)" }} data-testid="adp-credit">
      <a href={ADP_CREDIT_URL} target="_blank" rel="noopener noreferrer" className="underline tap-link" style={{ color: "var(--color-text-secondary)" }}>
        {ADP_CREDIT}
      </a>
      {asOf ? ` (as of ${asOf})` : ""}
    </p>
  );
}
