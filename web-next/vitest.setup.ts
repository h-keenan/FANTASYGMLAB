import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Explicit unmount between tests: @testing-library/react's own auto-cleanup
// only self-registers when `afterEach` is a global, which this project's
// vitest config (no `test.globals: true`) doesn't provide — without this,
// a test file with more than one `render()` call leaks every previous
// render's DOM into the next test, breaking any `getByText` whose string
// appears in more than one fixture (first hit on MyTeamContent.test.tsx,
// which renders several times per file; DashboardContent.test.tsx just
// hadn't happened to collide yet).
afterEach(() => {
  cleanup();
});
