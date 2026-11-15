import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
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

  it("expands on tap and collapses again (the body plays its exit, then leaves)", async () => {
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
    await waitFor(() => expect(screen.queryByText("expanded body")).toBeNull());
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
  it("Trade completed: it enters, auto-dismisses after ~4s, then plays its exit and unmounts (never pops)", () => {
    vi.useFakeTimers();
    function Host() {
      const [notice, setNotice] = useState<{ message: string; tone: "success" } | null>(null);
      return (
        <>
          <button type="button" onClick={() => setNotice({ message: "Trade done.", tone: "success" })}>trigger</button>
          <SimNotice message={notice?.message ?? ""} tone={notice?.tone} onDismiss={() => setNotice(null)} />
        </>
      );
    }
    render(<Host />);
    expect(screen.queryByTestId("sim-notice")).toBeNull();
    fireEvent.click(screen.getByText("trigger"));
    expect(screen.getByTestId("sim-notice")).toHaveAttribute("data-presence", "entering");
    act(() => vi.advanceTimersByTime(300));
    expect(screen.getByTestId("sim-notice")).toHaveAttribute("data-presence", "entered");
    act(() => vi.advanceTimersByTime(4000));
    // Timed out: still on screen, but leaving, with its text intact.
    expect(screen.getByTestId("sim-notice")).toHaveAttribute("data-presence", "exiting");
    expect(screen.getByText("Trade done.")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(200));
    expect(screen.queryByTestId("sim-notice")).toBeNull();
    vi.useRealTimers();
  });
});
