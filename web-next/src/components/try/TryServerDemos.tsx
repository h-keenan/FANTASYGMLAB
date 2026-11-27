import { PlayoffSosTables } from "@/components/seo/PlayoffSosTables";
import { ValueTable } from "@/components/seo/ValueTable";
import { loadChartRows } from "@/lib/seo/chartRows";
import { fetchPlayoffSos, hasUsableSos } from "@/lib/seo/playoffSos";
import { playoffSosInSeason, seasonMoment } from "@/lib/seasonalLanding";

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <section className="glass-surface p-4">
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {children}
      </p>
    </section>
  );
}

export async function Playoffs() {
  const sos = await fetchPlayoffSos();
  if (!playoffSosInSeason(seasonMoment()) || !hasUsableSos(sos)) {
    return <Notice>Playoff schedule rankings appear once the fantasy playoffs are close and enough games have been played to rate every defense.</Notice>;
  }
  return <PlayoffSosTables sos={sos} />;
}

export async function DynastyValues() {
  const chart = await loadChartRows();
  if (!chart) return <Notice>The value chart is refreshing. Try again in a few minutes.</Notice>;
  return (
    <>
      <ValueTable rows={chart.rows} valueHeader="1QB value" extraHeader="Superflex" caption="Dynasty trade value chart" />
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Values assume a 12-team PPR league and are not tied to any specific league.
      </p>
    </>
  );
}
