import { afterEach, describe, expect, it, vi } from "vitest";

const init = vi.fn();
const captureException = vi.fn();
vi.mock("@sentry/browser", () => ({ init, captureException }));

import { reportError, resetErrorReporterForTests } from "./errorReporter";

afterEach(() => {
  vi.unstubAllEnvs();
  resetErrorReporterForTests();
  init.mockClear();
  captureException.mockClear();
});

describe("errorReporter", () => {
  it("is a no-op without a DSN (Sentry never initialised)", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "");
    reportError(new Error("x"));
    await new Promise((r) => setTimeout(r, 10));
    expect(init).not.toHaveBeenCalled();
    expect(captureException).not.toHaveBeenCalled();
  });

  it("initialises privacy-safe Sentry once and captures with a DSN", async () => {
    vi.stubEnv("NEXT_PUBLIC_SENTRY_DSN", "https://k@o.ingest.sentry.io/1");
    reportError(new Error("a"));
    reportError(new Error("b"), { route: "/x" });
    await new Promise((r) => setTimeout(r, 20));
    expect(init).toHaveBeenCalledTimes(1);
    expect(init.mock.calls[0][0]).toMatchObject({ tracesSampleRate: 0, sendDefaultPii: false });
    expect(captureException).toHaveBeenCalledTimes(2);
  });
});
