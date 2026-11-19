import { describe, expect, it } from "vitest";

import { createShareToggleFlow } from "./shareToggleFlow";

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

describe("createShareToggleFlow", () => {
  it("off during an in-flight share removes the trade once the share lands", async () => {
    const share = deferred<string | null>();
    const deleted: string[] = [];
    const flow = createShareToggleFlow({
      unshare: async (id) => {
        deleted.push(id);
        return true;
      },
      enabled: true,
    });
    const shared = flow.requestShare(() => share.promise);
    const off = flow.requestOff();
    await Promise.resolve();
    expect(deleted).toEqual([]);
    share.resolve("t1");
    expect(await shared).toBe("cancelled");
    expect(await off).toBe("nothing");
    expect(deleted).toEqual(["t1"]);
    expect(flow.sharedId).toBeNull();
  });

  it("reports stuck-public when the follow-up delete fails, then off retries", async () => {
    const share = deferred<string | null>();
    let ok = false;
    const flow = createShareToggleFlow({ unshare: async () => ok, enabled: true });
    const shared = flow.requestShare(() => share.promise);
    const off = flow.requestOff();
    share.resolve("t1");
    expect(await shared).toBe("stuck-public");
    expect(await off).toBe("still-public");
    ok = true;
    expect(await flow.requestOff()).toBe("off");
    expect(flow.sharedId).toBeNull();
  });

  it("drops a second share while one is pending", async () => {
    const share = deferred<string | null>();
    let calls = 0;
    const send = () => {
      calls += 1;
      return share.promise;
    };
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    const first = flow.requestShare(send);
    expect(await flow.requestShare(send)).toBe("dropped");
    share.resolve("t1");
    expect(await first).toBe("shared");
    expect(calls).toBe(1);
    expect(flow.sharedId).toBe("t1");
  });

  it("a share started after an earlier off is not cancelled by it", async () => {
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    expect(await flow.requestOff()).toBe("nothing");
    expect(await flow.requestShare(async () => "t2")).toBe("shared");
    expect(flow.sharedId).toBe("t2");
  });

  it("normal off after a settled share deletes it; failure keeps the id", async () => {
    let ok = false;
    const flow = createShareToggleFlow({ unshare: async () => ok, enabled: true });
    await flow.requestShare(async () => "t1");
    expect(await flow.requestOff()).toBe("still-public");
    expect(flow.sharedId).toBe("t1");
    ok = true;
    expect(await flow.requestOff()).toBe("off");
  });

  it("a failed or unavailable share leaves nothing to remove", async () => {
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    expect(await flow.requestShare(async () => null)).toBe("unavailable");
    expect(await flow.requestShare(() => Promise.reject(new Error("x")))).toBe("error");
    expect(await flow.requestOff()).toBe("nothing");
  });

  it("kill switch off restores the old behaviour (in-flight off does not wait)", async () => {
    const share = deferred<string | null>();
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: false });
    const shared = flow.requestShare(() => share.promise);
    expect(await flow.requestOff()).toBe("nothing");
    share.resolve("t1");
    expect(await shared).toBe("shared");
  });
});
