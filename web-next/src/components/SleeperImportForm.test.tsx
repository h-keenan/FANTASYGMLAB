import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SleeperImportForm } from "./SleeperImportForm";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { trackFeatureUse } from "@/lib/analytics";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      lookupSleeperLeagues: vi.fn(),
      linkSleeperUsername: vi.fn(),
      saveLeague: vi.fn(),
    },
  };
});

describe("SleeperImportForm", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "user-1" } } as never,
      loading: false,
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      deleteAccount: vi.fn(),
      isGuest: false,
    });
    vi.mocked(trackFeatureUse).mockClear();
  });

  it("always shows an explanation of what Sleeper is, with a link to sleeper.com", () => {
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    expect(screen.getByText(/connects to your existing/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /create a free one at sleeper\.com/i })[0]).toHaveAttribute(
      "href",
      "https://sleeper.com",
    );
  });

  it("shows a sleeper.com signup CTA when the username genuinely has no Sleeper account", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: false,
      status: "user_not_found",
      username: "nobody",
      leagues: [],
      message: "No Sleeper account matched that username. Check spelling and try again.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "nobody" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).toHaveTextContent(/no sleeper account matched/i);
    expect(screen.getByRole("alert")).toHaveTextContent(/don't have a sleeper account/i);
  });

  it("does not show the no-account CTA for an unrelated lookup failure", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: false,
      status: "no_eligible_leagues",
      username: "someone",
      leagues: [],
      message: "No eligible leagues found for that username.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(screen.getByRole("alert")).not.toHaveTextContent(/don't have a sleeper account/i);
  });

  // Audit finding, 2026-10-20: this whole flow had zero analytics wiring --
  // the entire League Import funnel step and sleeper_connected had never
  // fired once from web-next. These tests guard the fix.

  it("fires league_import_started on every submit, before the lookup resolves", () => {
    vi.mocked(api.lookupSleeperLeagues).mockReturnValue(new Promise(() => {})); // never resolves
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    expect(trackFeatureUse).toHaveBeenCalledWith("league_import_started");
  });

  it("fires sleeper_connected on a successful lookup even with zero eligible leagues (identity resolved)", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "no_leagues",
      username: "someone",
      leagues: [],
      message: "No eligible leagues found for that username.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackFeatureUse).toHaveBeenCalledWith("sleeper_connected");
    expect(trackFeatureUse).not.toHaveBeenCalledWith("league_import_failed", expect.anything());
  });

  it("does not fire sleeper_connected when the lookup itself fails, and fires league_import_failed with the reason instead", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: false,
      status: "user_not_found",
      username: "nobody",
      leagues: [],
      message: "No Sleeper account matched that username.",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "nobody" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(trackFeatureUse).not.toHaveBeenCalledWith("sleeper_connected");
    expect(trackFeatureUse).toHaveBeenCalledWith("league_import_failed", {
      dedupe: false,
      props: { reason: "user_not_found" },
    });
  });

  it("fires league_import_completed with the real leagueId when exactly one eligible league auto-continues", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "ok",
      username: "someone",
      leagues: [{ league_id: "league-solo", name: "Solo League", season: "2026", total_rosters: 12 }],
      message: "",
    });
    vi.mocked(api.linkSleeperUsername).mockResolvedValue({ ok: true } as never);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 3 });
    const onLeagueChosen = vi.fn();
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("league-solo", "Solo League"));
    expect(trackFeatureUse).toHaveBeenCalledWith("league_import_completed", { leagueId: "league-solo" });
  });

  it("fires league_import_completed with the real leagueId when a league is picked from a multi-league list", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "ok",
      username: "someone",
      leagues: [
        { league_id: "league-a", name: "League A", season: "2026", total_rosters: 12 },
        { league_id: "league-b", name: "League B", season: "2026", total_rosters: 10 },
      ],
      message: "",
    });
    vi.mocked(api.linkSleeperUsername).mockResolvedValue({ ok: true } as never);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 3 });
    const onLeagueChosen = vi.fn();
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getByText("League B")).toBeInTheDocument());
    fireEvent.click(screen.getByText("League B"));

    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("league-b", "League B"));
    expect(trackFeatureUse).toHaveBeenCalledWith("league_import_completed", { leagueId: "league-b" });
  });

  // Bug report, 2026-10-21: a continuing dynasty league gets a new
  // league_id each season it rolls over on Sleeper, so the SAME league can
  // legitimately appear twice here (once per season) -- users were tapping
  // the wrong year's card. The picker must group by season under a visible
  // header, current season first, not render one flat list.
  it("groups leagues by season with the current season first when the same league appears across years", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "ok",
      username: "someone",
      leagues: [
        { league_id: "league-2025", name: "Dynasty Warriors", season: "2025", total_rosters: 12 },
        { league_id: "league-2026", name: "Dynasty Warriors", season: "2026", total_rosters: 12 },
      ],
      message: "",
    });
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() => expect(screen.getAllByText("Dynasty Warriors")).toHaveLength(2));
    const seasonHeaders = [screen.getByText("2026 season"), screen.getByText("2025 season")];
    // 2026 header must appear before 2025 header in document order.
    expect(
      seasonHeaders[0].compareDocumentPosition(seasonHeaders[1]) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("fires league_import_failed when saving the chosen league throws", async () => {
    vi.mocked(api.lookupSleeperLeagues).mockResolvedValue({
      ok: true,
      status: "ok",
      username: "someone",
      leagues: [{ league_id: "league-solo", name: "Solo League", season: "2026", total_rosters: 12 }],
      message: "",
    });
    vi.mocked(api.linkSleeperUsername).mockResolvedValue({ ok: true } as never);
    vi.mocked(api.saveLeague).mockRejectedValue(new Error("network down"));
    render(<SleeperImportForm onLeagueChosen={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Sleeper username"), { target: { value: "someone" } });
    fireEvent.click(screen.getByRole("button", { name: /load my leagues/i }));

    await waitFor(() =>
      expect(trackFeatureUse).toHaveBeenCalledWith("league_import_failed", {
        dedupe: false,
        props: { reason: "exception" },
      }),
    );
  });
});
