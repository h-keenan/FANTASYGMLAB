import { handle } from "./handler.ts";

Deno.serve((req) =>
  handle(req, { env: (k) => Deno.env.get(k), fetch: (u, i) => fetch(u, i) })
);
