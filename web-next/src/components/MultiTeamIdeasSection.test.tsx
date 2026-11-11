import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import type { MultiTeamIdea, MultiTeamIdeasResponse } from "@/lib/multiTeamIdeas";

import { MultiTeamIdeasSection } from "./MultiTeamIdeasSection";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getMultiTeamTradeIdeas: vi.fn() } };
});
vi.mock("@/lib/shareCard/clientRender", () => ({ renderMultiTradeCardBlob: vi.fn() }));

const getIdeas = api.getMultiTeamTradeIdeas as unknown as ReturnType<typeof vi.fn>;

function team(id: string, name: string, over: Record<string, unknown> = {}) {
  return {
    roster_id: id,
    team_name: name,
    is_perspective: id === "1",
    sends: [{ type: "player", id: `s${id}`, label: `Sent ${id}`, position: "RB", team: "SF", to_roster_id: "2", to_team_name: "B" }],
    receives: [{ type: "player", id: `r${id}`, label: `Got ${id}`, position: "WR", team: "SF", from_roster_id: "3", from_team_name: "C" }],
    verdict: { ui_verdict: "Fair" },
    trade_score: 100,
    market_delta: 120,
    lineup_delta: { per_week: 2.4 },
    tone: "fair",
    outcome: "even",
    why: [{ factor: "need", text: `${name} fills a WR need.` }],
    ...over,
  };
}

const IDEA = {
  id: "m3-abc",
  headline: "Team B + Team C: you get Got 1, you send Sent 1",
  teams: [team("1", "Team A"), team("2", "Team B"), team("3", "Team C")],
  flows: [],
  partners: [],
  user: { roster_id: "1", trade_score: 100, market_delta: 120, lineup_delta: { per_week: 2.4 }, outcome: "even" },
  summary: {},
  variant: { edits: 1, note: "One added piece brings every team to fair." },
  analyzer_request: {
    transfers: [
      { type: "player", id: "s1", from_roster_id: "1", to_roster_id: "2" },
      { type: "player", id: "s2", from_roster_id: "2", to_roster_id: "3" },
      { type: "pick", id: "2027:1:3", from_roster_id: "3", to_roster_id: "1" },
    ],
    perspective_roster_id: "1",
  },
} as unknown as MultiTeamIdea;

function renderSection() {
  return render(<MultiTeamIdeasSection leagueId="league-1" leagueName="Dynasty Overlords" lens="Dynasty" />);
}

describe("MultiTeamIdeasSection", () => {
  beforeEach(() => {
    getIdeas.mockReset();
  });

  it("shows a skeleton while the search runs, then the ideas", async () => {
    let resolve!: (value: MultiTeamIdeasResponse) => void;
    getIdeas.mockReturnValue(new Promise<MultiTeamIdeasResponse>((r) => (resolve = r)));
    renderSection();
    expect(screen.getByTestId("multi-team-ideas-skeleton")).toHaveAttribute("aria-busy", "true");
    resolve({ ideas: [IDEA], idea_count: 1, locked: false });
    expect(await screen.findByTestId("multi-team-idea")).toBeInTheDocument();
    expect(screen.queryByTestId("multi-team-ideas-skeleton")).toBeNull();
    expect(getIdeas).toHaveBeenCalledWith("league-1", "Dynasty");
  });

  it("lists every team with its verdict and why, and opens the Analyzer prefilled", async () => {
    getIdeas.mockResolvedValue({ ideas: [IDEA], idea_count: 1, locked: false });
    renderSection();
    await screen.findByTestId("multi-team-idea");
    const lines = screen.getAllByTestId("idea-team-line");
    expect(lines).toHaveLength(3);
    expect(lines[0]).toHaveTextContent("You");
    expect(lines[0]).toHaveTextContent("Gets Got 1. Sends Sent 1.");
    expect(lines[0]).toHaveTextContent("Team A fills a WR need.");
    expect(screen.getByTestId("idea-you-delta")).toHaveTextContent("value +120, lineup +2.4 pts a week");
    expect(screen.getAllByText("One added piece brings every team to fair.").length).toBeGreaterThan(0);
    const open = screen.getByRole("link", { name: "Open in Analyzer" });
    expect(open.getAttribute("href")).toBe(
      "/trade-analyzer/league-1?name=Dynasty+Overlords&multi=player~1~2~s1,player~2~3~s2,pick~3~1~2027:1:3",
    );
    expect(screen.getByRole("button", { name: /Share the pitch/ })).toBeInTheDocument();
  });

  it("shows Free a locked teaser with the count and no idea details", async () => {
    getIdeas.mockResolvedValue({ ideas: [], idea_count: 3, locked: true, is_premium: false, upsell: { title: "See 3-team trade ideas", body: "Pro finds three-way deals." } });
    renderSection();
    expect(await screen.findByText("See 3-team trade ideas")).toBeInTheDocument();
    expect(screen.getByTestId("paid-preview-example")).toHaveTextContent("3 three-team deals fit your league");
    expect(screen.queryByTestId("multi-team-idea")).toBeNull();
    expect(screen.queryByRole("link", { name: "Open in Analyzer" })).toBeNull();
  });

  it("says so plainly when no deal works, and when trading is closed", async () => {
    getIdeas.mockResolvedValue({ ideas: [], idea_count: 0, locked: false, reason: "no_fit" });
    const first = renderSection();
    expect(await screen.findByText("No 3-team deals right now")).toBeInTheDocument();
    first.unmount();
    getIdeas.mockResolvedValue({ ideas: [], idea_count: 0, locked: false, reason: "trade_deadline_passed", message: "Your league's trade deadline has passed." });
    renderSection();
    expect(await screen.findByText("Trading is closed")).toBeInTheDocument();
  });

  it("shows a friendly busy error and retries from the Try again button", async () => {
    getIdeas.mockRejectedValueOnce(Object.assign(new Error("busy"), { status: 503, code: "server_busy" }));
    renderSection();
    expect(await screen.findByRole("alert")).toHaveTextContent("FantasyDesk is busy right now");
    getIdeas.mockResolvedValue({ ideas: [IDEA], idea_count: 1, locked: false });
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByTestId("multi-team-idea")).toBeInTheDocument());
    expect(getIdeas).toHaveBeenCalledTimes(2);
  });
});
