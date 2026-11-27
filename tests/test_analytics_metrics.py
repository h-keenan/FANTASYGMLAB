from __future__ import annotations

from unittest.mock import Mock, patch

from modules import account_acquisition, analytics_metrics as am
from modules import launch_analytics as la

DAY = 86400.0
NOW = 1_800_000_000.0  # fixed; day 0 = floor(NOW / DAY)
D0 = NOW - (NOW % DAY)


def row(event, ts, anon="", acct="", sess="", env="production", **props):
    return {
        "event": event,
        "ts": ts,
        "anon_id": anon,
        "user_key": acct,
        "account_hash": acct,
        "session_key": sess or anon,
        "environment": env,
        "props": props,
    }


def test_anon_to_account_stitching_counts_one_person():
    rows = [
        row("landing_viewed", D0 + 10, anon="a1", sess="s1"),
        row("signup_completed", D0 + 20, anon="a1", acct="acct_1", sess="s1"),
        row("pqv_opened", D0 + 30, anon="", acct="acct_1", sess="s2"),
    ]
    out = am.compute_audience_metrics(rows, now=D0 + 100)
    assert out["dau"] == 1 and out["mau"] == 1
    assert out["windows"]["dau"]["sessions"] == 2


def test_session_key_never_counts_as_a_person():
    # Same anonymous browser, two different sessions on two days: one visitor, not two.
    rows = [
        row("landing_viewed", D0 - DAY + 5, anon="a1", sess="s1"),
        row("landing_viewed", D0 + 5, anon="a1", sess="s2"),
    ]
    out = am.compute_audience_metrics(rows, now=D0 + 100)
    assert out["wau"] == 1
    assert out["windows"]["wau"]["sessions"] == 2
    assert la._identity_key(rows[0]) == "a1"


def test_shared_browser_is_not_merged():
    rows = [
        row("a", D0 + 1, anon="a1", acct="acct_1"),
        row("a", D0 + 2, anon="a1", acct="acct_2"),
        row("a", D0 + 3, anon="a1"),
    ]
    links = am.build_identity_links(rows)
    assert "a1" not in links
    assert am.compute_audience_metrics(rows, now=D0 + 100)["dau"] == 3


def test_separated_metrics_guest_registered_engaged():
    rows = [
        row("landing_viewed", D0 + 1, anon="v1"),  # anonymous visitor
        row("page_view", D0 + 2, acct="acct_g", account_kind="guest"),  # guest
        row("pqv_opened", D0 + 3, acct="acct_r", account_kind="registered"),  # registered + engaged
        row("feature_use", D0 + 4, anon="v2", feature="sample_league", action="viewed", demo=True),  # demo only
        row("page_view", D0 + 5, acct="acct_l"),  # legacy row, no account_kind
    ]
    w = am.compute_audience_metrics(rows, now=D0 + 100)["windows"]["dau"]
    assert w["unique_visitors"] == 5
    assert w["guest_users"] == 1
    assert w["registered_users"] == 2  # acct_r + legacy acct_l
    assert w["legacy_unclassified_users"] == 1
    assert w["engaged_users"] == 1  # demo feature_use never engaged
    assert w["anonymous_visitors"] == 2


def test_guest_who_upgrades_counts_as_registered():
    rows = [
        row("page_view", D0 + 1, acct="acct_u", account_kind="guest"),
        row("pqv_opened", D0 + 2, acct="acct_u", account_kind="registered"),
    ]
    w = am.compute_audience_metrics(rows, now=D0 + 100)["windows"]["dau"]
    assert w["guest_users"] == 0 and w["registered_users"] == 1


def test_history_is_recomputed_with_same_definition():
    rows = [row("pqv_opened", D0 - i * DAY + 5, anon=f"a{i}") for i in range(10)]
    out = am.compute_audience_metrics(rows, now=D0 + 100, history_days=5)
    today = out["history"][-1]
    assert today["date"] == out["as_of"]
    assert today["dau"] == out["dau"] and today["mau"] == out["mau"]
    assert [h["dau"] for h in out["history"]] == [1] * 6
    assert out["history"][0]["wau"] == 5 and out["history"][-1]["wau"] == 7 and out["mau"] == 10


def test_clean_rows_drops_test_environment():
    rows = [row("pqv_opened", D0 + 1, anon="a1", env="test"), row("pqv_opened", D0 + 2, anon="a2")]
    kept, _bots = am.clean_rows(rows)
    assert [r["anon_id"] for r in kept] == ["a2"]


def test_signup_dedupe_and_method_breakdown():
    rows = [
        row("signup_completed", D0 + 1, acct="acct_1", signup_method="google"),
        row("signup_completed", D0 + 2, acct="acct_1", signup_method="google"),
        row("signup_completed", D0 + 3, acct="acct_2", signup_method="email"),
    ]
    s = am.compute_audience_metrics(rows, now=D0 + 100)["signups"]
    assert s["distinct_signups"] == 2
    assert s["by_method"] == {"email": 1, "google": 1}


def test_signup_reconciliation_against_accounts():
    rows = [row("signup_completed", D0 + 1, acct="acct_1", signup_method="email")]
    accounts = [
        {"is_guest": False, "signup_method": "email"},
        {"is_guest": False, "signup_method": "google"},
        {"is_guest": True, "signup_method": "guest"},
    ]
    rec = am.signup_reconciliation(rows, accounts)
    assert rec["accounts_created_registered"] == 2
    assert rec["accounts_created_guest"] == 1
    assert rec["unlogged_signups"] == 1
    assert am.signup_reconciliation(rows, None)["available"] is False


def test_sample_league_funnel_converts_only_after_view():
    rows = [
        row("feature_use", D0 + 1, anon="a1", feature="sample_league", action="viewed", demo=True),
        row("feature_use", D0 + 2, anon="a1", feature="sample_league", action="tab", demo=True),
        row("signup_completed", D0 + 9, anon="a1", acct="acct_1"),
        row("feature_use", D0 + 10, anon="a2", feature="sample_league", action="viewed", demo=True),
        row("signup_completed", D0 + 5, anon="a2", acct="acct_2"),  # signed up BEFORE viewing
    ]
    f = am.sample_league_funnel(rows)
    assert f["viewers"] == 2 and f["engaged"] == 1 and f["signed_up_after_view"] == 1
    assert f["view_to_signup_pct"] == 50.0


def test_try_link_funnel_by_topic_and_demo_never_engaged():
    rows = [
        row("feature_use", D0 + 1, anon="a1", feature="try_link", action="viewed", item_kind="trade", demo=True),
        row("feature_use", D0 + 2, anon="a1", feature="try_link", action="cta_click", item_kind="trade", demo=True),
        row("signup_completed", D0 + 9, anon="a1", acct="acct_1"),
        row("feature_use", D0 + 3, anon="a2", feature="try_link", action="viewed", item_kind="waivers", demo=True),
        row("feature_use", D0 + 4, anon="a3", feature="try_link", action="viewed", item_kind="trade", demo=True),
        row("signup_completed", D0 + 1, anon="a3", acct="acct_3"),  # signed up BEFORE viewing
    ]
    f = am.try_link_funnel(rows)
    assert f["viewers"] == 3 and f["cta_clicked"] == 1 and f["signed_up_after_view"] == 1
    assert f["by_topic"]["trade"] == {"viewers": 2, "cta_clicked": 1, "signed_up_after_view": 1, "view_to_signup_pct": 50.0}
    assert f["by_topic"]["waivers"]["viewers"] == 1 and f["by_topic"]["waivers"]["signed_up_after_view"] == 0
    assert am.try_link_funnel([])["view_to_signup_pct"] is None
    # demo views never count as engaged, with or without the demo flag
    assert not am._is_engaged(row("feature_use", D0, anon="x", feature="try_link", action="viewed", demo=True))
    assert not am._is_engaged(row("feature_use", D0, anon="x", feature="try_link", action="viewed"))


def test_fetch_reports_truncation_at_cap():
    cfg = la.AnalyticsSupabaseConfig(url="https://x.supabase.co", service_role_key="k")
    page = Mock(status_code=200)
    page.json.return_value = [{"event": "page_view", "ts": float(t)} for t in (9, 8, 7)]
    with patch("requests.get", return_value=page):
        rows, ok, truncated = la._fetch_events_supabase_meta(cfg, limit=3)
    assert ok and truncated and len(rows) == 3
    short = Mock(status_code=200)
    short.json.return_value = [{"event": "page_view", "ts": 1.0}]
    with patch("requests.get", return_value=short):
        _rows, _ok, truncated = la._fetch_events_supabase_meta(cfg, limit=3)
    assert truncated is False


def test_max_read_rows_default_exceeds_old_20k_cap(monkeypatch):
    monkeypatch.delenv(la.MAX_READ_ROWS_ENV, raising=False)
    assert la.max_read_rows() > 20_000
    monkeypatch.setenv(la.MAX_READ_ROWS_ENV, "5000")
    assert la.max_read_rows() == 5000


def test_account_kind_and_signup_method():
    assert account_acquisition.account_kind_for(None) == "visitor"
    assert account_acquisition.account_kind_for({"id": "u", "is_anonymous": True}) == "guest"
    assert account_acquisition.account_kind_for({"id": "u"}) == "registered"
    assert account_acquisition.signup_method_for({"app_metadata": {"provider": "Apple"}}) == "apple"
    assert account_acquisition.signup_method_for({"app_metadata": {"provider": "email"}}) == "email"


def test_record_account_acquisition_dedupes_and_degrades(monkeypatch):
    account_acquisition.reset_cache()
    monkeypatch.setattr(la, "analytics_enabled", lambda **kw: True)
    monkeypatch.setattr(
        la, "load_analytics_supabase_config",
        lambda: la.AnalyticsSupabaseConfig(url="https://x.supabase.co", service_role_key="k"),
    )
    monkeypatch.setattr(la, "_spawn_background", lambda fn: fn())
    user = {"id": "u1", "app_metadata": {"provider": "google"}, "created_at": "2026-11-20T00:00:00Z"}
    props = {"utm_source": "tiktok", "lt_utm_source": "x", "platform": "web", "email": "no@x"}
    ok = Mock(status_code=201, text="")
    with patch("requests.post", return_value=ok) as post, patch("requests.patch") as patch_req:
        assert account_acquisition.record_account_acquisition(user, props) is True
        assert account_acquisition.record_account_acquisition(user, props) is False  # deduped in-process
    sent = post.call_args.kwargs["json"]
    assert sent["user_id"] == "u1" and sent["signup_method"] == "google" and sent["is_guest"] is False
    assert sent["utm_source"] == "tiktok" and sent["lt_utm_source"] == "x"
    assert "email" not in sent
    assert patch_req.called  # registered -> flips a prior guest row
    # missing table -> disables further writes quietly
    account_acquisition.reset_cache()
    missing = Mock(status_code=404, text='relation "account_acquisition" does not exist')
    with patch("requests.post", return_value=missing):
        account_acquisition.record_account_acquisition({"id": "u2"}, {})
    with patch("requests.post") as post2:
        assert account_acquisition.record_account_acquisition({"id": "u3"}, {}) is False
        post2.assert_not_called()
    account_acquisition.reset_cache()


def test_mobile_app_okhttp_ua_is_not_a_bot_but_scripts_still_are():
    assert la.is_bot_user_agent("okhttp/4.12.0") is True  # generic filter unchanged
    assert la.is_bot_user_agent_for_platform("okhttp/4.12.0", "android") is False
    assert la.is_bot_user_agent_for_platform("okhttp/4.12.0", "web") is True
    assert la.is_bot_user_agent_for_platform("curl/8.0", "android") is True
    assert la.is_bot_user_agent_for_platform("Googlebot/2.1", "ios") is True
