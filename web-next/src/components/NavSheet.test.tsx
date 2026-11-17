import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { NavSheet } from "./NavSheet";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/PlayerQuickViewContext", () => ({
  usePlayerQuickView: () => ({ openPlayer: vi.fn(), closePlayer: vi.fn() }),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, searchLeaguePlayers: vi.fn() } };
});
vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/league-1",
  useParams: () => ({ leagueId: "league-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

function signedIn() {
  vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u1" } } as never } as never);
}

describe("NavSheet (More and Search share it)", () => {
  it("is a labelled dialog with the eyebrow, title, a labelled search field and grouped, described rows", () => {
    signedIn();
    render(<NavSheet open onClose={() => {}} leagueId="league-1" leagueName="Revivalry" />);
    const dialog = screen.getByRole("dialog", { name: "Where to go" });
    expect(within(dialog).getByLabelText("Search destinations and players")).toBeInTheDocument();
    for (const group of ["Revivalry", "GM Tools", "General", "Account"]) expect(within(dialog).getByRole("heading", { name: group })).toBeInTheDocument();
    expect(within(dialog).getByText("Roster, lineup, and team analysis")).toBeInTheDocument();
  });

  it("More opens without focusing the search field; Search opens with it focused", () => {
    signedIn();
    const { unmount } = render(<NavSheet open onClose={() => {}} leagueId="league-1" leagueName="Revivalry" />);
    expect(screen.getByTestId("nav-sheet-search")).not.toHaveFocus();
    unmount();
    render(<NavSheet open onClose={() => {}} leagueId="league-1" leagueName="Revivalry" focusSearch />);
    expect(screen.getByTestId("nav-sheet-search")).toHaveFocus();
  });

  it("filters destinations from the same registry and closes on Escape", () => {
    signedIn();
    const onClose = vi.fn();
    render(<NavSheet open onClose={onClose} leagueId="league-1" leagueName="Revivalry" />);
    fireEvent.change(screen.getByTestId("nav-sheet-search"), { target: { value: "waiver" } });
    expect(screen.getAllByTestId("nav-sheet-row").some((row) => /Waivers/.test(row.textContent ?? ""))).toBe(true);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
  });
});
