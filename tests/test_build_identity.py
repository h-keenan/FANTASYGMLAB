from modules.build_identity import BuildIdentity, resolve_build_identity
from modules.interface_reimagining_styles import INTERFACE_REIMAGINING_CSS


def test_render_git_identity_is_authoritative_and_shortened():
    identity = resolve_build_identity(
        {
            "RENDER_GIT_COMMIT": "EBE2E66F2E12124684CE89E49F562EAA63288D0C",
            "RENDER_GIT_BRANCH": "main",
            "DYNASTYGM_BUILD": "stale-manual-value",
        }
    )

    assert identity == BuildIdentity(revision="ebe2e66", branch="main")
    assert identity.label == "Build ebe2e66 · main"


def test_configured_build_is_used_when_render_identity_is_absent():
    identity = resolve_build_identity({"DYNASTYGM_BUILD": "release-2026.07"})

    assert identity.label == "Build release-2026.07"


def test_missing_environment_resolves_without_error_or_secret_output():
    identity = resolve_build_identity({})

    assert identity == BuildIdentity(revision="local")
    assert identity.label == "Build local"


def test_identity_sanitizes_untrusted_environment_labels():
    identity = resolve_build_identity(
        {
            "RENDER_GIT_COMMIT": "<script>",
            "DYNASTYGM_BUILD": "release<script>alert(1)</script>",
            "RENDER_GIT_BRANCH": "feature/<unsafe>",
        }
    )

    assert "<" not in identity.label
    assert ">" not in identity.label
    assert identity.revision == "release-script-alert-1-/script"
    assert identity.branch == "feature/-unsafe"


def test_build_identity_has_token_backed_nonintrusive_footer_style():
    assert ".dg-build-identity" in INTERFACE_REIMAGINING_CSS
    assert "var(--color-text-muted)" in INTERFACE_REIMAGINING_CSS
    assert "font-size: var(--font-size-badge)" in INTERFACE_REIMAGINING_CSS
