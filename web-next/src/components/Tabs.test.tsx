import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Tabs, type TabItem } from "./Tabs";

const make = (calls: string[] = []): TabItem[] => [
  { key: "overview", label: "Overview", render: () => { calls.push("overview"); return <p>Overview body</p>; } },
  { key: "stats", label: "Stats", render: () => { calls.push("stats"); return <p>Stats body</p>; } },
  { key: "history", label: "History", count: 2, render: () => <p>History body</p> },
];

describe("shared Tabs", () => {
  afterEach(() => window.sessionStorage.clear());

  it("renders only the open tab's panel and wires tab to tabpanel", () => {
    const calls: string[] = [];
    render(<Tabs id="t1" tabs={make(calls)} ariaLabel="Sections" />);
    expect(screen.getByRole("tablist", { name: "Sections" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Overview body")).toBeInTheDocument();
    expect(screen.queryByText("Stats body")).toBeNull();
    expect(calls).not.toContain("stats"); // lazy: a tab costs nothing until picked
    const panel = screen.getByRole("tabpanel");
    expect(panel).toHaveAttribute("aria-labelledby", screen.getByRole("tab", { name: "Overview" }).id);
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-controls", panel.id);
  });

  it("switches panels, slides in from the side moved toward, and shows the count", () => {
    render(<Tabs id="t2" tabs={make()} />);
    fireEvent.click(screen.getByRole("tab", { name: "Stats" }));
    expect(screen.getByText("Stats body")).toBeInTheDocument();
    expect(screen.queryByText("Overview body")).toBeNull();
    expect(screen.getByRole("tabpanel")).toHaveAttribute("data-dir", "1");
    fireEvent.click(screen.getByRole("tab", { name: "Overview" }));
    expect(screen.getByRole("tabpanel")).toHaveAttribute("data-dir", "-1");
    expect(screen.getByLabelText("2 new")).toBeInTheDocument();
  });

  it("remembers the last tab for the session per surface id, and a different id is independent", () => {
    const first = render(<Tabs id="pqv" tabs={make()} />);
    fireEvent.click(screen.getByRole("tab", { name: /History/ }));
    first.unmount();
    render(<Tabs id="pqv" tabs={make()} />);
    expect(screen.getByRole("tab", { name: /History/ })).toHaveAttribute("aria-selected", "true");
    render(<Tabs id="other" tabs={make()} />);
    expect(screen.getAllByRole("tab", { name: "Overview", selected: true })).toHaveLength(1);
  });

  it("falls back when the remembered tab no longer exists, and survives blocked storage", () => {
    window.sessionStorage.setItem("fgl:tab:gone", "scouting");
    render(<Tabs id="gone" tabs={make()} />);
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<Tabs id="blocked" tabs={make()} initial="stats" />);
    expect(screen.getAllByText("Stats body").length).toBeGreaterThan(0);
    spy.mockRestore();
  });

  it("arrow keys move between tabs", () => {
    render(<Tabs id="keys" tabs={make()} />);
    screen.getByRole("tab", { name: "Overview" }).focus();
    fireEvent.keyDown(screen.getByRole("tablist"), { key: "ArrowRight" });
    expect(screen.getByRole("tab", { name: "Stats" })).toHaveAttribute("aria-selected", "true");
  });
});
