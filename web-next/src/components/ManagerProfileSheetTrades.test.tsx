import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const baseDetail = {
  ok: true,
  is_premium: true,
  upsell: null,
  manager: {
    team_name: "Big Dogs",
    owner_handle: "zk",
    headline: null,
    sample: { trades: 6, wire_moves: 2, seasons: 2 },
    signals: {
      posture: { status: "ok", label: "rebuilding", summary: "Leaning rebuild.", sample_size: 6, min_sample: 5, evidence: [] },
    },
  },
};

const trade = {
  transaction_id: "t1",
  season: "2026",
  week: 5,
  date: "2026-10-04",
  partners: ["Rival FC"],
  received: [{ kind: "pick", season: "2026", round: 1, label: "2026 1st" }],
  sent: [{ kind: "player", player_id: "9", name: "Vet WR One", position: "WR", team: "BUF" }],
  grade: { letter: "B+", tone: "positive", confidence: "Medium confidence", timing_label: "Current grade", ratio: 1.1 },
};

async function mountWith(recent_trades: unknown[]) {
  vi.resetModules();
  vi.doMock("@/lib/api", () => ({
    api: { getManagerTendencyDetail: () => Promise.resolve({ ...baseDetail, recent_trades }) },
  }));
  const { ManagerProfileSheet } = await import("./ManagerProfileSheet");
  render(<ManagerProfileSheet leagueId="1" rosterId={3} teamName="Big Dogs" onClose={() => {}} />);
}

describe("ManagerProfileSheet recent trades", () => {
  afterEach(() => vi.doUnmock("@/lib/api"));

  it("renders trades with pick plate, position badge and grade", async () => {
    await mountWith([trade]);
    expect(await screen.findByText("Recent trades")).toBeTruthy();
    expect(screen.getByText("2026 1st")).toBeTruthy();
    expect(screen.getByText("Vet WR One")).toBeTruthy();
    expect(screen.getByText("B+")).toBeTruthy();
    expect(screen.getByText("R1")).toBeTruthy();
    expect(screen.getByText("WR")).toBeTruthy();
  });

  it("omits the grade badge when null and hides the section when empty", async () => {
    await mountWith([{ ...trade, grade: null }]);
    expect(await screen.findByText("Recent trades")).toBeTruthy();
    expect(screen.queryByText("B+")).toBeNull();
  });

  it("hides the section when there are no recent trades", async () => {
    await mountWith([]);
    expect(await screen.findByText("Leaning rebuild.")).toBeTruthy();
    expect(screen.queryByText("Recent trades")).toBeNull();
  });
});
