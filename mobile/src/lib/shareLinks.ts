/**
 * Attribution-tagged link appended to share-sheet text so a shared recap,
 * trade or player brings traffic that shows up as utm_source=share on the
 * first-party landing analytics (the app itself ships no analytics). `surface`
 * is a fixed snake_case id, never free text.
 */
export function shareLink(surface: 'trade' | 'player' | 'compare' | 'portfolio' | 'recap'): string {
  return `https://fantasygmlab.com/?utm_source=share&utm_medium=text&utm_campaign=${surface}`;
}
