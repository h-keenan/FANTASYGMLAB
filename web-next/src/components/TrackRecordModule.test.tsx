import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { TrackRecordModule } from "./TrackRecordModule";
import { api, type TrackRecordResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getTrackRecord: vi.fn(), getMe: vi.fn() } };
});

const basic = { trades_confirmed: 3, trades_graded: 2, worked_out: 1, didnt_pan_out: 1, even: 0, net_points_total: 12, reliability: "low" } as unknown as TrackRecordResponse["basic"];

describe("TrackRecordModule", () => {
  beforeEach(() => {
    vi.mocked(api.getMe).mockRejectedValue(new Error("me down"));
  });

  it("shows the Pro lock for a Free record from the response's own is_pro, even when /me fails", async () => {
    vi.mocked(api.getTrackRecord).mockResolvedValue({ ok: true, is_pro: false, basic, advanced: null });
    render(<TrackRecordModule />);
    fireEvent.click(await screen.findByRole("button", { name: /Your track record/ }));
    expect(await screen.findByTestId("track-record-lock")).toHaveTextContent("Pro");
    expect(api.getMe).not.toHaveBeenCalled();
  });

  it("shows no lock for a Pro record", async () => {
    vi.mocked(api.getTrackRecord).mockResolvedValue({ ok: true, is_pro: true, basic, advanced: null });
    render(<TrackRecordModule />);
    await screen.findByTestId("track-record");
    expect(screen.queryByTestId("track-record-lock")).not.toBeInTheDocument();
  });

  it("stays visible with an error state when the record cannot be read, never a blank", async () => {
    vi.mocked(api.getTrackRecord).mockRejectedValue(new Error("offline"));
    render(<TrackRecordModule />);
    expect(await screen.findByTestId("track-record-error")).toHaveTextContent("Your track record");
  });
});
