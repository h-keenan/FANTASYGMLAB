import { render, screen } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import TradeAnalyzerPublicPage, { metadata } from "./page";
import { TRADE_FAQ } from "@/lib/seo/tradeAnalyzer";

vi.mock("@/lib/analytics", () => ({ trackUse: vi.fn() }));

describe("/trade-analyzer public page", () => {
  afterEach(() => vi.restoreAllMocks());

  it("has crawlable SEO metadata: title, description, canonical, OG image", () => {
    expect(String(metadata.title)).toMatch(/Trade Analyzer/);
    expect(String(metadata.description).length).toBeLessThanOrEqual(160);
    expect(metadata.alternates?.canonical).toBe("https://app.fantasygmlab.com/trade-analyzer");
    expect(JSON.stringify(metadata.openGraph)).toContain("og-image.png");
  });

  it("server-renders the H1, FAQ, FantasyCalc credit and internal links without JS", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    const html = renderToStaticMarkup(<TradeAnalyzerPublicPage />);
    expect(html).toContain("<h1");
    expect(html).toContain("Fantasy Football Trade Analyzer");
    for (const item of TRADE_FAQ) expect(html).toContain(item.q);
    expect(html).toContain("fantasycalc.com");
    expect(html).toContain('href="/dynasty-trade-value-chart"');
    expect(html).toContain('href="/dynasty-tools"');
  });

  it("emits FAQPage, WebApplication and breadcrumb JSON-LD", () => {
    vi.spyOn(globalThis, "fetch").mockReturnValue(new Promise(() => {}));
    const { container } = render(<TradeAnalyzerPublicPage />);
    const types = Array.from(container.querySelectorAll('script[type="application/ld+json"]')).map(
      (el) => JSON.parse(el.textContent || "{}")["@type"],
    );
    expect(types).toEqual(expect.arrayContaining(["BreadcrumbList", "WebPage", "WebApplication", "FAQPage"]));
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Fantasy Football Trade Analyzer");
  });
});
