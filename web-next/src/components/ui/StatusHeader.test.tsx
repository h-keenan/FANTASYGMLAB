import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StatusHeader } from "./StatusHeader";
import type { StatusHeaderModel } from "@/lib/statusHeader";

const MODEL: StatusHeaderModel = {
  kicker: "TODAY",
  headline: "Set 2 lineup holes",
  context: "A waiver add could win your week",
  ring: { pct: 72, center: "72%", label: "Win chance 72%", tone: "success" },
  stats: [
    { key: "a", label: "Trades", value: "3 ideas", href: "/trade-hub/x" },
    { key: "b", label: "Standing", value: "3rd of 12" },
  ],
  attention: [
    { key: "p1", playerId: "123", name: "Tank Dell", position: "WR", team: "HOU", meta: "HOU · 12% rostered", stat: { value: "+4.1", label: "GAIN", tone: "success" }, detail: "He is open on the wire.", href: "/waivers/x" },
    { key: "p2", playerId: null, name: "Brock Bowers", position: "TE", team: "LV", meta: "LV · 23", stat: { value: "11.4", label: "PROJ" }, href: "/my-team/x" },
    { key: "p3", playerId: "7", name: "Jahmyr Gibbs", position: "RB", team: "DET", meta: "Best available · ADP 5.1", grade: "A-" },
  ],
  primary: { label: "Fix lineup", actionKey: "team" },
};

describe("StatusHeader", () => {
  it("renders the ring, mini stats, player rows with avatars and the one primary action", () => {
    const onAction = vi.fn();
    render(<StatusHeader model={MODEL} onAction={onAction} />);
    expect(screen.getByTestId("status-ring")).toHaveAttribute("aria-label", "Win chance 72%");
    expect(screen.getByTestId("status-headline")).toHaveTextContent("Set 2 lineup holes");
    expect(screen.getByTestId("status-stat-a")).toHaveAttribute("href", "/trade-hub/x");
    const rows = screen.getAllByTestId("status-attention-row");
    expect(rows).toHaveLength(3);
    // Every player row carries the avatar (an img when there is a headshot id, the ringed circle otherwise).
    expect(rows[0].querySelector("img")).not.toBeNull();
    expect(rows[1].querySelector("span[aria-hidden]")).not.toBeNull();
    expect(within(rows[2]).getByTestId("status-row-grade")).toHaveTextContent("A-");
    fireEvent.click(screen.getByTestId("status-primary"));
    expect(onAction).toHaveBeenCalledWith("team");
  });

  it("a row with a detail expands inline and offers the open link", () => {
    render(<StatusHeader model={MODEL} />);
    const [first] = screen.getAllByTestId("status-attention-row");
    const toggle = within(first).getByRole("button");
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(within(first).getByText("He is open on the wire.")).toBeInTheDocument();
    expect(within(first).getByRole("link", { name: "Open →" })).toHaveAttribute("href", "/waivers/x");
  });

  it("uses cyan for the one action and never gold", () => {
    render(<StatusHeader model={MODEL} />);
    expect(screen.getByTestId("status-primary").getAttribute("style")).toContain("--color-accent-strong");
    expect(document.body.innerHTML).not.toMatch(/--color-action|--color-premium/);
  });

  it("omits the list and the action when there is nothing to say", () => {
    render(<StatusHeader model={{ ...MODEL, attention: [], stats: [], primary: null, ring: null }} />);
    expect(screen.queryByTestId("status-attention")).toBeNull();
    expect(screen.queryByTestId("status-primary")).toBeNull();
    expect(screen.queryByTestId("status-ring")).toBeNull();
  });
});
