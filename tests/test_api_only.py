from pathlib import Path
import subprocess
import sys

import pytest

from smartvoice import config


def test_default_providers_are_remote(monkeypatch):
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    settings = config.api_settings()
    assert settings["stt_provider"] == "pyannote_api"
    assert settings["llm_provider"] == "typhoon"


@pytest.mark.parametrize("key,value", [("STT_PROVIDER", "local"), ("LLM_PROVIDER", "ollama")])
def test_retired_providers_are_rejected(monkeypatch, key, value):
    monkeypatch.setenv("STT_PROVIDER", "pyannote_api")
    monkeypatch.setenv("LLM_PROVIDER", "typhoon")
    monkeypatch.setenv(key, value)
    with pytest.raises(ValueError, match=key):
        config.api_settings()


def test_runtime_imports_without_local_ai_packages():
    code = '''
import importlib.abc
import sys
class BlockLocalAI(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] in {"torch", "torchaudio", "transformers", "faster_whisper", "pyannote", "huggingface_hub", "soundfile", "noisereduce", "scipy"}:
            raise AssertionError("Local AI dependency imported: " + fullname)
sys.meta_path.insert(0, BlockLocalAI())
from smartvoice import pipeline, preflight
from smartvoice.stt import orchestrator
assert not hasattr(orchestrator, "_real_transcribe_diarized")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_installation_does_not_include_local_ai():
    manifests = Path("pyproject.toml").read_text(encoding="utf-8") + Path("requirements.txt").read_text(encoding="utf-8") + Path("requirements-api.txt").read_text(encoding="utf-8")
    for package in ("torch", "transformers", "faster-whisper", "pyannote.audio", "huggingface_hub", "soundfile", "noisereduce", "scipy"):
        assert package not in manifests
    for filename in ("run.bat", "run.sh"):
        launcher = Path(filename).read_text(encoding="utf-8").lower()
        assert "ollama" not in launcher
        assert "torch" not in launcher
        assert "nvidia-smi" not in launcher
