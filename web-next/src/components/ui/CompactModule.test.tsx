import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimNotice } from "../SimGameParts";
import { CompactModule } from "./CompactModule";

describe("CompactModule", () => {
  it("collapsed it shows the dense summary and a usable action, not an empty header", () => {
    const onDraft = vi.fn();
    render(
      <CompactModule
        id="test.clock"
        title="Draft clock"
        persist={false}
        parts={[{ key: "rp", text: "R1 P2", strong: true }, { key: "s", text: "You pick now" }, { key: "n", text: "need RB/WR" }]}
        action={<button onClick={onDraft}>Draft Gibbs</button>}
      >
        <p>expanded body</p>
      </CompactModule>,
    );
    expect(screen.getByTestId("compact-summary")).toHaveTextContent("R1 P2 · You pick now · need RB/WR");
    expect(screen.queryByText("expanded body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Draft Gibbs" }));
    expect(onDraft).toHaveBeenCalledTimes(1);
    // The action does not toggle the module.
    expect(screen.queryByText("expanded body")).toBeNull();
  });

  it("expands on tap and collapses again", () => {
    render(
      <CompactModule id="test.toggle" title="Board" persist={false} parts={[{ key: "a", text: "1/192 picks" }]}>
        <p>expanded body</p>
      </CompactModule>,
    );
    const header = screen.getByRole("button", { name: /Board: 1\/192 picks\. Expand/ });
    expect(header).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(header);
    expect(screen.getByText("expanded body")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Collapse/ })).toHaveAttribute("aria-expanded", "true");
    fireEvent.click(screen.getByRole("button", { name: /Collapse/ }));
    expect(screen.queryByText("expanded body")).toBeNull();
  });
});

describe("SimNotice toast", () => {
  it("a confirmation the player caused removes itself after a few seconds", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<SimNotice message="Trade completed." tone="success" onDismiss={onDismiss} />);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.advanceTimersByTime(4100);
    expect(onDismiss).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
  it("an error stays until dismissed", () => {
    vi.useFakeTimers();
    const onDismiss = vi.fn();
    render(<SimNotice message="Could not trade." tone="danger" onDismiss={onDismiss} />);
    vi.advanceTimersByTime(60000);
    expect(onDismiss).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});
