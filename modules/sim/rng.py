"""Order-independent randomness for the sim.

Every random draw comes from a generator derived from
``SeedSequence(world_seed, spawn_key=(week, subsystem, key))``. The same
(seed, week, subsystem, key) always yields the same stream no matter what ran
before it, so a counterfactual replay (a vetoed trade, a different strategy)
shares every unaffected random number with the base run (common random
numbers), and a future "shareable seed" feature only has to carry the seed.
"""

from __future__ import annotations

import numpy as np

SUBSYSTEMS = {
    "score": 1,
    "injury": 2,
    "waiver": 3,
    "trade": 4,
    "persona": 5,
    "schedule": 6,
    "form": 7,
    # The interactive GM game (game_*.py). Same keyed-stream rule: the draws a
    # decision can touch never shift draws it cannot.
    "draft": 8,
    "gprofile": 9,
    "gscore": 10,
    "ginjury": 11,
    "gwaiver": 12,
    "gtrade": 13,
    "gsetup": 14,
    "goffer": 15,
    # Dynasty mode (multi-season). ``week`` carries the season number.
    "gage": 16,
    "grookie": 17,
    "grdraft": 18,
    "gseason": 19,
}


class WorldRng:
    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        if self.seed < 0:
            raise ValueError("seed must be non-negative")

    def stream(self, week: int, subsystem: str, key: int = 0) -> np.random.Generator:
        sequence = np.random.SeedSequence(
            entropy=self.seed, spawn_key=(int(week), SUBSYSTEMS[subsystem], int(key))
        )
        return np.random.Generator(np.random.PCG64(sequence))
