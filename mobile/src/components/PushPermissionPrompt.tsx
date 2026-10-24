import React, { useEffect, useRef, useState } from 'react';

import ModalFormCard, { ModalFormActions, ModalFormHint, ModalFormTitle } from './ModalFormCard';
import { trackUse } from '../lib/analytics';
import { getPushPermissionState, syncPushToken } from '../lib/pushNotifications';
import { shouldShowPushPrePrompt } from '../lib/pushPermissionPrompt';
import { getPushPromptDismissedAt, setPushPromptDismissedAt } from '../lib/pushPermissionPromptStorage';

let askedThisSession = false;

/**
 * In-app pre-prompt shown the first time a league's Dashboard has loaded
 * (coridian_, 2026-10-24). The OS permission dialog only appears after
 * "Turn on". "Not now" suppresses this for 14 days; granted/denied never
 * show it (denied users use the Settings toggle). Renders nothing otherwise.
 */
export default function PushPermissionPrompt({ leagueLoaded }: { leagueLoaded: boolean }) {
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const checking = useRef(false);

  useEffect(() => {
    if (!leagueLoaded || askedThisSession || checking.current) return;
    checking.current = true;
    void (async () => {
      try {
        const [permission, dismissedAt] = await Promise.all([
          getPushPermissionState(),
          getPushPromptDismissedAt(),
        ]);
        if (
          shouldShowPushPrePrompt({
            permission,
            leagueLoaded,
            dismissedAt,
            now: Date.now(),
            askedThisSession,
          })
        ) {
          askedThisSession = true;
          trackUse('push_permission', 'prompt_shown');
          setVisible(true);
        }
      } finally {
        checking.current = false;
      }
    })();
  }, [leagueLoaded]);

  const dismiss = () => {
    setVisible(false);
    trackUse('push_permission', 'prompt_dismissed');
    void setPushPromptDismissedAt(Date.now());
  };

  const accept = async () => {
    setBusy(true);
    try {
      await syncPushToken();
      const result = await getPushPermissionState();
      trackUse('push_permission', 'prompt_accepted', { props: { os_result: result } });
    } finally {
      setBusy(false);
      setVisible(false);
    }
  };

  return (
    <ModalFormCard visible={visible} onClose={dismiss}>
      <ModalFormTitle>Turn on notifications?</ModalFormTitle>
      <ModalFormHint>Get alerts for injuries, lineup locks and trade offers.</ModalFormHint>
      <ModalFormActions
        cancelLabel="Not now"
        onCancel={dismiss}
        cancelDisabled={busy}
        confirmLabel="Turn on"
        onConfirm={accept}
        confirmLoading={busy}
      />
    </ModalFormCard>
  );
}
