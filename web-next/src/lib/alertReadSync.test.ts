import { beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api";
import {
  markAlertReadSynced,
  overlayPendingAlertReads,
  pendingAlertReadKeys,
  reconcileAlertReads,
} from "./alertReadSync";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, markAlertRead: vi.fn() } };
});

const markAlertRead = vi.mocked(api.markAlertRead);

describe("alertReadSync", () => {
  beforeEach(() => {
    window.localStorage.clear();
    markAlertRead.mockReset();
  });

  it("clears the pending read once the server durably records it", async () => {
    markAlertRead.mockResolvedValue({ ok: true });
    await expect(markAlertReadSynced("u1", "L1", "k1")).resolves.toBe(true);
    expect(markAlertRead).toHaveBeenCalledWith("L1", "k1");
    expect(pendingAlertReadKeys("u1", "L1").size).toBe(0);
  });

  it("keeps a read pending when offline or the backend answers ok: false, and shows it read", async () => {
    markAlertRead.mockRejectedValueOnce(new Error("offline"));
    await expect(markAlertReadSynced("u1", "L1", "k1")).resolves.toBe(false);
    markAlertRead.mockResolvedValueOnce({ ok: false });
    await expect(markAlertReadSynced("u1", "L1", "k2")).resolves.toBe(false);

    expect([...pendingAlertReadKeys("u1", "L1")].sort()).toEqual(["k1", "k2"]);
    const items = [
      { alert_key: "k1", read: false },
      { alert_key: "k3", read: false },
    ];
    expect(overlayPendingAlertReads("u1", "L1", items)).toEqual([
      { alert_key: "k1", read: true },
      { alert_key: "k3", read: false },
    ]);
    // Scoped per account and league.
    expect(pendingAlertReadKeys("u2", "L1").size).toBe(0);
    expect(pendingAlertReadKeys("u1", "L2").size).toBe(0);
  });

  it("reconcile drops reads the server confirms and retries the rest", async () => {
    markAlertRead.mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: false });
    await markAlertReadSynced("u1", "L1", "k1");
    await markAlertReadSynced("u1", "L1", "k2");

    markAlertRead.mockReset();
    markAlertRead.mockResolvedValue({ ok: true });
    const merged = reconcileAlertReads("u1", "L1", [
      { alert_key: "k1", read: true }, // read on another device / already synced
      { alert_key: "k2", read: false }, // still only local
    ]);
    expect(merged).toEqual([
      { alert_key: "k1", read: true },
      { alert_key: "k2", read: true },
    ]);
    expect(markAlertRead).toHaveBeenCalledTimes(1);
    expect(markAlertRead).toHaveBeenCalledWith("L1", "k2");
    await vi.waitFor(() => expect(pendingAlertReadKeys("u1", "L1").size).toBe(0));
  });

  it("degrades to server-only state when storage throws", async () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });
    markAlertRead.mockResolvedValue({ ok: true });
    await expect(markAlertReadSynced("u1", "L1", "k1")).resolves.toBe(true);
    expect(overlayPendingAlertReads("u1", "L1", [{ alert_key: "k1", read: false }])).toEqual([
      { alert_key: "k1", read: false },
    ]);
    getItem.mockRestore();
  });
});
