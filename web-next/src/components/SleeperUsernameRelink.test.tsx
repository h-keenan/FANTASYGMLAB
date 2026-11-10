import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SleeperUsernameRelink } from "./SleeperUsernameRelink";

const mocks = vi.hoisted(() => ({ lookup: vi.fn(), link: vi.fn() }));
vi.mock("@/lib/api", () => ({
  api: { lookupSleeperLeagues: (u: string) => mocks.lookup(u), linkSleeperUsername: (u: string) => mocks.link(u) },
}));

describe("SleeperUsernameRelink", () => {
  beforeEach(() => {
    mocks.lookup.mockReset().mockResolvedValue({ ok: true, status: "ok", leagues: [{ league_id: "1" }] });
    mocks.link.mockReset().mockResolvedValue({ ok: true, sleeper_username: "newname" });
  });

  it("verifies the username on Sleeper, links it, and reports it", async () => {
    const onLinked = vi.fn();
    render(<SleeperUsernameRelink current="old" onLinked={onLinked} />);
    fireEvent.click(screen.getByRole("button", { name: "Change Sleeper username" }));
    fireEvent.change(screen.getByLabelText("Sleeper username"), { target: { value: " newname " } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(onLinked).toHaveBeenCalledWith("newname"));
    expect(mocks.lookup).toHaveBeenCalledWith("newname");
    expect(mocks.link).toHaveBeenCalledWith("newname");
  });

  it("does not link a username Sleeper can't find", async () => {
    mocks.lookup.mockResolvedValue({ ok: false, status: "user_not_found", leagues: [] });
    const onLinked = vi.fn();
    render(<SleeperUsernameRelink current="" onLinked={onLinked} />);
    fireEvent.click(screen.getByRole("button", { name: "Link Sleeper username" }));
    fireEvent.change(screen.getByLabelText("Sleeper username"), { target: { value: "nobody" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/couldn't find a Sleeper user/);
    expect(mocks.link).not.toHaveBeenCalled();
    expect(onLinked).not.toHaveBeenCalled();
  });
});
