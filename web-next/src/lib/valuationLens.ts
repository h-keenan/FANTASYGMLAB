/**
 * The valuation lens options (server values + display labels). A plain
 * module rather than living only in ValuationLensContext ("use client"),
 * so server code such as the share-card routes can read the same list.
 */
export const VALUATION_LENS_OPTIONS = [
  { value: "Dynasty", label: "Dynasty", hint: "Values future upside alongside this year." },
  { value: "Rebuild", label: "Rebuild", hint: "Weights youth and draft capital most heavily." },
  { value: "Non-Dynasty", label: "Redraft", hint: "Values this season only — future picks discounted." },
] as const;

export type ValuationLens = (typeof VALUATION_LENS_OPTIONS)[number]["value"];
export const DEFAULT_LENS: ValuationLens = "Dynasty";

export function isValuationLens(value: string | null | undefined): value is ValuationLens {
  return VALUATION_LENS_OPTIONS.some((option) => option.value === value);
}

export function valuationLensLabel(value: string): string {
  return VALUATION_LENS_OPTIONS.find((option) => option.value === value)?.label ?? value;
}
