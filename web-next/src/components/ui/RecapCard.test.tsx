import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecapCard } from "./RecapCard";
import { recapCardModel } from "@/lib/recapCard";

const rows = [1, 2, 3, 4].map((n) => ({ key: `k${n}`, label: `Label ${n}`, value: `Value ${n}`, sub: n === 1 ? "pts" : null }));

describe("RecapCard", () => {
  it("draws the kicker, a badge and exactly three rows, with the rest behind More", () => {
    render(<RecapCard model={recapCardModel({ kicker: "DRAFT RECAP", badge: "A-", rows })} />);
    expect(screen.getByText("DRAFT RECAP")).toBeInTheDocument();
    expect(screen.getByTestId("recap-card-badge")).toHaveTextContent("A-");
    expect(screen.getAllByTestId("recap-card-row")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "More (1)" }));
    expect(screen.getAllByTestId("recap-card-row")).toHaveLength(4);
    expect(screen.getByText("Value 4")).toBeInTheDocument();
    expect(document.body.innerHTML).not.toMatch(/--color-action|--color-premium/);
  });
  it("has no More button when there are three rows or fewer", () => {
    render(<RecapCard model={recapCardModel({ kicker: "K", rows: rows.slice(0, 3) })} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
