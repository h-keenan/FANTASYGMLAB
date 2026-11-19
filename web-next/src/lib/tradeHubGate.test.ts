import { describe, expect, it } from "vitest";

import { TRADE_HUB_UPGRADE_LABEL, tradeHubGateBody, tradeHubGateTitle } from "./tradeHubGate";

describe("trade hub gate copy (one copy for web and the app)", () => {
  it("counts the hidden ideas on this board", () => {
    expect(tradeHubGateTitle(1)).toBe("1 more trade idea on this board");
    expect(tradeHubGateTitle(3)).toBe("3 more trade ideas on this board");
  });

  it("says Pro unlocks the board, and mentions an ad only when one can run", () => {
    expect(tradeHubGateBody(2, null)).toBe("Free shows the top 2. Go Pro to unlock the full board.");
    expect(tradeHubGateBody(2, 3)).toContain("Watch a quick ad to reveal 3 more");
    expect(TRADE_HUB_UPGRADE_LABEL).toBe("Upgrade to Pro");
  });
});
