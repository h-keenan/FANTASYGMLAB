/**
 * Deep link into a Quick Fantasy Sim game: fantasygmlab://gm-game?quickstart=1 (web twin: /gm-game?quickstart=1).
 * Pure so it can be tested; RootNavigator wires it to Linking.
 */
export function isSimQuickStartUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  const match = /^[a-z][a-z0-9+.-]*:\/\/\/?([^?#]*)(?:\?([^#]*))?/i.exec(url.trim());
  if (!match) return false;
  const path = match[1].replace(/\/+$/, '');
  if (path !== 'gm-game') return false;
  return (match[2] ?? '').split('&').includes('quickstart=1');
}
