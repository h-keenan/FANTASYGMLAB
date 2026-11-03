import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerNewsTab } from "./PlayerNewsTab";
import { api, type NewsItem, type PlayerAvailability } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getPlayerNews: vi.fn() } };
});

const nowSec = () => Date.now() / 1000;

function story(n: number, overrides: Partial<NewsItem> = {}): NewsItem {
  return {
    title: `Story ${n}`,
    link: `https://example.com/${n}`,
    source: "ESPN",
    summary: `Snippet ${n}`,
    published_ts: nowSec() - n * 3600,
    event_type: "transaction",
    speculative: false,
    ...overrides,
  };
}

const out: PlayerAvailability = {
  status: "IR",
  label: "Injured Reserve",
  severity: "out",
  unavailable: true,
  body_part: "Hamstring",
  report: null,
  return_note: "No return date reported",
};

describe("PlayerNewsTab", () => {
  beforeEach(() => {
    vi.mocked(api.getPlayerNews).mockReset();
  });

  it("shows a skeleton while loading", () => {
    vi.mocked(api.getPlayerNews).mockReturnValue(new Promise(() => {}));
    render(<PlayerNewsTab playerId="p1" availability={null} />);
    expect(screen.getByTestId("player-news-skeleton")).toBeInTheDocument();
  });

  it("lists stories grouped by day with source, snippet, link and impact tag", async () => {
    vi.mocked(api.getPlayerNews).mockResolvedValue({
      ok: true,
      items: [story(1, { event_type: "injury/status" }), story(2, { also_reported_by: [{ source: "RotoWire", link: "https://r/2" }] })],
      injury_item: null,
      has_more: false,
      next_offset: null,
    });
    render(<PlayerNewsTab playerId="p1" availability={null} />);
    expect(await screen.findByText("Story 1")).toBeInTheDocument();
    expect(screen.getByText("Snippet 1")).toBeInTheDocument();
    expect(screen.getAllByTestId("news-event-tag").map((el) => el.textContent)).toEqual(["Injury / Status", "Transaction"]);
    expect(screen.getByTestId("news-also-reported")).toHaveTextContent("Also reported by RotoWire");
    expect(screen.getByLabelText("Story 1").closest("a")).toHaveAttribute("href", "https://example.com/1");
    expect(screen.queryByText("Load more news")).not.toBeInTheDocument();
  });

  it("pins the availability and injury report on top without repeating it in the list", async () => {
    const injury = story(1, { title: "Out with a hamstring tear", event_type: "injury/status" });
    vi.mocked(api.getPlayerNews).mockResolvedValue({ ok: true, items: [injury, story(2)], injury_item: injury });
    render(<PlayerNewsTab playerId="p1" availability={out} />);
    const pinned = await screen.findByTestId("pqv-availability");
    expect(pinned).toHaveTextContent("Injured Reserve");
    expect(pinned).toHaveTextContent("Hamstring");
    expect(screen.getAllByText("Out with a hamstring tear")).toHaveLength(1);
    expect(screen.getByText("Story 2")).toBeInTheDocument();
  });

  it("loads more with the next offset and appends without duplicates", async () => {
    vi.mocked(api.getPlayerNews)
      .mockResolvedValueOnce({ ok: true, items: [story(1), story(2)], injury_item: null, has_more: true, next_offset: 2 })
      .mockResolvedValueOnce({ ok: true, items: [story(2), story(3)], injury_item: null, has_more: false, next_offset: null });
    render(<PlayerNewsTab playerId="p1" availability={null} />);
    fireEvent.click(await screen.findByText("Load more news"));
    expect(await screen.findByText("Story 3")).toBeInTheDocument();
    expect(api.getPlayerNews).toHaveBeenLastCalledWith("p1", 10, { offset: 2, groupDuplicates: true });
    expect(screen.getAllByText("Story 2")).toHaveLength(1);
    expect(screen.queryByText("Load more news")).not.toBeInTheDocument();
  });

  it("shows 'No recent news' when empty, with the feed's own message when it is warming up", async () => {
    vi.mocked(api.getPlayerNews).mockResolvedValue({
      ok: true,
      items: [],
      injury_item: null,
      status: { state: "warming_up", last_updated_ts: 0, message: "News is loading for the first time." },
    });
    render(<PlayerNewsTab playerId="p1" availability={null} />);
    expect(await screen.findByText("No recent news")).toBeInTheDocument();
    expect(screen.getByTestId("player-news-degraded")).toHaveTextContent("News is loading for the first time.");
  });

  it("shows an error with retry when the request fails, then recovers", async () => {
    vi.mocked(api.getPlayerNews).mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce({ ok: true, items: [story(1)], injury_item: null });
    render(<PlayerNewsTab playerId="p1" availability={null} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Couldn't load news right now.");
    fireEvent.click(screen.getByText("Try again"));
    await waitFor(() => expect(screen.getByText("Story 1")).toBeInTheDocument());
  });
});
