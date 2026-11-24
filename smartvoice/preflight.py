import os
import sys
from dataclasses import dataclass

from smartvoice.auth import bootstrap_password_error, default_admin_password_unchanged, is_auth_configured
from smartvoice.config import MOCK_STT, api_settings


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    severity: str = "warning"


def get_llm_readiness() -> tuple[bool, str]:
    try:
        settings = api_settings()
    except ValueError as exc:
        return False, str(exc)
    return bool(settings["typhoon_key"]), "Typhoon API key configured (not verified)" if settings["typhoon_key"] else "missing TYPHOON_API_KEY"


def get_pyannote_access_readiness() -> tuple[bool, str]:
    try:
        settings = api_settings()
    except ValueError as exc:
        return False, str(exc)
    if not MOCK_STT:
        if settings["pyannote_model"] not in {"precision-2", "precision-3"}:
            return False, "combined transcription requires precision-2 or precision-3"
        if settings["stt_model"] != "faster-whisper-large-v3-turbo":
            return False, "Thai API backend requires faster-whisper-large-v3-turbo"
        return bool(settings["pyannote_key"]), "pyannoteAI key configured (not verified)" if settings["pyannote_key"] else "missing PYANNOTE_API_KEY"
    return True, "not required in demo mode"


def run_preflight_checks() -> list[CheckResult]:
    try:
        api_settings()
    except ValueError as exc:
        return [CheckResult("API configuration", False, str(exc), "error")]
    default_password = default_admin_password_unchanged()
    checks = [
        CheckResult("Python", (3, 10) <= sys.version_info[:2] <= (3, 12),
                    f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} (API mode: 3.10–3.12)", "error"),
        CheckResult("Speech-to-text mode", not MOCK_STT,
                    "Whisper + pyannoteAI API" if not MOCK_STT else "demo mode enabled; real STT and diarization are skipped"),
        CheckResult("Authentication", is_auth_configured() and not default_password,
                    "the bootstrap 'admin' account still uses the default password" if default_password
                    else "staff accounts are configured" if is_auth_configured()
                    else "no account found; open the app once to seed the bootstrap admin"),
    ]
    bootstrap_error = bootstrap_password_error()
    if bootstrap_error:
        checks.append(CheckResult(
            "Bootstrap password", False,
            f"{bootstrap_error}; no first Admin account is created until it is fixed", "error",
        ))
    for name, readiness in (("Pyannote access", get_pyannote_access_readiness), ("Typhoon API", get_llm_readiness)):
        ready, detail = readiness()
        checks.append(CheckResult(name, ready, detail, "error"))
    data_dir = os.path.abspath("data")
    checks.append(CheckResult("Local data directory", os.path.isdir(data_dir), data_dir))
    return checks
