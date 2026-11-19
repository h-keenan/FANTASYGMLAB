import { useEffect, useState } from "react";

import { createLatestGate, type LatestGate } from "./latestRequest";

/** A LatestGate that lives as long as the component and retires its tickets on unmount. See latestRequest.ts. */
export function useLatestGate(): LatestGate {
  const [gate] = useState(() => createLatestGate());
  useEffect(() => () => gate.cancel(), [gate]);
  return gate;
}
