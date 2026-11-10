import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SavedLeaguesSection } from "./SavedLeaguesSection";

const mocks = vi.hoisted(() => ({
  rows: [] as Array<{ league_id: string; league_name: string | null }>,
  remove: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: () => ({ select: () => ({ order: () => Promise.resolve({ data: mocks.rows, error: null }) }) }),
  },
}));
vi.mock("@/lib/api", () => ({ api: { removeSavedLeague: (id: string) => mocks.remove(id) } }));

describe("SavedLeaguesSection", () => {
  beforeEach(() => {
    mocks.rows = [
      { league_id: "1", league_name: "Alpha" },
      { league_id: "2", league_name: "Beta" },
    ];
    mocks.remove.mockReset().mockResolvedValue({ ok: true, reason: "" });
  });

  it("renders nothing when there are no saved leagues", async () => {
    mocks.rows = [];
    const { container } = render(<SavedLeaguesSection />);
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it("asks for confirmation, then removes through the API", async () => {
    render(<SavedLeaguesSection />);
    expect(await screen.findByText("Alpha")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Not your league? Remove" })[0]);
    expect(mocks.remove).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Confirm remove" }));
    await waitFor(() => expect(screen.queryByText("Alpha")).not.toBeInTheDocument());
    expect(mocks.remove).toHaveBeenCalledWith("1");
    expect(screen.getByText("Beta")).toBeInTheDocument();
  });

  it("keeps the league and shows an error when the API refuses", async () => {
    mocks.remove.mockResolvedValue({ ok: false, reason: "not_available" });
    render(<SavedLeaguesSection />);
    fireEvent.click((await screen.findAllByRole("button", { name: "Not your league? Remove" }))[0]);
    fireEvent.click(screen.getByRole("button", { name: "Confirm remove" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
  });
});
