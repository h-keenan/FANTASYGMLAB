import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { VerdictTrust } from "@/components/VerdictTrust";
import { api } from "@/lib/api";
import { VERDICT_TRUST_COPY, type VerdictReportContext } from "@/lib/verdictTrust";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, postVerdictFeedback: vi.fn() } };
});

const CONTEXT: VerdictReportContext = {
  surface: "trade_analyzer",
  platform: "web",
  leagueId: "L1",
  lens: "Dynasty",
  strategy: "retool",
  sendIds: ["p1"],
  receiveIds: ["p2"],
  verdictLabel: "ACCEPT",
  confidence: "High confidence",
  valueDelta: -379,
  assumptionsLine: "Assumed: Superflex, PPR.",
};
const ASSUMPTIONS = {
  line: "Assumed: Superflex, PPR, Dynasty values, Contender posture; values only, no weekly projections.",
  items: [{ key: "basis", label: "Basis", value: "values only, no weekly projections" }],
};

describe("VerdictTrust", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the assumptions line with its details", () => {
    render(<VerdictTrust assumptions={ASSUMPTIONS} context={CONTEXT} />);
    expect(screen.getByTestId("verdict-assumptions-line")).toHaveTextContent("Assumed: Superflex, PPR");
    expect(screen.getByText("Basis:")).toBeInTheDocument();
  });

  it("sends one fixed reason with the verdict context and thanks the reporter", async () => {
    vi.mocked(api.postVerdictFeedback).mockResolvedValue({ ok: true, reason: "" });
    render(<VerdictTrust assumptions={ASSUMPTIONS} context={CONTEXT} />);
    fireEvent.click(screen.getByRole("button", { name: VERDICT_TRUST_COPY.report }));
    expect(screen.queryByRole("textbox")).toBeNull(); // no free text
    fireEvent.click(screen.getByRole("button", { name: "Player values look off" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("Thanks"));
    expect(api.postVerdictFeedback).toHaveBeenCalledWith("values_off", CONTEXT);
    expect(screen.queryByRole("button", { name: VERDICT_TRUST_COPY.report })).toBeNull();
  });

  it("lets the reporter retry when sending fails, and cancel", async () => {
    vi.mocked(api.postVerdictFeedback).mockResolvedValue({ ok: false, reason: "not_available" });
    render(<VerdictTrust assumptions={null} context={CONTEXT} />);
    fireEvent.click(screen.getByRole("button", { name: VERDICT_TRUST_COPY.report }));
    fireEvent.click(screen.getByRole("button", { name: "Something else" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Could not send"));
    expect(screen.getByRole("button", { name: "Something else" })).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: VERDICT_TRUST_COPY.cancel }));
    expect(screen.getByRole("button", { name: VERDICT_TRUST_COPY.report })).toBeInTheDocument();
  });
});
