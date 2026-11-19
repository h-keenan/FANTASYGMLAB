import { describe, expect, it } from "vitest";
import { preconnectOrigins } from "./preconnect";

describe("preconnectOrigins", () => {
  it("returns each distinct http(s) origin once, without paths", () => {
    expect(preconnectOrigins(["https://api.example.com/v1", "https://x.supabase.co", "https://api.example.com/other"])).toEqual([
      "https://api.example.com",
      "https://x.supabase.co",
    ]);
  });
  it("skips empty, malformed and non-http values", () => {
    expect(preconnectOrigins([undefined, "", "not a url", "ftp://host/x", "javascript:alert(1)"])).toEqual([]);
  });
});
