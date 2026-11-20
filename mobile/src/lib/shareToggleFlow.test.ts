import assert from "node:assert/strict";
import test from "node:test";

import { createShareToggleFlow } from "./shareToggleFlow.ts";

function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
});
  return { promise, resolve };
}

test("off during an in-flight share removes the trade once the share lands", async () => {
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
    assert.deepEqual(deleted, []);
    share.resolve("t1");
    assert.equal(await shared, "cancelled");
    assert.equal(await off, "nothing");
    assert.deepEqual(deleted, ["t1"]);
    assert.equal(flow.sharedId, null);
});

test("reports stuck-public when the follow-up delete fails, then off retries", async () => {
    const share = deferred<string | null>();
    let ok = false;
    const flow = createShareToggleFlow({ unshare: async () => ok, enabled: true });
    const shared = flow.requestShare(() => share.promise);
    const off = flow.requestOff();
    share.resolve("t1");
    assert.equal(await shared, "stuck-public");
    assert.equal(await off, "still-public");
    ok = true;
    assert.equal(await flow.requestOff(), "off");
    assert.equal(flow.sharedId, null);
});

test("drops a second share while one is pending", async () => {
    const share = deferred<string | null>();
    let calls = 0;
    const send = () => {
      calls += 1;
      return share.promise;
    };
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    const first = flow.requestShare(send);
    assert.equal(await flow.requestShare(send), "dropped");
    share.resolve("t1");
    assert.equal(await first, "shared");
    assert.equal(calls, 1);
    assert.equal(flow.sharedId, "t1");
});

test("a share started after an earlier off is not cancelled by it", async () => {
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    assert.equal(await flow.requestOff(), "nothing");
    assert.equal(await flow.requestShare(async () => "t2"), "shared");
    assert.equal(flow.sharedId, "t2");
});

test("normal off after a settled share deletes it; failure keeps the id", async () => {
    let ok = false;
    const flow = createShareToggleFlow({ unshare: async () => ok, enabled: true });
    await flow.requestShare(async () => "t1");
    assert.equal(await flow.requestOff(), "still-public");
    assert.equal(flow.sharedId, "t1");
    ok = true;
    assert.equal(await flow.requestOff(), "off");
});

test("a failed or unavailable share leaves nothing to remove", async () => {
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: true });
    assert.equal(await flow.requestShare(async () => null), "unavailable");
    assert.equal(await flow.requestShare(() => Promise.reject(new Error("x"))), "error");
    assert.equal(await flow.requestOff(), "nothing");
});

test("kill switch off restores the old behaviour (in-flight off does not wait)", async () => {
    const share = deferred<string | null>();
    const flow = createShareToggleFlow({ unshare: async () => true, enabled: false });
    const shared = flow.requestShare(() => share.promise);
    assert.equal(await flow.requestOff(), "nothing");
    share.resolve("t1");
    assert.equal(await shared, "shared");
});
