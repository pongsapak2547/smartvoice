from unittest import mock

import pytest

from smartvoice import preflight


@pytest.fixture(autouse=True)
def api_environment(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "pyannote_api")
    monkeypatch.setenv("LLM_PROVIDER", "typhoon")
    monkeypatch.setenv("TYPHOON_API_KEY", "")
    monkeypatch.setenv("PYANNOTE_API_KEY", "")
    monkeypatch.setenv("PYANNOTE_API_MODEL", "precision-2")
    monkeypatch.setenv("STT_API_MODEL", "faster-whisper-large-v3-turbo")
    monkeypatch.setattr(preflight, "MOCK_STT", False)


def test_llm_requires_key_even_with_mock_speech(monkeypatch):
    monkeypatch.setattr(preflight, "MOCK_STT", True)
    assert preflight.get_llm_readiness() == (False, "missing TYPHOON_API_KEY")


@pytest.mark.parametrize("check,key", [(preflight.get_llm_readiness, "TYPHOON_API_KEY"), (preflight.get_pyannote_access_readiness, "PYANNOTE_API_KEY")])
def test_api_readiness_requires_key(check, key):
    assert check() == (False, "missing " + key)


@pytest.mark.parametrize("check,key", [(preflight.get_llm_readiness, "TYPHOON_API_KEY"), (preflight.get_pyannote_access_readiness, "PYANNOTE_API_KEY")])
def test_configured_key_is_not_claimed_verified(monkeypatch, check, key):
    monkeypatch.setenv(key, "test-secret")
    ready, detail = check()
    assert ready
    assert "not verified" in detail
    assert "test-secret" not in detail


@pytest.mark.parametrize("key,value", [("PYANNOTE_API_MODEL", "community-1"), ("STT_API_MODEL", "unsupported")])
def test_unsupported_speech_model_is_not_ready(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    assert not preflight.get_pyannote_access_readiness()[0]


def test_mock_speech_does_not_require_key(monkeypatch):
    monkeypatch.setattr(preflight, "MOCK_STT", True)
    assert preflight.get_pyannote_access_readiness() == (True, "not required in demo mode")


@pytest.mark.parametrize("key,value", [("STT_PROVIDER", "local"), ("LLM_PROVIDER", "ollama")])
def test_legacy_configuration_returns_actionable_error(monkeypatch, key, value):
    monkeypatch.setenv(key, value)
    assert not preflight.get_llm_readiness()[0]
    assert not preflight.get_pyannote_access_readiness()[0]
    checks = preflight.run_preflight_checks()
    assert len(checks) == 1 and not checks[0].ok
    assert key in checks[0].detail


def test_run_preflight_reports_demo_and_api_keys(monkeypatch):
    monkeypatch.setattr(preflight, "MOCK_STT", True)
    with mock.patch.object(preflight, "is_auth_configured", return_value=True), mock.patch.object(preflight, "default_admin_password_unchanged", return_value=False):
        checks = {check.name: check for check in preflight.run_preflight_checks()}
    assert not checks["Speech-to-text mode"].ok
    assert checks["Pyannote access"].ok
    assert not checks["Typhoon API"].ok
    assert "Ollama CLI" not in checks
    assert "HuggingFace token" not in checks
