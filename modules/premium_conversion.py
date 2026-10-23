"""Premium checkout-intent session keys (cleared on sign-out by auth_supabase)."""

from __future__ import annotations
from typing import Any, MutableMapping

CHECKOUT_INTENT_KEY = "_premium_checkout_intent"
RESUME_CHECKOUT_FLAG = "_premium_resume_checkout"


def clear_checkout_intent(
    session_state: MutableMapping[str, Any],
) -> None:
    state = session_state
    state.pop(CHECKOUT_INTENT_KEY, None)
    state.pop(RESUME_CHECKOUT_FLAG, None)
