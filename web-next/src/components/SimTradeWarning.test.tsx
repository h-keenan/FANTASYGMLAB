import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimTradeWarning } from "./SimTradeWarning";

describe("SimTradeWarning", () => {
  it("shows the message, can be dismissed, and comes back for a different message", () => {
    const { rerender } = render(<SimTradeWarning message="They already have a kicker." />);
    expect(screen.getByTestId("trade-warning")).toHaveTextContent("They already have a kicker.");
    fireEvent.click(screen.getByText("Dismiss"));
    expect(screen.queryByTestId("trade-warning")).toBeNull();
    rerender(<SimTradeWarning message="You already have a defense." />);
    expect(screen.getByTestId("trade-warning")).toBeTruthy();
    rerender(<SimTradeWarning message="" />);
    expect(screen.queryByTestId("trade-warning")).toBeNull();
  });
});
