// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

import { POST } from "./route";
import { summarizeCspReport } from "@/lib/cspReport";

const legacy = {
  "csp-report": {
    "document-uri": "https://app.fantasygmlab.com/dashboard/123?token=secret#frag",
    "blocked-uri": "https://evil.example.com/x.js?user=me@example.com",
    "effective-directive": "script-src-elem",
    disposition: "report",
  },
};

afterEach(() => vi.restoreAllMocks());

describe("summarizeCspReport", () => {
  it("keeps the directive, blocked origin and page path only", () => {
    expect(summarizeCspReport(legacy)).toEqual({ directive: "script-src-elem", blocked: "https://evil.example.com", page: "/dashboard/123", disposition: "report" });
  });

  it("reads the Reporting API shape and rejects junk", () => {
    expect(summarizeCspReport([{ type: "csp-violation", body: { effectiveDirective: "img-src", blockedURL: "inline", documentURL: "https://a.test/x" } }])?.blocked).toBe("inline");
    expect(summarizeCspReport("nope")).toBeNull();
    expect(summarizeCspReport(null)).toBeNull();
  });
});

describe("POST /api/csp-report", () => {
  const post = (body: string) => POST(new Request("https://app.fantasygmlab.com/api/csp-report", { method: "POST", body }));

  it("logs one sanitized line (no query, no PII) when the report is sampled in", async () => {
    vi.spyOn(Math, "random").mockReturnValue(0);
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    expect((await post(JSON.stringify(legacy))).status).toBe(204);
    expect(warn).toHaveBeenCalledTimes(1);
    const line = String(warn.mock.calls[0][0]);
    expect(line).toContain("directive=script-src-elem");
    expect(line).not.toMatch(/secret|example.com\/x|me@|frag/);
  });

  it("drops reports outside the sample, malformed and oversized ones, always with 204", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.spyOn(Math, "random").mockReturnValue(0.99);
    expect((await post(JSON.stringify(legacy))).status).toBe(204);
    vi.spyOn(Math, "random").mockReturnValue(0);
    expect((await post("{not json")).status).toBe(204);
    expect((await post("x".repeat(9000))).status).toBe(204);
    expect(warn).not.toHaveBeenCalled();
  });
});
