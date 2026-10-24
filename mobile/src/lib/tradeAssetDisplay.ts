/** Short injury code for the compact pill (Q, D, O, IR); anything else shows as-is. */
export function injuryShortCode(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized.startsWith('quest')) return 'Q';
  if (normalized.startsWith('doubt')) return 'D';
  if (normalized === 'out') return 'O';
  if (normalized === 'ir' || normalized.startsWith('injured')) return 'IR';
  return status;
}
