/**
 * Retired as a painter: the wash, accent bloom and the animated field/sweep
 * now live in ONE root-level AppBackground (mounted by RootNavigator behind
 * every screen), and screens' root backgrounds are transparent to let it
 * show. Kept as a no-op component only so existing screens (and screens
 * being added concurrently) that still render `<GridBackground />` keep
 * compiling and simply render nothing.
 */
export default function GridBackground() {
  return null;
}
