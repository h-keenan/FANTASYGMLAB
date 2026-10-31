import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { CommissionerContent } from "./CommissionerContent";
import { api } from "@/lib/api";
import type { CommissionerIntegrityResponse, IntegrityTeam } from "@/lib/commissionerIntegrity";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getCommissionerIntegrity: vi.fn() } };
});

const tanker: IntegrityTeam = {
  roster_id: 6, team_name: "Tanker", owner_name: "Tom", band: "strong", band_label: "Strong signals", score: 0.88,
  confidence: "high", interpretation: "possible_tanking", context: "eliminated",
  weeks: { evaluated: 6, flagged: 5, longest_streak: 5, latest_streak: 5 },
  evidence: [{ kind: "lineup", week: 6, text: "Week 6: started WR4 over WR1." }],
  innocent_explanations: ["Late injury designations."],
  series: [{ week: 1, actual: 100, best_possible: 110, efficiency: 0.9, flagged: false }],
};
const fine: IntegrityTeam = { ...tanker, roster_id: 1, team_name: "Alpha", band: "fine", band_label: "Lineup looks fine", interpretation: "none", score: 0.03 };

function body(overrides: Partial<CommissionerIntegrityResponse> = {}): CommissionerIntegrityResponse {
  return { ok: true, reason: "", is_premium: true, upsell: null, weeks_evaluated: 6, teams: [tanker, fine], collusion: [], inactive: [], limits: ["Sleeper does not say who was injured."], ...overrides };
}

describe("CommissionerContent", () => {
  beforeEach(() => vi.mocked(api.getCommissionerIntegrity).mockReset());

  it("shows flagged teams with evidence and innocent explanations, others collapsed", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body());
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("Tanker")).toBeTruthy();
    expect(screen.getByText("Strong signals")).toBeTruthy();
    expect(screen.getByText("Week 6: started WR4 over WR1.")).toBeTruthy();
    expect(screen.getByText("Late injury designations.")).toBeTruthy();
    expect(screen.queryByText("Alpha")).toBeNull();
    fireEvent.click(screen.getByText("Show 1 team"));
    expect(screen.getByText("Alpha")).toBeTruthy();
  });

  it("re-requests with the draft-order rule the commissioner picks", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body());
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    await screen.findByText("Tanker");
    fireEvent.click(screen.getByText("Worst record picks first"));
    await waitFor(() => expect(api.getCommissionerIntegrity).toHaveBeenLastCalledWith("L1", "record"));
  });

  it("is honest in early season and for unsupported platforms", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body({ reason: "not_enough_weeks", teams: [] }));
    const { unmount } = render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText(/at least three completed/)).toBeTruthy();
    unmount();
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(body({ reason: "unsupported_platform", teams: [] }));
    render(<CommissionerContent leagueId="L2" leagueName="Other" />);
    expect(await screen.findByText(/only available for Sleeper leagues/)).toBeTruthy();
  });

  it("shows the upsell for a Free account", async () => {
    vi.mocked(api.getCommissionerIntegrity).mockResolvedValue(
      body({ is_premium: false, teams: [], upsell: { title: "Spot tanking early", body: "Pro feature." } }),
    );
    render(<CommissionerContent leagueId="L1" leagueName="My League" />);
    expect(await screen.findByText("Spot tanking early")).toBeTruthy();
  });
});
