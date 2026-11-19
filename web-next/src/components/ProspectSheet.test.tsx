import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ProspectSheet } from "./ProspectSheet";
import { draftFromProspect } from "./ProspectReportForm";
import type { CollegeProspect } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getProspectProfile: vi.fn(), getMe: vi.fn() } };
});

const prospect: CollegeProspect = {
  id: "2027-arch-manning-texas",
  name: "Arch Manning",
  position: "QB",
  school: "Texas",
  draft_year: 2027,
  aggregate: { avg_grade: 4.2, scout_count: 5, avg_round_projection: 1.4 },
  my_report: null,
  on_watchlist: false,
};

const profile = {
  ok: true,
  prospect: { id: prospect.id, name: "Arch Manning", position: "QB", school: "Texas", draft_year: 2027, drafted: false, nfl_team: null, draft_round: null, draft_pick: null, sleeper_player_id: null },
  bio: { class_year: 3, height_in: 76, weight_lb: 220, hometown: "New Orleans, LA", school_logo_url: null },
  stats_available: true,
  seasons: [
    { season: 2026, team: "Texas", passing: { yds: 3000, td: 25, int: 5, pct: 0.656 }, fantasy_points: 248 },
    { season: 2025, team: "Texas", passing: { yds: 900, td: 9, int: 2 }, fantasy_points: 54 },
  ],
  weekly: { season: 2026, games: [{ week: 1, opponent: "Ohio State", passing: { yds: 250, td: 2 }, fantasy_points: 18 }, { week: 2, opponent: "Kansas", passing: { yds: 300, td: 3 }, fantasy_points: 24 }] },
  fantasy_rules: "PPR rules.",
  advanced: null,
  advanced_available: true,
  advanced_locked: true,
  recruiting: { year: 2023, stars: 5, rating: 0.9998, national_rank: 1, high_school: "Isidore Newman", city: "New Orleans", state: "LA" },
  adp: null,
  source: { name: "College Football Data", url: "https://collegefootballdata.com/player/1", as_of: "2026-11-16" },
};

function renderSheet() {
  return render(
    <ProspectSheet
      prospect={prospect}
      draft={draftFromProspect(prospect)}
      flash={null}
      busy={false}
      onDraftChange={vi.fn()}
      onSubmit={vi.fn()}
      onRemove={vi.fn().mockResolvedValue(true)}
      onToggleWatchlist={vi.fn()}
      onClose={vi.fn()}
    />,
  );
}

describe("ProspectSheet", () => {
  beforeEach(() => {
    window.sessionStorage.clear(); // the sheet remembers its last tab for the session
    vi.mocked(api.getProspectProfile).mockResolvedValue(profile as never);
    vi.mocked(api.getMe).mockResolvedValue({ user: { entitlement: "free", profile_status: "ok" } } as never);
  });

  it("shows the header, crowd grade and the Overview with your report form", async () => {
    renderSheet();
    expect(await screen.findByText(`Class of 2027 · 6'4" · 220 lb`)).toBeInTheDocument();
    expect(screen.getByText("Arch Manning")).toBeInTheDocument();
    expect(screen.getByTestId("prospect-grade-tile")).toHaveTextContent("4.2");
    expect(screen.getByTestId("prospect-overview")).toBeInTheDocument();
    expect(screen.getByTestId("prospect-report-form")).toBeInTheDocument();
    expect(screen.getByText("No ADP yet")).toBeInTheDocument();
  });

  it("Stats: season lines and the weekly chart from CFBD, with the source cited, and advanced locked for Free", async () => {
    renderSheet();
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));
    expect(await screen.findByTestId("prospect-season-stats")).toHaveTextContent("3,000");
    expect(screen.getByTestId("prospect-weekly")).toBeInTheDocument();
    expect(screen.getByTestId("prospect-game-log")).toHaveTextContent("Wk 2 vs Kansas");
    expect(screen.getByTestId("prospect-source")).toHaveTextContent("College Football Data");
    expect(screen.getByTestId("prospect-advanced-lock")).toHaveTextContent("Pro");
    expect(screen.queryByTestId("prospect-advanced")).not.toBeInTheDocument();
    // season switch
    fireEvent.click(screen.getByRole("tab", { name: "2025" }));
    expect(screen.getByTestId("prospect-season-stats")).toHaveTextContent("900");
  });

  it("Stats: the advanced lock comes from the profile itself, so a failed /me never blanks it", async () => {
    vi.mocked(api.getMe).mockRejectedValue(new Error("me down"));
    renderSheet();
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));
    expect(await screen.findByTestId("prospect-advanced-lock")).toHaveTextContent("Pro");
  });

  it("Stats: Pro sees the advanced metrics, no lock", async () => {
    vi.mocked(api.getMe).mockResolvedValue({ user: { entitlement: "premium", profile_status: "ok" } } as never);
    vi.mocked(api.getProspectProfile).mockResolvedValue({ ...profile, advanced_locked: false, advanced: { season: 2026, ppa: { avg: { all: 0.42 } }, usage: { overall: 0.31 } } } as never);
    renderSheet();
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));
    expect(await screen.findByTestId("prospect-advanced")).toHaveTextContent("+0.42");
    expect(screen.queryByTestId("prospect-advanced-lock")).not.toBeInTheDocument();
  });

  it("Stats: with no ingest yet it says so, no invented numbers", async () => {
    vi.mocked(api.getProspectProfile).mockResolvedValue({ ok: true, seasons: [], weekly: null, advanced: null, recruiting: null, adp: null, bio: {}, stats_available: false } as never);
    renderSheet();
    fireEvent.click(await screen.findByRole("tab", { name: "Stats" }));
    expect(await screen.findByText("No college stats yet")).toBeInTheDocument();
  });

  it("Profile: recruiting stars, rank and hometown", async () => {
    renderSheet();
    fireEvent.click(await screen.findByRole("tab", { name: "Profile" }));
    const panel = await screen.findByTestId("prospect-profile");
    expect(panel).toHaveTextContent("5-star");
    expect(panel).toHaveTextContent("#1");
    expect(panel).toHaveTextContent("New Orleans, LA");
  });

  it("shows the rookie ADP when a snapshot has one", async () => {
    vi.mocked(api.getProspectProfile).mockResolvedValue({ ...profile, adp: { adp: 1.4, adp_formatted: "1.04", label: "1QB ADP", source: { source: "Fantasy Football Calculator", url: "x", as_of: "2027-04-20" } } } as never);
    renderSheet();
    expect(await screen.findByText("1.04")).toBeInTheDocument();
    expect(screen.getByTestId("prospect-adp-source")).toHaveTextContent("Fantasy Football Calculator");
  });
});
