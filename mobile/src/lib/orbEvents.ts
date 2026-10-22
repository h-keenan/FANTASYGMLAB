import { DeviceEventEmitter } from 'react-native';

/** Fired by the Dashboard header's search icon; GmOrb opens its sheet on the search field. */
export const OPEN_ORB_SEARCH_EVENT = 'fd:open-search';
/** Fired by the Dashboard's Guess the Player card to re-open today's prompt. */
export const OPEN_GUESS_EVENT = 'fd:open-guess';

export function requestOrbSearch(): void {
  DeviceEventEmitter.emit(OPEN_ORB_SEARCH_EVENT);
}

export function requestGuessThePlayer(): void {
  DeviceEventEmitter.emit(OPEN_GUESS_EVENT);
}
