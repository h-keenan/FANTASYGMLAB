/**
 * The grab bar at the top of every swipe-to-dismiss sheet (see
 * lib/useSheetDragDismiss.ts). A touch that starts here always drags the
 * sheet, even when the content below is scrolled. Shown only on touch
 * (coarse-pointer) devices, where the gesture exists; desktop keeps the X
 * button, Esc and the backdrop.
 */
export function SheetHandle({ className = "" }: { className?: string }) {
  return (
    <div className={`sheet-handle ${className}`.trim()} data-sheet-handle aria-hidden="true">
      <span className="sheet-handle-bar" />
    </div>
  );
}
