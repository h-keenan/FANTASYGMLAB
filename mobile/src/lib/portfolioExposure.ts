import type { PortfolioExposurePlayer } from './api.ts';

export type ExposureSortKey = 'leagues' | 'value';

export function sortExposurePlayers(players: PortfolioExposurePlayer[], sort: ExposureSortKey): PortfolioExposurePlayer[] {
  return [...players].sort((a, b) =>
    sort === 'value'
      ? b.value - a.value || b.leagues_owned - a.leagues_owned
      : b.leagues_owned - a.leagues_owned || b.value - a.value,
  );
}
