"""Fantasy Sim: a self-contained season simulator (MVP backend).

HARD RULE: nothing in this package may affect real FantasyDesk logic, and real
logic never imports it. Enforced by tests/test_sim_isolation.py:

* only ``services/mobile_api_service.py`` (one guarded mount) may import
  ``modules.sim``, and only ``modules.sim.api``;
* the engine files import nothing but the stdlib, numpy and ``modules.sim.*``;
* ``inputs.py`` (read-only data adapter) and ``backend.py`` (sim_* table I/O)
  are the only files allowed to touch other ``modules.*``, from an allowlist.

The package is inert unless the ``SIM_ENABLED`` env flag is on.
"""

from modules.sim.version import ENGINE_VERSION

__all__ = ["ENGINE_VERSION"]
