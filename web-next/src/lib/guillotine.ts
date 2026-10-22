import type { GuillotineResponse } from "@/lib/api";

export type GuillotineTone = "success" | "danger";

export type GuillotineView = {
  badge: { label: string; tone: GuillotineTone };
  items: Array<{ label: string; value: string; tone?: "neutral" | "risk" | "positive" }>;
};

function signed(n: number): string {
  return `${n > 0 ? "+" : ""}${n.toFixed(1)}`;
}

/** Card model for a guillotine league; null (render nothing) otherwise. */
export function guillotineView(data: GuillotineResponse | null | undefined): GuillotineView | null {
  if (!data || !data.ok || !data.is_guillotine || data.alive === undefined) return null;
  const chop = data.chop_line ?? null;
  const items: GuillotineView["items"] = [
    { label: "Survived", value: `${data.weeks_survived ?? 0} wk` },
    { label: "Alive", value: `${data.teams_alive ?? 0}/${data.teams_total ?? 0}` },
  ];
  if (data.alive && chop) {
    items.push({ label: "Chop line", value: chop.line.toFixed(1) });
    if (chop.margin != null) {
      items.push({ label: "Margin", value: signed(chop.margin), tone: chop.at_risk ? "risk" : "positive" });
    }
  }
  const label = !data.alive ? "Chopped" : chop?.at_risk ? "At risk" : "Alive";
  return { badge: { label, tone: data.alive && !chop?.at_risk ? "success" : "danger" }, items };
}
