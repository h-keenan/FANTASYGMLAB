"use client";

import { useState, type ReactNode } from "react";
import { ButtonLink } from "@/components/Button";
import { PillRow } from "@/components/PillRow";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
import { CONNECT_MODES, SIM_QUICKSTART_PATH, type ConnectMode } from "@/lib/connectFlow";
import { trackOnboarding } from "@/lib/onboardingAnalytics";

/**
 * The onboarding connect step's three ways in: connect a league (default), look around a sample league, or play
 * Fantasy Sim, which needs no league. Sample and Sim reuse the existing routes. Mobile twin: ConnectModeTabs in
 * mobile/src/components/ConnectModeTabs.tsx.
 */
export function ConnectModeTabs({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<ConnectMode>("connect");
  const current = CONNECT_MODES.find((m) => m.key === mode) ?? CONNECT_MODES[0];
  return (
    <div className="flex flex-col gap-3" data-testid="connect-mode-tabs">
      <PillRow
        ariaLabel="How to start"
        variant="fill"
        options={CONNECT_MODES.map((m) => ({ label: m.label, value: m.key }))}
        active={mode}
        onSelect={(value) => setMode(value as ConnectMode)}
      />
      {mode === "connect" ? (
        children
      ) : (
        <div className="flex flex-col gap-3">
          <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>{current.blurb}</p>
          {mode === "sample" ? (
            <SampleLeagueButton surface="connect_step" variant="primary" />
          ) : (
            <ButtonLink
              href={SIM_QUICKSTART_PATH}
              variant="primary"
              fullWidth
              data-testid="sim-quickstart-button"
              onClick={() => trackOnboarding("sim_selected", { step: "connect", step_index: 2 })}
            >
              {current.action}
            </ButtonLink>
          )}
        </div>
      )}
    </div>
  );
}
