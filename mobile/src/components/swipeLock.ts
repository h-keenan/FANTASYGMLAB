import { makeMutable } from 'react-native-reanimated';

/**
 * Set while a finger is down inside a horizontal scroller (chip rows, depth-chart / draft strips, charts). The shared
 * Tabs swipe reads it on the UI thread and never takes such a touch. Spread `swipeLockProps` onto any horizontal
 * ScrollView that can sit inside a tab panel.
 */
export const swipeLock = makeMutable(false);

export const swipeLockProps = {
  onTouchStart: () => {
    swipeLock.value = true;
  },
  onTouchEnd: () => {
    swipeLock.value = false;
  },
  onTouchCancel: () => {
    swipeLock.value = false;
  },
};
