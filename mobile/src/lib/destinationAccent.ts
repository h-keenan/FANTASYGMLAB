import { accentFor, type AccentToken } from './destinationAccents.generated.ts';

/** The theme fields the shared semantic accent tokens resolve to (a ThemeColors subset). */
export interface AccentPalette {
  accent: string;
  success: string;
  warning: string;
  danger: string;
  opportunity: string;
  violet: string;
  premium: string;
}

/**
 * Web's --color-diagnostic is the app's `violet`; --color-information is the
 * same hue as accent on web (globals.css aliases it), so it is `accent` here.
 */
export function accentTokenColor(palette: AccentPalette, token: AccentToken): string {
  switch (token) {
    case 'success':
      return palette.success;
    case 'warning':
      return palette.warning;
    case 'danger':
      return palette.danger;
    case 'opportunity':
      return palette.opportunity;
    case 'diagnostic':
      return palette.violet;
    case 'premium':
      return palette.premium;
    case 'information':
    case 'accent':
    default:
      return palette.accent;
  }
}

/**
 * A destination's accent color from the one shared map (modules/
 * destination_accents.py): GM orb rows pass their label, the feature catalog
 * its id. `fallback` covers destinations with no entry (Home, Account, ...).
 */
export function accentColor(palette: AccentPalette, idOrLabel: string, fallback: AccentToken = 'accent'): string {
  return accentTokenColor(palette, accentFor(idOrLabel, fallback));
}
