// Twin file: web-next/src/lib/storyCarousel.ts and mobile/src/lib/storyCarousel.ts stay identical.
//
// Pure logic of the story-style full-screen Carousel (components/ui/StoryCarousel.tsx on web,
// components/StoryCarousel.tsx in the app): page index state, tap zones, swipes and keys.
// No React, no DOM.

export interface StoryState {
  index: number;
  count: number;
  /** Direction of the last move, for the slide animation ("none" on first render). */
  direction: "next" | "prev" | "none";
}

export type StoryAction = { type: "next" } | { type: "prev" } | { type: "goto"; index: number } | { type: "count"; count: number };

export function storyInitial(count: number, index = 0): StoryState {
  const safe = Math.max(0, count);
  return { index: Math.min(Math.max(0, index), Math.max(0, safe - 1)), count: safe, direction: "none" };
}

export function storyReducer(state: StoryState, action: StoryAction): StoryState {
  switch (action.type) {
    case "next":
      return state.index >= state.count - 1 ? state : { ...state, index: state.index + 1, direction: "next" };
    case "prev":
      return state.index <= 0 ? state : { ...state, index: state.index - 1, direction: "prev" };
    case "goto": {
      const index = Math.min(Math.max(0, action.index), Math.max(0, state.count - 1));
      return index === state.index ? state : { ...state, index, direction: index > state.index ? "next" : "prev" };
    }
    case "count": {
      const count = Math.max(0, action.count);
      return { ...state, count, index: Math.min(state.index, Math.max(0, count - 1)) };
    }
  }
}

export function storyIsLast(state: StoryState): boolean {
  return state.index >= state.count - 1;
}

/** The left third of the screen goes back, the rest goes forward (the Stories convention). */
export function storyTapAction(x: number, width: number): "next" | "prev" {
  return width > 0 && x < width * 0.3 ? "prev" : "next";
}

/** A horizontal swipe: far enough and clearly more sideways than vertical. Left swipe = next. */
export function storySwipeAction(dx: number, dy: number, threshold = 48): "next" | "prev" | null {
  if (Math.abs(dx) < threshold || Math.abs(dx) < Math.abs(dy) * 1.5) return null;
  return dx < 0 ? "next" : "prev";
}

export function storyKeyAction(key: string): "next" | "prev" | "close" | null {
  if (key === "ArrowRight" || key === "PageDown") return "next";
  if (key === "ArrowLeft" || key === "PageUp") return "prev";
  if (key === "Escape") return "close";
  return null;
}

/** Fill of the i-th progress segment: past pages full, the current one full, later ones empty. */
export function storySegmentFill(index: number, current: number): 0 | 1 {
  return index <= current ? 1 : 0;
}
