import { useEffect, useState } from 'react';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import { api } from './api';
import { showProMarkers } from './plan';
import { queryKeys } from './queryKeys';
import { PRO, getEntitlementTier, isAtLeast } from './revenuecat';

/**
 * True only for a person CONFIRMED to be on the Free plan (an unreadable plan shows no marker rather than a wrong one).
 * Paid tabs and rows wear the gold Pro marker before the tap when this is true. Same rule as the orb sheet's rows
 * (web twin: lib/useIsPro.ts === false). A store (App Store / Play) subscriber is never Free.
 */
export function useShowProTags(): boolean {
  const isRestoring = useIsRestoring();
  const planQuery = useQuery({ queryKey: queryKeys.mePlan(), queryFn: () => api.getMe(), enabled: !isRestoring, staleTime: 5 * 60 * 1000 });
  const [storeSubscriber, setStoreSubscriber] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getEntitlementTier()
      .then((tier) => {
        if (!cancelled) setStoreSubscriber(isAtLeast(tier, PRO));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return showProMarkers(planQuery.data?.user, storeSubscriber);
}
