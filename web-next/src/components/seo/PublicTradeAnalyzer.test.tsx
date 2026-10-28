import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PublicTradeAnalyzer, mergeSearch } from "./PublicTradeAnalyzer";
import type { TradeBoard } from "@/lib/seo/tradeAnalyzer";

const trackUse = vi.fn();
vi.mock("@/lib/analytics", () => ({ trackUse: (...args: unknown[]) => trackUse(...args) }));

const BOARD: TradeBoard = {
  updated: "2026-10-27T00:00:00Z",
  tepAvailable: true,
  players: [
    { id: "1", name: "Ja'Marr Chase", pos: "WR", team: "CIN", age: 26, inj: null, v: [9000, 9500, 9000, 9500] },
    { id: "2", name: "Josh Allen", pos: "QB", team: "BUF", age: 30, inj: null, v: [7000, 9800, 7000, 9800] },
    { id: "3", name: "Brock Bowers", pos: "TE", team: "LV", age: 23, inj: null, v: [6500, 6600, 7400, 7500] },
    { id: "4", name: "Josh Jacobs", pos: "RB", team: "GB", age: 28, inj: "Questionable", v: [3000, 3100, 3000, 3100] },
  ],
};

function mockFetch(ok = true, body: unknown = BOARD) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok, status: ok ? 200 : 503, json: async () => body } as Response);
}

async function renderLoaded() {
  render(<PublicTradeAnalyzer />);
  await screen.findByLabelText("Search players for You send");
}

function addPlayer(side: "You send" | "You get", query: string, name: string) {
  const input = screen.getByLabelText(`Search players for ${side}`);
  fireEvent.focus(input);
  fireEvent.change(input, { target: { value: query } });
  const listbox = screen.getByRole("listbox", { name: `${side} suggestions` });
  fireEvent.mouseDown(within(listbox).getByText(name));
}

describe("PublicTradeAnalyzer", () => {
  beforeEach(() => {
    trackUse.mockClear();
    window.history.replaceState(null, "", "/trade-analyzer");
  });
  afterEach(() => vi.restoreAllMocks());

  it("searches, adds to each side and shows a value-only verdict with the soft gate", async () => {
    mockFetch();
    await renderLoaded();
    addPlayer("You send", "jacobs", "Josh Jacobs");
    addPlayer("You get", "chase", "Ja'Marr Chase");

    const result = screen.getByTestId("trade-result");
    expect(result).toHaveTextContent("Value-only verdict");
    expect(result).toHaveTextContent("Lopsided in your favor");
    expect(result).toHaveTextContent("+6,000");
    expect(result).toHaveTextContent("Josh Jacobs (Questionable)");
    expect(document.querySelectorAll(".lean-bar-track").length).toBe(1);

    expect(screen.queryByTestId("trade-gate")).toBeNull();
    const teaser = screen.getByTestId("roster-teaser");
    const cta = within(teaser).getByRole("link", { name: "See how this trade affects MY team" });
    expect(cta.getAttribute("href")).toContain("utm_campaign=public_trade_analyzer_verdict");
    expect(within(teaser).getByRole("link", { name: "Try a sample league first" }).getAttribute("href")).toMatch(/^\/sample-league\?/);
    expect(teaser).toHaveTextContent("Roster-aware verdict");
    expect(teaser).toHaveTextContent("Lineup impact");
    expect(teaser).toHaveTextContent("Partner fit");
    expect(teaser).toHaveTextContent("Counter-offers");
    // Trade-specific: names the players actually entered.
    expect(teaser).toHaveTextContent("sending Josh Jacobs");
    expect(teaser).toHaveTextContent("has Ja'Marr Chase");
  });

  it("shows the generic account gate before a trade is entered", async () => {
    mockFetch();
    await renderLoaded();
    const gate = screen.getByTestId("trade-gate");
    expect(within(gate).getByRole("link", { name: "Get a roster-aware verdict" })).toBeInTheDocument();
    expect(screen.queryByTestId("roster-teaser")).toBeNull();
  });

  it("carries the entered trade through sign-up and tags the copied link", async () => {
    mockFetch();
    window.localStorage.clear();
    await renderLoaded();
    addPlayer("You send", "jacobs", "Josh Jacobs");
    addPlayer("You get", "chase", "Ja'Marr Chase");
    fireEvent.click(within(screen.getByTestId("roster-teaser")).getByRole("link", { name: "See how this trade affects MY team" }));
    const stored = JSON.parse(window.localStorage.getItem("fd_pending_bridge_trade_v1") || "{}");
    expect(stored).toMatchObject({ a: ["4"], b: ["1"] });
    // Names and values are never stored, only the ids already in the shared URL.
    expect(JSON.stringify(stored)).not.toMatch(/Jacobs|Chase/);

    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    fireEvent.click(screen.getByRole("button", { name: "Copy share link" }));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(String(writeText.mock.calls[0][0])).toContain("utm_source=share&utm_medium=copy_link&utm_campaign=public_trade_analyzer");
  });

  it("does not store the trade when the visitor takes the sample league instead", async () => {
    mockFetch();
    window.localStorage.clear();
    await renderLoaded();
    addPlayer("You send", "jacobs", "Josh Jacobs");
    addPlayer("You get", "chase", "Ja'Marr Chase");
    fireEvent.click(within(screen.getByTestId("roster-teaser")).getByRole("link", { name: "Try a sample league first" }));
    expect(window.localStorage.getItem("fd_pending_bridge_trade_v1")).toBeNull();
  });

  it("recomputes for Superflex and TE premium and never sends names or ids to analytics", async () => {
    mockFetch();
    await renderLoaded();
    addPlayer("You send", "allen", "Josh Allen");
    addPlayer("You get", "chase", "Ja'Marr Chase");
    expect(screen.getByTestId("trade-result")).toHaveTextContent("Lopsided in your favor");

    fireEvent.click(screen.getByRole("button", { name: "Superflex" }));
    expect(screen.getByTestId("trade-result")).toHaveTextContent("Slight edge to them");

    expect(trackUse).toHaveBeenCalledWith(
      "public_trade_analyzer",
      "player_added",
      expect.objectContaining({ props: expect.objectContaining({ source_surface: "public_trade_analyzer" }) }),
    );
    const serialized = JSON.stringify(trackUse.mock.calls);
    expect(serialized).not.toMatch(/Chase|Allen|Jacobs/);
    expect(trackUse.mock.calls.some((c) => c[1] === "result_viewed")).toBe(true);
  });

  it("restores a shared ?a=&b=&f= link and keeps the URL in sync and shareable", async () => {
    window.history.replaceState(null, "", "/trade-analyzer?utm_source=x&a=4&b=1&f=sf");
    mockFetch();
    await renderLoaded();
    expect(screen.getByRole("button", { name: "Superflex" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Remove Josh Jacobs from You send" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove Ja'Marr Chase from You get" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Remove Josh Jacobs from You send" }));
    await waitFor(() => expect(window.location.search).not.toContain("a="));
    expect(window.location.search).toContain("utm_source=x");
    expect(window.location.search).toContain("b=1");
  });

  it("supports keyboard selection in the combobox", async () => {
    mockFetch();
    await renderLoaded();
    const input = screen.getByLabelText("Search players for You send");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "josh" } });
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(screen.getByRole("button", { name: /Remove Josh Jacobs from You send/ })).toBeInTheDocument();
  });

  it("disables TE premium when the premium boards are unavailable", async () => {
    mockFetch(true, { ...BOARD, tepAvailable: false });
    await renderLoaded();
    expect(screen.getByLabelText("Tight end premium")).toBeDisabled();
  });

  it("shows a retry state when values fail to load", async () => {
    mockFetch(false, {});
    render(<PublicTradeAnalyzer />);
    expect(await screen.findByRole("alert")).toHaveTextContent("did not load");
    mockFetch();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    });
    await screen.findByLabelText("Search players for You send");
  });

  it("mergeSearch keeps foreign params and replaces only ours", () => {
    expect(mergeSearch("?utm_source=g&a=1&f=sf", "?b=2")).toBe("?utm_source=g&b=2");
    expect(mergeSearch("?a=1", "")).toBe("");
  });
});
