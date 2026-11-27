import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DynastyValues, Playoffs } from "@/components/try/TryServerDemos";
import TryPage, { generateMetadata, generateStaticParams } from "./page";

const trackTryLink = vi.fn();
vi.mock("@/lib/analytics", () => ({ trackTryLink: (...a: unknown[]) => trackTryLink(...a), trackUse: vi.fn(), trackFeatureUse: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/try/start-sit",
  useSearchParams: () => new URLSearchParams(),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));
vi.mock("@/lib/seo/playoffSos", async (orig) => ({ ...(await orig<object>()), fetchPlayoffSos: vi.fn().mockResolvedValue(null) }));
vi.mock("@/lib/seo/chartRows", () => ({ loadChartRows: vi.fn().mockResolvedValue(null) }));

async function renderTopic(topic: string) {
  const ui = await TryPage({ params: Promise.resolve({ topic }) });
  return render(ui);
}

describe("/try/[topic]", () => {
  beforeEach(() => {
    trackTryLink.mockClear();
    window.history.pushState({}, "", "/try/start-sit?utm_source=ad_app&utm_campaign=hook&gclid=G1");
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
  });
  afterEach(() => vi.restoreAllMocks());

  it("pre-renders exactly the five topics and is never indexed", async () => {
    expect(generateStaticParams().map((p) => p.topic)).toEqual(["start-sit", "trade", "waivers", "playoffs", "dynasty-values"]);
    const meta = await generateMetadata({ params: Promise.resolve({ topic: "trade" }) });
    expect(meta.robots).toMatchObject({ index: false, follow: false });
  });

  it("404s an unknown topic", async () => {
    await expect(renderTopic("nope")).rejects.toThrow("NEXT_NOT_FOUND");
  });

  it("start-sit shows the real Suggested Moves module on the example league, then ONE CTA with the campaign carried", async () => {
    await renderTopic("start-sit");
    expect(screen.getByTestId("matchup-moves")).toBeInTheDocument();
    expect(screen.getAllByText(/Taylor Exampleton/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Example league: made-up players/)).toBeInTheDocument();
    const cta = await screen.findByTestId("try-cta-link");
    expect(cta).toHaveTextContent("Do this for your league");
    expect(screen.getAllByTestId("try-cta-link")).toHaveLength(1);
    await vi.waitFor(() => expect(cta.getAttribute("href")).toContain("gclid=G1"));
    expect(cta.getAttribute("href")).toMatch(/^\/connect-league\?utm_source=ad_app&utm_campaign=hook/);
    expect(trackTryLink).toHaveBeenCalledWith("viewed", "start-sit");
  });

  it("waivers renders the real waiver board on example data", async () => {
    await renderTopic("waivers");
    expect(screen.getAllByText(/Reese Wirewell/).length).toBeGreaterThan(0);
    expect(screen.getAllByTestId("try-cta-link")).toHaveLength(1);
    expect(trackTryLink).toHaveBeenCalledWith("viewed", "waivers");
  });

  it("trade mounts the real public trade analyzer with the preset and no competing CTAs", async () => {
    await renderTopic("trade");
    expect(screen.getByTestId("public-trade-analyzer")).toBeInTheDocument();
    expect(screen.queryByTestId("roster-teaser")).not.toBeInTheDocument();
    expect(screen.getAllByTestId("try-cta-link")).toHaveLength(1);
  });

  it("playoffs and dynasty-values (async server views) degrade to a notice when the public data is unavailable", async () => {
    render(await Playoffs());
    expect(screen.getByText(/appear once the fantasy playoffs are close/)).toBeInTheDocument();
    document.body.innerHTML = "";
    render(await DynastyValues());
    expect(screen.getByText(/refreshing/)).toBeInTheDocument();
  });

  it("click on the CTA is counted as a demo cta_click", async () => {
    await renderTopic("start-sit");
    (await screen.findByTestId("try-cta-link")).addEventListener("click", (e) => e.preventDefault());
    (await screen.findByTestId("try-cta-link")).click();
    expect(trackTryLink).toHaveBeenCalledWith("cta_click", "start-sit");
  });
});
