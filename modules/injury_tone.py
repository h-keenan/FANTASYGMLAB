"""The ONE injury-status tone map (audit C5).

Web and mobile each carried their own: Doubtful was amber on web and red in
the app; Questionable was amber, grey or amber depending on the screen;
substring matches ("ir" inside "Questionable"-like words) misfired. Now:

    Out / IR / Doubtful / PUP / Suspended / Inactive / NFI  -> danger  (red)
    Questionable / Probable / Day-to-day                    -> warning (amber)
    Active / Healthy                                        -> success (green)
    anything else, empty                                    -> neutral

Matching is on the whole normalized status (plus the standard Sleeper
abbreviations), never a substring. ``scripts/sync_injury_tone.py`` generates
the TypeScript copy shared byte-for-byte by web-next and mobile; a golden test
replays these rows through it.
"""

from __future__ import annotations

DANGER = (
    "out", "o", "ir", "injured reserve", "doubtful", "d", "pup", "sus", "susp", "suspended",
    "inactive", "nfi", "non-football injury", "covid", "covid-19",
)
WARNING = ("questionable", "q", "probable", "p", "day-to-day", "day to day", "dtd")
SUCCESS = ("active", "healthy")

TONE_BY_STATUS: dict[str, str] = {
    **{s: "danger" for s in DANGER},
    **{s: "warning" for s in WARNING},
    **{s: "success" for s in SUCCESS},
}

GOLDEN = (
    ("Out", "danger"), ("OUT", "danger"), ("IR", "danger"), ("Injured Reserve", "danger"),
    ("Doubtful", "danger"), ("PUP", "danger"), ("Sus", "danger"), ("Suspended", "danger"),
    ("Questionable", "warning"), ("Q", "warning"), ("Probable", "warning"), ("Day-To-Day", "warning"),
    ("Healthy", "success"), ("Active", "success"),
    ("", "neutral"), ("  ", "neutral"), ("NA", "neutral"), ("Bye", "neutral"), ("Hamstring", "neutral"),
)


def normalize(status: object) -> str:
    return " ".join(str(status if status is not None else "").strip().lower().replace("_", " ").split())


def injury_tone(status: object) -> str:
    return TONE_BY_STATUS.get(normalize(status), "neutral")


def table() -> dict:
    return {
        "tones": TONE_BY_STATUS,
        "golden": [{"status": s, "tone": t} for s, t in GOLDEN],
    }
