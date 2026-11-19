import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SeasonWrapped } from "@/components/SeasonWrapped";
import type { WrappedDeck } from "@/lib/wrapped";

vi.mock("@/components/PlayerAvatar", () => ({ PlayerAvatar: ({ name }: { name?: string }) => <span data-testid="avatar">{name}</span> }));
vi.mock("@/lib/useShareImage", () => ({ useShareImage: () => ({ onClick: vi.fn(), busy: false, label: (l: string) => l, status: null }) }));

const P = { id: "1", headshot_id: "1", name: "Marcus Hale", pos: "RB", team: "MIA" };
const deck: WrappedDeck = {
  kind: "sim",
  partial: false,
  season_label: "Sim Season 1 · 2026",
  team_name: "Lake City Comets",
  cards: [
    { id: "intro", eyebrow: "X", title: "Your season, wrapped", sub: "Lake City Comets", pro: false, locked: false, data: { record: "9-5", outcome: "Lost in the semifinal" } },
    { id: "bust", eyebrow: "BIGGEST BUST", title: "The one that got away", sub: "Round 2, pick 17", pro: false, locked: false, data: { player: P, projected: 168, actual: 115.6, over_proj: -52.4, why: "Missed 5 games: hamstring" } },
    { id: "trades", eyebrow: "TRADES", title: "Best and worst trade", sub: null, pro: true, locked: true, data: null },
  ],
};

describe("SeasonWrapped", () => {
  it("walks the cards, shows names as J. Surname with a photo, and locks Pro cards", () => {
    const onClose = vi.fn();
    render(<SeasonWrapped deck={deck} itemId="g1" onClose={onClose} />);
    expect(screen.getByText("9-5")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Share this card" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next card" }));
    expect(screen.getByText("M. Hale")).toBeTruthy();
    expect(screen.getByTestId("avatar")).toBeTruthy();
    expect(screen.getByText("Missed 5 games: hamstring")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Next card" }));
    expect(screen.getByTestId("wrapped-locked")).toBeTruthy();
    expect(screen.getByText("Unlock with Pro")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Share this card" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalled();
  });
});
