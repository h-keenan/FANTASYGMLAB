import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TradeScale } from "@/components/ui/TradeScale";
import { simAcceptanceMeter } from "@/lib/tradeScale";

const chase = { key: "a", player: { id: "7564", name: "Ja'Marr Chase", position: "WR", team: "CIN" }, value: 90 };
const gibbs = { key: "b", player: { id: "9221", name: "Jahmyr Gibbs", position: "RB", team: "DET" }, value: 80 };
const pick = { key: "p", pickLabel: "2027 Round 1" };

describe("TradeScale (two-column scale)", () => {
  it("shows both columns with avatars, an empty-state meter and add tiles when nothing is selected", () => {
    const onAdd = vi.fn();
    render(<TradeScale give={[]} get={[]} onAdd={onAdd} />);
    expect(screen.getByTestId("trade-scale")).toHaveAttribute("data-phase", "empty");
    expect(screen.getByTestId("fairness-label")).toHaveTextContent("Add what you send");
    fireEvent.click(screen.getByTestId("scale-add-get"));
    expect(onAdd).toHaveBeenCalledWith("get");
  });

  it("says what is missing while one side is empty, and keeps the add tiles", () => {
    render(<TradeScale give={[chase]} get={[]} onAdd={() => {}} />);
    expect(screen.getByTestId("trade-scale")).toHaveAttribute("data-phase", "building");
    expect(screen.getByTestId("fairness-label")).toHaveTextContent("Add something you get");
    expect(screen.getAllByTestId("player-avatar-slot")).toHaveLength(1);
  });

  it("updates the meter live as assets change", () => {
    const { rerender } = render(<TradeScale give={[gibbs]} get={[chase]} onAdd={() => {}} />);
    expect(screen.getByTestId("fairness-label").textContent).toMatch(/win|edge to you/i);
    rerender(<TradeScale give={[chase]} get={[gibbs]} onAdd={() => {}} />);
    expect(screen.getByTestId("fairness-label").textContent).toMatch(/lose|edge to them/i);
  });

  it("replaces the add tiles with the verdict and Send / Tweak when ready; Tweak brings the tiles back", () => {
    const onSend = vi.fn();
    render(<TradeScale give={[gibbs]} get={[chase, pick]} onAdd={() => {}} onRemove={() => {}} verdict={<p>Fair for both</p>} onSend={onSend} />);
    expect(screen.getByTestId("trade-scale")).toHaveAttribute("data-phase", "review");
    expect(screen.getByText("Fair for both")).toBeInTheDocument();
    expect(screen.getByTestId("scale-add-give").closest(".scale-collapse")).toHaveAttribute("data-open", "false");
    expect(screen.queryByLabelText(/^Remove/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Send offer" }));
    expect(onSend).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Tweak" }));
    expect(screen.getByTestId("trade-scale")).toHaveAttribute("data-phase", "tweak");
    expect(screen.getByTestId("scale-add-give").closest(".scale-collapse")).toHaveAttribute("data-open", "true");
    expect(screen.getByLabelText("Remove Jahmyr Gibbs")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Review" }));
    expect(screen.getByTestId("trade-scale")).toHaveAttribute("data-phase", "review");
  });

  it("opens the peek when a card is tapped and draws a pick with the pick avatar", () => {
    const onOpen = vi.fn();
    render(<TradeScale give={[{ ...gibbs, onOpen }]} get={[pick]} onAdd={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Open Jahmyr Gibbs" }));
    expect(onOpen).toHaveBeenCalled();
    expect(screen.getByTestId("pick-avatar")).toBeInTheDocument();
  });

  it("sim mode uses the acceptance meter in plain words and never prints a value or percentage", () => {
    const sim = { ...chase, value: undefined };
    render(<TradeScale mode="sim" give={[{ ...gibbs, value: undefined }]} get={[sim]} meter={simAcceptanceMeter("counter")} onAdd={() => {}} verdict={<p>They want a TE</p>} />);
    expect(screen.getByTestId("fairness-label")).toHaveTextContent("They would counter");
    expect(screen.getByTestId("trade-scale").textContent).not.toMatch(/%|\b90\b|\b80\b/);
  });

  it("hides the add tile at the per-side cap", () => {
    render(<TradeScale give={[gibbs]} get={[]} max={1} onAdd={() => {}} />);
    expect(screen.getByTestId("scale-add-give").closest(".scale-collapse")).toHaveAttribute("data-open", "false");
    expect(screen.getByTestId("scale-give")).toHaveTextContent("1 of 1");
  });
});
