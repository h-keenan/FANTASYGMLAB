import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ShellHeader } from "./ShellHeader";
import { resetHeaderChips, setHeaderChips } from "@/lib/headerContext";
import { supabase } from "@/lib/supabase";

/** UI pass 7: the shell header is league identity + a context ribbon on tab pages (no page title), a titled header on detail pages, and the switcher is a sheet. */

const nav = vi.hoisted(() => ({ pathname: "/dashboard/L1" }));
const mockSearchParams = { get: vi.fn() };
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useParams: () => ({ leagueId: "L1" }),
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));
vi.mock("@/lib/useShellNav", () => ({ useShellNav: () => ({ enabled: true, barVisible: true }) }));
vi.mock("@/lib/supabase", () => ({ supabase: { from: vi.fn() } }));
vi.mock("@/context/ValuationLensContext", async () => {
  const actual = await vi.importActual<typeof import("@/context/ValuationLensContext")>("@/context/ValuationLensContext");
  return { ...actual, useValuationLens: () => ({ lens: "Dynasty", setLens: vi.fn() }) };
});

function saved(rows: { league_id: string; league_name: string | null }[], error: unknown = null) {
  vi.mocked(supabase.from).mockReturnValue({ select: vi.fn().mockResolvedValue({ data: rows, error }) } as never);
}

beforeEach(() => {
  nav.pathname = "/dashboard/L1";
  mockSearchParams.get.mockImplementation((k: string) => (k === "name" ? "The Revivalry Dynasty Superflex League of Champions" : null));
  resetHeaderChips();
  saved([{ league_id: "L1", league_name: "The Revivalry Dynasty Superflex League of Champions" }, { league_id: "L2", league_name: "Donk" }]);
});

describe("ShellHeader", () => {
  it("a tab page shows league identity (crest, full wrapping name, lens) and no visible page title", async () => {
    render(<ShellHeader actions={<span>actions</span>} />);
    const identity = screen.getByTestId("league-identity");
    expect(identity).toHaveTextContent("The Revivalry Dynasty Superflex League of Champions");
    expect(identity).toHaveTextContent("Dynasty lens");
    expect(screen.getByTestId("league-crest")).toBeInTheDocument();
    // The page name is for screen readers only (the bottom pill names the page).
    expect(screen.getByTestId("shell-title")).toHaveClass("sr-only");
    await waitFor(() => expect(supabase.from).toHaveBeenCalled());
  });

  it("the ribbon shows the chips the page registered, and folds on scroll", async () => {
    render(<ShellHeader actions={null} />);
    act(() => setHeaderChips({}, [{ key: "wk", text: "Wk 10" }, { key: "rec", text: "7-1" }]));
    expect(screen.getByTestId("header-ribbon")).toHaveTextContent("Wk 10");
    expect(screen.getByTestId("header-ribbon")).toHaveTextContent("7-1");
    const header = screen.getByTestId("shell-header");
    expect(header).toHaveAttribute("data-collapsed", "false");
    act(() => {
      Object.defineProperty(window, "scrollY", { value: 60, configurable: true });
      window.dispatchEvent(new Event("scroll"));
    });
    expect(header).toHaveAttribute("data-collapsed", "true");
    Object.defineProperty(window, "scrollY", { value: 0, configurable: true });
  });

  it("a detail page keeps its title and gets a crest button instead of the identity block", () => {
    nav.pathname = "/gm-plan/L1";
    render(<ShellHeader actions={null} />);
    expect(screen.getByTestId("shell-title")).not.toHaveClass("sr-only");
    expect(screen.getByTestId("shell-title")).toHaveTextContent("GM Plan");
    expect(screen.queryByTestId("league-identity")).toBeNull();
    expect(screen.queryByTestId("header-ribbon")).toBeNull();
  });

  it("tapping the identity opens the switcher sheet with league cards, the connect row and the sample league", async () => {
    render(<ShellHeader actions={null} />);
    fireEvent.click(screen.getByTestId("league-identity"));
    expect(await screen.findByRole("dialog", { name: "Your leagues" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId("league-row")).toHaveLength(2));
    expect(screen.getByRole("link", { name: /Connect a league/ })).toHaveAttribute("href", "/connect-league");
    expect(screen.getByRole("link", { name: /Try the sample league/ })).toHaveAttribute("href", "/sample-league");
    expect(screen.getByRole("link", { name: /Fantasy Sim games/ })).toHaveAttribute("href", "/gm-game");
    // 2 leagues: no search field (it shows from 6).
    expect(screen.queryByRole("searchbox", { name: "Search leagues" })).toBeNull();
  });

  it("shows a clear error with Try again when the league list fails to load", async () => {
    saved([], { message: "boom" });
    render(<ShellHeader actions={null} />);
    fireEvent.click(screen.getByTestId("league-identity"));
    expect(await screen.findByTestId("league-switcher-error")).toHaveTextContent("Couldn't load your other leagues");
    saved([{ league_id: "L1", league_name: "A" }, { league_id: "L2", league_name: "B" }]);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByTestId("league-switcher-error")).toBeNull());
  });

  it("search appears from 6 leagues and filters", async () => {
    saved(Array.from({ length: 7 }, (_, i) => ({ league_id: `X${i}`, league_name: i === 3 ? "Gridiron Gurus" : `League ${i}` })));
    render(<ShellHeader actions={null} />);
    fireEvent.click(screen.getByTestId("league-identity"));
    const search = await screen.findByRole("searchbox", { name: "Search leagues" });
    fireEvent.change(search, { target: { value: "grid" } });
    await waitFor(() => expect(screen.getAllByTestId("league-row")).toHaveLength(1));
  });
});
