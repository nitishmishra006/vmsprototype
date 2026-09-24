"""/api/health, /api/metrics, / and the 501 stubs."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] == 0
    assert body["database"] is True
    assert body["storage"] is True
    assert body["device"] in {"cpu", "cuda"}
    assert body["device_reason"]


def test_health_reports_features_with_fix_commands(client: TestClient) -> None:
    features = {f["name"]: f for f in client.get("/api/health").json()["features"]}
    assert {"detection", "open_vocab", "concepts", "vlm", "nl_parser"} <= set(features)
    # Stubbed probes say the HF models are missing -> the feature must say unavailable,
    # with the command that fixes it. Never a fake "available".
    assert features["open_vocab"]["available"] is False
    assert "huggingface-cli download" in features["open_vocab"]["fix_command"]


def test_health_lists_registered_models(client: TestClient) -> None:
    # Phase 0 registers no models yet, but the field must exist for the UI.
    assert client.get("/api/health").json()["models"] == []


def test_metrics_reports_rss(client: TestClient) -> None:
    body = client.get("/api/metrics").json()
    assert body["process_rss_mb"] > 0
    assert body["system_ram_total_mb"] > 0
    assert 0 <= body["system_ram_percent"] <= 100


def test_root_endpoint(client: TestClient) -> None:
    body = client.get("/").json()
    assert body["name"] == "Vision VMS"
    assert body["phase"] == 0


def test_openapi_schema_builds(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/health" in schema["paths"]
    assert "/api/settings" in schema["paths"]


def test_unimplemented_endpoints_return_501_not_fake_data(client: TestClient) -> None:
    for path in ("/api/webcams", "/api/cameras", "/api/events", "/api/learning-queue"):
        response = client.get(path)
        assert response.status_code == 501, path
        assert "Phase" in response.json()["detail"]
