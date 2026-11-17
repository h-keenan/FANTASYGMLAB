import * as Haptics from 'expo-haptics';

/** A footer tab changed: a light tap. Never throws (haptics are absent on simulators and some devices). */
export function tabChangeHaptic(): void {
  void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => undefined);
}

/** A row was selected or deselected, or a long-press shortcut opened: the system "selection" tick. */
export function selectionHaptic(): void {
  void Haptics.selectionAsync().catch(() => undefined);
}
