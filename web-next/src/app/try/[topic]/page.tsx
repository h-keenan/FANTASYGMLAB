import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { StartSitDemo, TradeDemo, WaiversDemo } from "@/components/try/TryDemos";
import { DynastyValues, Playoffs } from "@/components/try/TryServerDemos";
import { TryCta } from "@/components/try/TryCta";
import { TryTracker } from "@/components/try/TryTracker";
import { ToneBadge } from "@/components/ToneBadge";
import { ValuesCredit } from "@/components/ValuesCredit";
import { isTryTopic, tryTopicInfo, TRY_TOPICS, type TryTopic } from "@/lib/tryLinks";

// No-signup ad landing pages (lib/tryLinks.ts). Rendered per request: playoffs follows the season clock and the live
// public schedule, dynasty-values the daily board. Never indexed: the real tools they wrap own the SEO.
export const dynamic = "force-dynamic";
export const dynamicParams = false;
export function generateStaticParams() {
  return TRY_TOPICS.map((t) => ({ topic: t.topic }));
}

type Params = Promise<{ topic: string }>;

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const { topic } = await params;
  if (!isTryTopic(topic)) return {};
  const info = tryTopicInfo(topic);
  return {
    title: info.title,
    description: info.intro,
    robots: { index: false, follow: false, nocache: true },
  };
}

function Demo({ topic }: { topic: TryTopic }) {
  switch (topic) {
    case "start-sit":
      return <StartSitDemo />;
    case "trade":
      return <TradeDemo />;
    case "waivers":
      return <WaiversDemo />;
    case "playoffs":
      return <Playoffs />;
    case "dynasty-values":
      return <DynastyValues />;
  }
}

const EXAMPLE_LEAGUE_TOPICS: readonly TryTopic[] = ["start-sit", "waivers"];

export default async function TryPage({ params }: { params: Params }) {
  const { topic } = await params;
  if (!isTryTopic(topic)) notFound();
  const info = tryTopicInfo(topic);
  return (
    <main className="page-shell page-shell-prose" data-testid={`try-page-${topic}`}>
      <TryTracker topic={topic} />
      <div className="flex flex-col gap-2">
        <h1 style={{ font: "var(--font-page-title)" }}>{info.title}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {info.intro}
        </p>
        {EXAMPLE_LEAGUE_TOPICS.includes(topic) ? (
          <span className="self-start">
            <ToneBadge label="Example league: made-up players" color="var(--color-accent)" />
          </span>
        ) : null}
      </div>
      <Demo topic={topic} />
      <TryCta topic={topic} />
      {topic === "trade" || topic === "dynasty-values" ? <ValuesCredit /> : null}
    </main>
  );
}
