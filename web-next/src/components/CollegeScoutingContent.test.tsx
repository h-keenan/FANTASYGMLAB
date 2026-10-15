import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CollegeScoutingContent } from "./CollegeScoutingContent";
import type { CollegeProspect, CollegeProspectsResponse } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      addProspectToWatchlist: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      removeProspectFromWatchlist: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      submitScoutingReport: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
      deleteScoutingReport: vi.fn().mockResolvedValue({ ok: true, reason: "" }),
    },
  };
});

function prospect(overrides: Partial<CollegeProspect>): CollegeProspect {
  return {
    id: "pr1",
    name: "Test Prospect",
    position: "WR",
    school: "Ole Miss",
    draft_year: 2026,
    aggregate: { avg_grade: null, scout_count: 0, avg_round_projection: null },
    my_report: null,
    on_watchlist: false,
    ...overrides,
  };
}

function response(prospects: CollegeProspect[], overrides: Partial<CollegeProspectsResponse> = {}): CollegeProspectsResponse {
  return { ok: true, prospects, catalog_available: true, reason: "", ...overrides };
}

describe("CollegeScoutingContent", () => {
  it("renders a prospect's identity, class, and the shared aggregate", () => {
    const data = response([
      prospect({
        name: "Big Arm QB",
        position: "QB",
        school: "Ohio State",
        draft_year: 2026,
        aggregate: { avg_grade: 4.2, scout_count: 5, avg_round_projection: 1.4 },
      }),
    ]);
    render(<CollegeScoutingContent data={data} />);

    expect(screen.getByRole("heading", { name: "College Scouting" })).toBeInTheDocument();
    expect(screen.getByText("Big Arm QB")).toBeInTheDocument();
    expect(screen.getByText("Ohio State · 2026 class")).toBeInTheDocument();
    expect(screen.getByText("4.2 avg · 5 scouts")).toBeInTheDocument();
  });

  it("shows 'Not yet scouted' and no signal meter for a prospect with zero reports", () => {
    const data = response([prospect({})]);
    render(<CollegeScoutingContent data={data} />);

    expect(screen.getByText("Not yet scouted")).toBeInTheDocument();
    expect(screen.queryByText("Signal")).not.toBeInTheDocument();
  });

  it("shows the caller's own grade when they've already scouted this prospect", () => {
    const data = response([
      prospect({ my_report: { grade: 4, round_projection: 2, note: "Good hands" } }),
    ]);
    render(<CollegeScoutingContent data={data} />);

    expect(screen.getByText("Your grade: 4/5")).toBeInTheDocument();
  });

  it("shows the empty catalog state when there are no prospects but the catalog is reachable", () => {
    render(<CollegeScoutingContent data={response([])} />);

    expect(screen.getByText("No prospects yet")).toBeInTheDocument();
    expect(screen.getByText("Check back soon — the prospect pool is still growing.")).toBeInTheDocument();
  });

  it("shows the unreachable-catalog state when catalog_available is false", () => {
    render(<CollegeScoutingContent data={response([], { catalog_available: false })} />);

    expect(screen.getByText("College Scouting isn't connected yet")).toBeInTheDocument();
  });

  it("filters to My Watchlist and shows its own empty state", () => {
    const data = response([prospect({ name: "Not Followed", on_watchlist: false })]);
    render(<CollegeScoutingContent data={data} />);

    fireEvent.click(screen.getByRole("button", { name: "My Watchlist" }));

    expect(screen.queryByText("Not Followed")).not.toBeInTheDocument();
    expect(screen.getByText("No prospects followed yet")).toBeInTheDocument();
  });

  it("calls addProspectToWatchlist and flips the button to Unfollow when Follow is pressed", () => {
    const data = response([prospect({ name: "Follow Me", on_watchlist: false })]);
    render(<CollegeScoutingContent data={data} />);

    fireEvent.click(screen.getByRole("button", { name: "Follow" }));

    expect(api.addProspectToWatchlist).toHaveBeenCalledWith("pr1");
    expect(screen.getByRole("button", { name: "Unfollow" })).toBeInTheDocument();
  });

  it("submits a grade through the expanded form and shows the saved confirmation", async () => {
    const data = response([prospect({ name: "Grade Me" })]);
    render(<CollegeScoutingContent data={data} />);

    fireEvent.click(screen.getByRole("button", { name: "Scout Grade Me" }));
    fireEvent.click(screen.getByRole("button", { name: "4" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit grade" }));

    expect(api.submitScoutingReport).toHaveBeenCalledWith("pr1", {
      grade: 4,
      round_projection: null,
      note: "",
    });
    expect(await screen.findByText("Saved — thanks for scouting.")).toBeInTheDocument();
  });

  it("warns instead of saving when Submit is pressed with no grade chosen", () => {
    const data = response([prospect({ name: "No Grade Yet" })]);
    render(<CollegeScoutingContent data={data} />);

    fireEvent.click(screen.getByRole("button", { name: "Scout No Grade Yet" }));
    const submit = screen.getByRole("button", { name: "Submit grade" });
    expect(submit).toBeDisabled();
    expect(api.submitScoutingReport).not.toHaveBeenCalled();
  });

  it("calls deleteScoutingReport when Remove my report is pressed", () => {
    const data = response([
      prospect({ name: "Remove Me", my_report: { grade: 3, round_projection: null, note: "" } }),
    ]);
    render(<CollegeScoutingContent data={data} />);

    fireEvent.click(screen.getByRole("button", { name: "Edit your grade — Remove Me" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove my report" }));

    expect(api.deleteScoutingReport).toHaveBeenCalledWith("pr1");
  });
});
