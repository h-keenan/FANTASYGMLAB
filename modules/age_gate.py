"""Web COPPA age gate for account signup.

Mirrors mobile's gate (mobile/src/lib/ageGate.ts / mobile/src/components/
AgeGate.tsx): a neutral date-of-birth entry, not an "I am 13 or older"
checkbox (the FTC treats a self-attestation checkbox as coaching the answer
rather than a real age check). Shown once per browser session, inline in
the signup form, before an account can be created.

Nothing about the entered date is persisted anywhere — not in
``st.session_state`` beyond the lifetime of the current browser session, not
in any database table, not in an export. Only a plain pass/fail boolean is
kept (session-scoped), so a user isn't asked again after passing once in the
same session. Unlike mobile's ``AsyncStorage`` flag, this does not survive a
fresh page load; that's an accepted platform difference (Streamlit has no
durable, privacy-safe per-browser storage of its own to mirror
AsyncStorage with) — the important COPPA property (nothing about age is
retained) still holds.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from modules import brand_identity

MINIMUM_AGE = 13


def calculate_age(birth_date: date, today: date | None = None) -> int:
    today = today or date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def render_age_confirmation(key_prefix: str) -> bool:
    """Render the DOB gate inline; return True once a >= MINIMUM_AGE date of
    birth has been confirmed for this browser session.

    Callers must not proceed to account creation (``auth_supabase.sign_up``)
    until this returns True. Returns False both before an answer is given
    and after an under-age result (which renders a terminal, non-retryable
    block message instead of the entry fields, matching mobile's
    ``AgeGate.tsx`` blocked state).
    """

    passed_key = f"_{key_prefix}_age_gate_passed"
    blocked_key = f"_{key_prefix}_age_gate_blocked"

    if st.session_state.get(passed_key):
        return True

    if st.session_state.get(blocked_key):
        st.error(
            f"You must be at least {MINIMUM_AGE} years old to use "
            f"{brand_identity.PRODUCT_NAME}. Nothing you entered has been saved."
        )
        return False

    st.caption(
        f"You must be at least {MINIMUM_AGE} to create an account. "
        "Enter your date of birth — it is not stored."
    )
    cols = st.columns(3)
    month = cols[0].text_input("MM", key=f"{key_prefix}_age_gate_month", max_chars=2, placeholder="MM")
    day = cols[1].text_input("DD", key=f"{key_prefix}_age_gate_day", max_chars=2, placeholder="DD")
    year = cols[2].text_input("YYYY", key=f"{key_prefix}_age_gate_year", max_chars=4, placeholder="YYYY")

    if st.button("Confirm date of birth", key=f"{key_prefix}_age_gate_continue"):
        try:
            birth_date = date(int(year), int(month), int(day))
        except (TypeError, ValueError):
            st.warning("Enter a valid date of birth.")
            return False
        if birth_date > date.today() or birth_date.year < 1900:
            st.warning("Enter a valid date of birth.")
            return False
        if calculate_age(birth_date) < MINIMUM_AGE:
            st.session_state[blocked_key] = True
        else:
            st.session_state[passed_key] = True
        st.rerun()

    return False
