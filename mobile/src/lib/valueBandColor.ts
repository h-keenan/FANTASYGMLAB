import type { ThemeColors } from '../theme';
import { badgeTone } from './tradeValueBands.generated.ts';

/** Value-edge badge word -> theme color, through the shared band table so every
 * screen (Trade Hub, Finder, live draft) colors the same band the same way. */
export function valueEdgeBandColor(colors: ThemeColors, band: string | null | undefined): string {
  switch (badgeTone(band)) {
    case 'success':
      return colors.success;
    case 'warning':
      return colors.warning;
    case 'danger':
      return colors.danger;
    default:
      return colors.textSecondary;
  }
}
