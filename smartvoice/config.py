"""Centralized configuration — all environment variables in one place."""

import os

def _get_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


def _get_int(name: str, default: str) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return int(default)


def _get_float(name: str, default: str) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return float(default)

MOCK_STT = _get_bool("MOCK_STT", "false")

# ── Reports ──────────────────────────────────────────────────────────────
# Thai TrueType font for the Dashboard PDF. Blank = use the first one found
# among the usual system fonts (Tahoma / Leelawadee on Windows, Noto Sans Thai
# or TLWG fonts on Linux).
REPORT_FONT_PATH = os.getenv("REPORT_FONT_PATH", "")

# ── Database ─────────────────────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "data/smartvoice.db")

# ── Case Auto-Assignment ─────────────────────────────────────────────────
# When a new call arrives from a customer who has an open case with a recent
# sibling call (within this many hours), auto-attach WITHOUT asking the LLM.
# This handles the common "customer called back 5 min later" / "dropped call
# resumed" pattern, which LLM topic-matching misses when topics drift.
# Set to 0 to disable the short-circuit and always use LLM matching.
CASE_RECENCY_HOURS = _get_float("CASE_RECENCY_HOURS", "4.0")

# Reset calls that were left in `processing` after the app/process was killed.
# Set to 0 to disable automatic recovery.
PROCESSING_STALE_MINUTES = _get_int("PROCESSING_STALE_MINUTES", "180")


def api_settings() -> dict:
    stt_provider = os.getenv("STT_PROVIDER", "pyannote_api").strip().lower()
    llm_provider = os.getenv("LLM_PROVIDER", "typhoon").strip().lower()
    if stt_provider != "pyannote_api":
        raise ValueError("Local STT was removed; set STT_PROVIDER=pyannote_api in Settings")
    if llm_provider != "typhoon":
        raise ValueError("Local LLM was removed; set LLM_PROVIDER=typhoon in Settings")
    return {
        "stt_provider": stt_provider,
        "llm_provider": llm_provider,
        "typhoon_key": os.getenv("TYPHOON_API_KEY", "").strip(),
        "typhoon_model": os.getenv("TYPHOON_MODEL", "typhoon-v2.5-30b-a3b-instruct").strip(),
        "pyannote_key": os.getenv("PYANNOTE_API_KEY", "").strip(),
        "pyannote_model": os.getenv("PYANNOTE_API_MODEL", "precision-2").strip(),
        "stt_model": os.getenv("STT_API_MODEL", "faster-whisper-large-v3-turbo").strip(),
        "timeout": max(1, _get_int("AI_API_TIMEOUT", "120")),
        "job_timeout": max(1, _get_int("AI_JOB_TIMEOUT", "1800")),
        "max_tokens": max(256, _get_int("TYPHOON_MAX_TOKENS", "4096")),
        "cleanup_chunk_chars": max(1, _get_int("TYPHOON_CLEANUP_CHUNK_CHARS", "3200")),
    }
