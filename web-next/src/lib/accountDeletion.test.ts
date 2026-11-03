import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it, vi } from "vitest";

import { DELETE_ACCOUNT_FALLBACK_ERROR, deleteAccountOnServer } from "./accountDeletion";

const client = (result: unknown) => ({ functions: { invoke: vi.fn().mockResolvedValue(result) } });

describe("deleteAccountOnServer", () => {
  it("calls the delete-account function (not the bare RPC) and succeeds only on ok:true", async () => {
    const c = client({ data: { ok: true }, error: null });
    expect(await deleteAccountOnServer(c)).toEqual({ error: null });
    expect(c.functions.invoke).toHaveBeenCalledWith("delete-account", { method: "POST", body: {} });
  });

  it("surfaces the server's error message and never reports success", async () => {
    const context = { json: async () => ({ ok: false, error: "Could not cancel your subscription, so your account was not deleted." }) };
    const r = await deleteAccountOnServer(client({ data: null, error: { message: "non-2xx", context } }));
    expect(r.error).toMatch(/not deleted/);
  });

  it("falls back to a clear error on unparseable, empty or thrown results", async () => {
    expect((await deleteAccountOnServer(client({ data: null, error: { message: "x" } }))).error).toBe(DELETE_ACCOUNT_FALLBACK_ERROR);
    expect((await deleteAccountOnServer(client({ data: {}, error: null }))).error).toBe(DELETE_ACCOUNT_FALLBACK_ERROR);
    const throwing = { functions: { invoke: vi.fn().mockRejectedValue(new Error("net")) } };
    expect((await deleteAccountOnServer(throwing)).error).toBe(DELETE_ACCOUNT_FALLBACK_ERROR);
  });

  it("stays byte-identical to mobile's copy", () => {
    const web = readFileSync(path.resolve(__dirname, "accountDeletion.ts"), "utf8");
    const mobile = readFileSync(path.resolve(__dirname, "../../../mobile/src/lib/accountDeletion.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
