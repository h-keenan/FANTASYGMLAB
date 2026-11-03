/**
 * Shared fixture list for abbreviatePlayerName. The identical file lives at
 * mobile/src/lib/playerNameFixtures.ts; both platforms' tests assert it, so
 * web and mobile can never drift apart on how a name is shortened.
 */
export const PLAYER_NAME_FIXTURES: ReadonlyArray<readonly [string, string]> = [
  ['Marvin Mitchell', 'M. Mitchell'],
  ['John Metchie', 'J. Metchie'],
  ['Amon-Ra St. Brown', 'A. St. Brown'],
  ['Marvin Harrison Jr.', 'M. Harrison Jr.'],
  ['Kenneth Walker III', 'K. Walker III'],
  ['Deebo Samuel Sr.', 'D. Samuel Sr.'],
  ['Ja\'Marr Chase', 'J. Chase'],
  ['D.K. Metcalf', 'D.K. Metcalf'],
  ['A.J. Brown', 'A.J. Brown'],
  ['CJ Stroud', 'CJ Stroud'],
  ['Christian McCaffrey', 'C. McCaffrey'],
  ['Wan\'Dale Robinson', 'W. Robinson'],
  ['Devaughn Vele', 'D. Vele'],
  ['Christian Watson-Smith', 'C. Watson-Smith'],
  ['Tank Dell', 'T. Dell'],
  ['  Justin   Jefferson  ', 'J. Jefferson'],
  ['Neymar', 'Neymar'],
  ['', ''],
];
