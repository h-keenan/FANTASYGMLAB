from html import escape


def _clean(value, fallback=""):
    text = "" if value is None else str(value)
    text = text.strip()
    return text or fallback


def _initials(label: str) -> str:
    words = [part for part in _clean(label, "DG").replace("/", " ").split() if part]
    if not words:
        return "DG"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][:1] + words[1][:1]).upper()


def league_identity_header_html(
    *,
    league_name: str = "",
    team_name: str = "",
    platform: str = "",
    avatar_url: str = "",
    has_league: bool = False,
    account_label: str = "",
    entitlement_label: str = "",
) -> str:
    """Return the compact top app identity header markup."""
    safe_platform = _clean(platform, "Sleeper")
    safe_account = _clean(account_label, "Guest")
    safe_entitlement = _clean(entitlement_label, "Free")

    if has_league:
        title = _clean(league_name, "Selected League")
        subtitle_bits = [
            _clean(team_name, "Current team"),
            safe_platform,
            safe_account,
            safe_entitlement,
        ]
        action_text = "Switch League / Refresh / Import / Premium"
        avatar_label = _clean(team_name, league_name)
    else:
        title = "DynastyGM"
        subtitle_bits = ["Import a Sleeper league", "ESPN experimental", safe_account, safe_entitlement]
        action_text = "Import League / Account / Premium"
        avatar_label = "DynastyGM"

    subtitle = " · ".join(escape(part) for part in subtitle_bits if part)
    avatar_src = _clean(avatar_url)
    if avatar_src:
        avatar_html = (
            "<div class='app-top-league-avatar'>"
            f"<img src='{escape(avatar_src, quote=True)}' alt='{escape(avatar_label)} avatar' />"
            "</div>"
        )
    else:
        avatar_html = (
            "<div class='app-top-league-avatar app-top-league-avatar-fallback'>"
            f"{escape(_initials(avatar_label))}"
            "</div>"
        )

    return (
        "<div class='app-top-league-header'>"
        f"{avatar_html}"
        "<div class='app-top-league-copy'>"
        f"<div class='app-top-league-kicker'>{escape(safe_platform if has_league else 'Founder beta')}</div>"
        f"<div class='app-top-league-title'>{escape(title)}</div>"
        f"<div class='app-top-league-meta'>{subtitle}</div>"
        "</div>"
        f"<div class='app-top-league-actions-label'>{escape(action_text)}</div>"
        "</div>"
    )
