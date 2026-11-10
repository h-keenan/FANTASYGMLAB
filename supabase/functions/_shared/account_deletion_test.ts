import { assert, assertEquals } from "./assert.ts";
import { handle as deleteAccount } from "../delete-account/handler.ts";
import { appleClientSecret } from "./account_deletion.ts";
import { BASE_ENV, envOf, fakeFetch, j, USER_ID } from "./fixtures.ts";

const req = (body: unknown = {}, jwt: string | null = "good-jwt") =>
  new Request("https://x.test/delete-account", {
    method: "POST",
    body: JSON.stringify(body),
    headers: jwt ? { authorization: `Bearer ${jwt}` } : {},
  });

function routes(profile: Record<string, unknown> | null, extra: Record<string, (c: never) => Response> = {}) {
  return {
    "GET /auth/v1/user": (c: { init: RequestInit }) =>
      (c.init.headers as Record<string, string>).Authorization === "Bearer good-jwt"
        ? j({ id: USER_ID, email: "a@b.test" })
        : j({}, 401),
    "GET /rest/v1/profiles": () => (profile === null ? j({ message: "boom" }, 500) : j([profile])),
    "DELETE /auth/v1/admin/users/": () => j({}),
    ...extra,
  } as Record<string, (c: { url: string; init: RequestInit }) => Response>;
}

const subList = (...subs: { id: string; status: string }[]) => () => j({ data: subs });
const noSearch = () => j({ data: [] });

Deno.test("delete-account: cancels live subs BEFORE deleting the user; skips terminal ones", async () => {
  const f = fakeFetch(routes({ stripe_customer_id: "cus_1", stripe_subscription_id: "sub_a" }, {
    "GET https://api.stripe.com/v1/subscriptions/search": noSearch,
    "GET https://api.stripe.com/v1/subscriptions?": subList({ id: "sub_a", status: "active" }, { id: "sub_old", status: "canceled" }),
    "DELETE https://api.stripe.com/v1/subscriptions/sub_a": () => j({ id: "sub_a", status: "canceled" }),
  }));
  const res = await deleteAccount(req(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 200);
  assertEquals((await res.json()).stripe_subscriptions_canceled, 1);
  const cancels = f.calls.filter((c) => c.init.method === "DELETE" && c.url.includes("api.stripe.com"));
  assertEquals(cancels.length, 1);
  assert(!f.calls.some((c) => c.url.endsWith("/subscriptions/sub_old")));
  const iCancel = f.calls.findIndex((c) => c.init.method === "DELETE" && c.url.includes("api.stripe.com"));
  const iDelete = f.calls.findIndex((c) => c.url.includes("/auth/v1/admin/users/"));
  assert(iCancel >= 0 && iDelete > iCancel, "stripe cancel must precede user deletion");
});

Deno.test("delete-account: Stripe cancel failure aborts and the user is NOT deleted", async () => {
  const f = fakeFetch(routes({ stripe_customer_id: "cus_1" }, {
    "GET https://api.stripe.com/v1/subscriptions/search": noSearch,
    "GET https://api.stripe.com/v1/subscriptions?": subList({ id: "sub_a", status: "active" }),
    "DELETE https://api.stripe.com/v1/subscriptions/sub_a": () => j({ error: { type: "api_error" } }, 500),
  }));
  const res = await deleteAccount(req(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 502);
  assert(!f.calls.some((c) => c.url.includes("/auth/v1/admin/users/")));
});

Deno.test("delete-account: already-canceled race (404 resource_missing) is idempotent success", async () => {
  const f = fakeFetch(routes({ stripe_customer_id: "cus_1" }, {
    "GET https://api.stripe.com/v1/subscriptions/search": noSearch,
    "GET https://api.stripe.com/v1/subscriptions?": subList({ id: "sub_a", status: "active" }),
    "DELETE https://api.stripe.com/v1/subscriptions/sub_a": () => j({ error: { code: "resource_missing" } }, 404),
  }));
  const res = await deleteAccount(req(), { env: envOf(BASE_ENV), fetch: f.fn });
  assertEquals(res.status, 200);
  assert(f.calls.some((c) => c.url.includes("/auth/v1/admin/users/")));
});

Deno.test("delete-account: user with no Stripe state is deleted without touching Stripe", async () => {
  const f = fakeFetch(routes({}));
  const res = await deleteAccount(req(), { env: envOf({ ...BASE_ENV, STRIPE_SECRET_KEY: "" }), fetch: f.fn });
  assertEquals(res.status, 200);
  assert(!f.calls.some((c) => c.url.includes("api.stripe.com")));
});

Deno.test("delete-account: Stripe unconfigured but user has billing ids => fail closed", async () => {
  const f = fakeFetch(routes({ stripe_customer_id: "cus_1" }));
  const res = await deleteAccount(req(), { env: envOf({ ...BASE_ENV, STRIPE_SECRET_KEY: "" }), fetch: f.fn });
  assertEquals(res.status, 503);
  assert(!f.calls.some((c) => c.url.includes("/auth/v1/admin/users/")));
});

Deno.test("delete-account: unreadable profile fails closed; bad JWT is 401", async () => {
  const f = fakeFetch(routes(null));
  assertEquals((await deleteAccount(req(), { env: envOf(BASE_ENV), fetch: f.fn })).status, 503);
  assertEquals((await deleteAccount(req({}, "bad"), { env: envOf(BASE_ENV), fetch: f.fn })).status, 401);
  assert(!f.calls.some((c) => c.url.includes("/auth/v1/admin/users/")));
});

Deno.test("delete-account: Apple revocation runs only when configured AND a code is supplied", async () => {
  const kp = await crypto.subtle.generateKey({ name: "ECDSA", namedCurve: "P-256" }, true, ["sign", "verify"]);
  const der = new Uint8Array(await crypto.subtle.exportKey("pkcs8", kp.privateKey));
  let bin = "";
  for (const b of der) bin += String.fromCharCode(b);
  const pem = `-----BEGIN PRIVATE KEY-----\n${btoa(bin)}\n-----END PRIVATE KEY-----`;
  const appleEnv = { ...BASE_ENV, STRIPE_SECRET_KEY: "", APPLE_TEAM_ID: "TEAM", APPLE_KEY_ID: "KEY", APPLE_CLIENT_ID: "com.example.app", APPLE_PRIVATE_KEY: pem };
  const apple = {
    "POST https://appleid.apple.com/auth/token": () => j({ refresh_token: "r_1", access_token: "a_1" }),
    "POST https://appleid.apple.com/auth/revoke": () => j({}),
  };
  const withCode = fakeFetch({ ...routes({}), ...apple });
  const r1 = await deleteAccount(req({ apple_authorization_code: "c1" }), { env: envOf(appleEnv), fetch: withCode.fn });
  assertEquals((await r1.json()).apple_revoked, true);
  const rev = withCode.calls.find((c) => c.url.endsWith("/auth/revoke"))!;
  assert(String(rev.init.body).includes("token=r_1"));

  const noCode = fakeFetch({ ...routes({}), ...apple });
  const r2 = await deleteAccount(req(), { env: envOf(appleEnv), fetch: noCode.fn });
  assertEquals((await r2.json()).apple_revoked, null);
  assert(!noCode.calls.some((c) => c.url.includes("appleid.apple.com")));

  const unconfigured = fakeFetch({ ...routes({}), ...apple });
  const r3 = await deleteAccount(req({ apple_authorization_code: "c1" }), { env: envOf({ ...appleEnv, APPLE_KEY_ID: "" }), fetch: unconfigured.fn });
  assertEquals((await r3.json()).apple_revoked, null);

  const jwt = await appleClientSecret({ teamId: "TEAM", keyId: "KEY", privateKey: pem, clientId: "c" }, 1_800_000_000);
  assertEquals(jwt.split(".").length, 3);
});
