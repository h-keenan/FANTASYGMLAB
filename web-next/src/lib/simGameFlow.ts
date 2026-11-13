/**
 * Fantasy Sim: the GM Game. The top-level screen state machine, pure and
 * import-light so web and the app drive the same transitions (byte-identical
 * twin, scripts/check_lib_twins.mjs). The screens own data fetching; this owns
 * "which screen am I on and why", so the gating rules (unavailable, paywall,
 * recap-then-hub) are tested once and cannot drift per platform.
 */
import {
  simGameStage,
  type SimGame,
  type SimGameGate,
  type SimGamePreview,
  type SimGameStage,
  type SimGameUpsell,
  type SimWeekRecap,
} from "./simGame";

export type SimTab = "home" | "team" | "players" | "trades" | "league" | "more";

export const SIM_TABS: { value: SimTab; label: string }[] = [
  { value: "home", label: "Home" },
  { value: "team", label: "Team" },
  { value: "players", label: "Players" },
  { value: "trades", label: "Trades" },
  { value: "league", label: "League" },
  { value: "more", label: "More" },
];

export type SimFlowView = "loading" | "unavailable" | "hub" | "setup" | "game" | "error";

export interface SimFlowState {
  view: SimFlowView;
  cause: "off" | "storage" | "busy" | null;
  message: string;
  gameId: string | null;
  stage: SimGameStage | null;
  tab: SimTab;
  /** Set when a write answered premium_required: the upsell card shows over the game. */
  paywall: { upsell: SimGameUpsell | null; preview: SimGamePreview | null } | null;
  /** Recaps from the last Advance (also_played adds playoff weeks), shown before the hub resumes. */
  recaps: SimWeekRecap[];
  /** Index of the recap currently shown. */
  recapIndex: number;
}

export const SIM_FLOW_INITIAL: SimFlowState = {
  view: "loading",
  cause: null,
  message: "",
  gameId: null,
  stage: null,
  tab: "home",
  paywall: null,
  recaps: [],
  recapIndex: 0,
};

export type SimFlowAction =
  | { type: "hub" }
  | { type: "setup" }
  | { type: "open"; game: SimGame }
  | { type: "game_updated"; game: SimGame }
  | { type: "gate"; gate: SimGameGate }
  | { type: "error"; message: string }
  | { type: "tab"; tab: SimTab }
  | { type: "advanced"; recaps: SimWeekRecap[]; game: SimGame }
  | { type: "recap_next" }
  | { type: "recap_close" }
  | { type: "dismiss_paywall" }
  | { type: "deleted" };

export function simFlowReducer(state: SimFlowState, action: SimFlowAction): SimFlowState {
  switch (action.type) {
    case "hub":
      return { ...SIM_FLOW_INITIAL, view: "hub" };
    case "setup":
      return { ...SIM_FLOW_INITIAL, view: "setup" };
    case "deleted":
      return { ...SIM_FLOW_INITIAL, view: "hub" };
    case "open":
      return {
        ...SIM_FLOW_INITIAL,
        view: "game",
        gameId: action.game.id,
        stage: simGameStage(action.game),
      };
    case "game_updated": {
      if (state.gameId !== action.game.id) return state;
      return { ...state, stage: simGameStage(action.game) };
    }
    case "gate": {
      const gate = action.gate;
      if (gate.kind === "premium") {
        // In a game the paywall overlays it (reads keep working); with no
        // game yet it is the whole screen's gate.
        return { ...state, paywall: { upsell: gate.upsell, preview: gate.preview } };
      }
      if (gate.kind === "unavailable") return { ...state, view: "unavailable", cause: gate.cause, message: "" };
      if (gate.kind === "conflict") return state;
      if (gate.kind === "blocked") return { ...state, message: gate.message };
      return state;
    }
    case "error":
      return { ...state, view: state.gameId ? state.view : "error", message: action.message };
    case "tab":
      return state.tab === action.tab ? state : { ...state, tab: action.tab };
    case "advanced":
      return {
        ...state,
        stage: simGameStage(action.game),
        recaps: action.recaps,
        recapIndex: 0,
        tab: "home",
        message: "",
      };
    case "recap_next":
      return state.recapIndex + 1 < state.recaps.length ? { ...state, recapIndex: state.recapIndex + 1 } : state;
    case "recap_close":
      return { ...state, recaps: [], recapIndex: 0 };
    case "dismiss_paywall":
      return { ...state, paywall: null };
  }
}

/** Recaps to show after an Advance: the week played, then any playoff weeks played in the same call. */
export function simRecapsFromAdvance(recap: SimWeekRecap | undefined, alsoPlayed: SimWeekRecap[] | undefined): SimWeekRecap[] {
  if (!recap) return [];
  return [recap, ...(alsoPlayed ?? [])];
}
