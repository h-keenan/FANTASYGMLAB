"""Characterization of the former per-module float coercers (audit item 7).

``tests/fixtures/coerce_matrix_golden.json`` froze the results of every old private helper over a shared input matrix
(``coerce_matrix_support.MATRIX``) BEFORE they were replaced by ``modules/coerce.py`` variants. This runs the same
matrix through whatever each module binds now and must match the frozen results exactly. Never regenerate the golden
to make this pass; a mismatch means a call site was moved to a variant with different semantics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.coerce_matrix_support import REGISTRY, load, resolve, run_matrix

GOLDEN = json.loads((Path(__file__).parent / "fixtures" / "coerce_matrix_golden.json").read_text())


@pytest.mark.parametrize("module,old,new", REGISTRY, ids=[f"{m}.{o}" for m, o, _ in REGISTRY])
def test_call_site_matches_frozen_matrix(module, old, new):
    mod = load(module)
    fn = resolve(mod, new)
    frozen = GOLDEN[f"{module}.{old}"]
    # the old helper took no `default` argument when the frozen matrix has no `|default` rows
    assert run_matrix(fn, probe_default="None|default" in frozen) == frozen
