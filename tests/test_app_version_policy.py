from modules import app_version_policy as p


def test_unset_means_no_gate_and_default_play_url():
    cfg = p.build_app_config({})
    assert cfg["min_app_version"] == {"ios": "", "android": ""}
    assert cfg["store_urls"]["android"] == p.DEFAULT_ANDROID_STORE_URL
    assert cfg["store_urls"]["ios"] == ""


def test_valid_values_normalized_and_invalid_ignored():
    cfg = p.build_app_config({"MIN_APP_VERSION_IOS": " v1.2.0 ", "MIN_APP_VERSION_ANDROID": "garbage",
                              "APP_STORE_URL_IOS": "https://apps.apple.com/app/id1"})
    assert cfg["min_app_version"] == {"ios": "1.2.0", "android": ""}
    assert cfg["store_urls"]["ios"] == "https://apps.apple.com/app/id1"


def test_endpoint_is_public_and_returns_config(monkeypatch):
    from fastapi.testclient import TestClient
    from services import mobile_api_service as svc

    monkeypatch.setenv("MIN_APP_VERSION_ANDROID", "2.0.0")
    res = TestClient(svc.app).get("/v1/app-config")
    assert res.status_code == 200
    assert res.json()["min_app_version"]["android"] == "2.0.0"
