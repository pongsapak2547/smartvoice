import io
import json
import socket
import sqlite3
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

from smartvoice import audit, auth, config, db, env_settings, file_manager, ollama_client, pipeline, preflight, processing_control, prompts
from smartvoice.stt import orchestrator


def response(data, status=200):
    result = Mock(status_code=status)
    result.json.return_value = data
    return result


@pytest.fixture
def api_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "typhoon")
    monkeypatch.setenv("STT_PROVIDER", "pyannote_api")
    monkeypatch.setenv("TYPHOON_API_KEY", "test-typhoon")
    monkeypatch.setenv("PYANNOTE_API_KEY", "test-pyannote")
    monkeypatch.setenv("MOCK_STT", "false")


def test_typhoon_uses_chat_completions_and_configurable_model(api_env, monkeypatch):
    monkeypatch.setenv("TYPHOON_MODEL", "typhoon-v2.1-12b-instruct")
    post = Mock(return_value=response({"choices": [{"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}]}))
    monkeypatch.setattr(requests, "post", post)
    assert json.loads(ollama_client.chat("system", "user", json_mode=True)) == {"ok": True}
    args, kwargs = post.call_args
    assert args[0] == "https://api.opentyphoon.ai/v1/chat/completions"
    assert kwargs["json"]["model"] == "typhoon-v2.1-12b-instruct"
    assert "options" not in kwargs["json"]
    assert kwargs["headers"]["Authorization"] == "Bearer test-typhoon"


def test_missing_key_fails_before_network(api_env, monkeypatch):
    monkeypatch.delenv("TYPHOON_API_KEY")
    post = Mock()
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(ValueError, match="TYPHOON_API_KEY"):
        ollama_client.chat("system", "user")
    post.assert_not_called()


def test_truncated_llm_output_is_not_accepted(api_env, monkeypatch):
    monkeypatch.setattr(requests, "post", Mock(return_value=response({"choices": [{"message": {"content": "{}"}, "finish_reason": "length"}]})))
    with pytest.raises(RuntimeError, match="truncated"):
        ollama_client.chat("system", "user")


def test_api_stt_upload_poll_and_cache(api_env, monkeypatch, tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"RIFF-test")
    turns = [{"speaker": "SPEAKER_00", "text": "สวัสดีค่ะ", "start": 0.0, "end": 1.0}]
    post = Mock(side_effect=[response({"url": "https://storage.example/upload"}), response({"jobId": "job-1"})])
    put = Mock(return_value=response({}))
    get = Mock(return_value=response({"status": "succeeded", "output": {"turnLevelTranscription": turns}}))
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", put)
    monkeypatch.setattr(requests, "get", get)
    assert not hasattr(orchestrator, "_real_transcribe_diarized")
    result = orchestrator.transcribe_diarized(str(audio))
    assert result == [{"speaker": "Speaker 0", "text": "สวัสดีค่ะ", "start": 0.0, "end": 1.0}]
    assert post.call_args.kwargs["json"]["transcriptionConfig"]["model"] == "faster-whisper-large-v3-turbo"
    assert "Authorization" not in put.call_args.kwargs["headers"]
    assert orchestrator.transcribe_diarized(str(audio)) == result
    assert post.call_count == 2
    assert get.call_count == 1


def test_api_stt_failure_is_not_empty_success(api_env, monkeypatch, tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"test")
    monkeypatch.setattr(requests, "post", Mock(side_effect=[response({"url": "https://storage.example/upload"}), response({"jobId": "job-2"})]))
    monkeypatch.setattr(requests, "put", Mock(return_value=response({})))
    monkeypatch.setattr(requests, "get", Mock(return_value=response({"status": "failed", "output": {"error": "private transcript"}})))
    with pytest.raises(RuntimeError, match="failed") as error:
        orchestrator.transcribe_diarized(str(audio))
    assert "private transcript" not in str(error.value)


def test_readiness_in_api_mode_does_not_require_ollama(api_env, monkeypatch):
    monkeypatch.setattr(preflight, "MOCK_STT", False)
    monkeypatch.setattr(requests, "get", Mock(side_effect=AssertionError("readiness must not call network")))
    assert preflight.get_llm_readiness()[0]
    assert preflight.get_pyannote_access_readiness()[0]


def test_invalid_provider_rejected(monkeypatch):
    monkeypatch.setenv("STT_PROVIDER", "typo")
    with pytest.raises(ValueError, match="STT_PROVIDER"):
        config.api_settings()


def test_api_errors_do_not_become_neutral_sentiment(api_env, monkeypatch):
    monkeypatch.setattr(requests, "post", Mock(return_value=response({}, status=429)))
    with pytest.raises(ollama_client.APIError, match="429"):
        ollama_client.analyze_sentiment("Customer: ไม่พอใจค่ะ")


def test_invalid_json_does_not_become_successful_analysis(api_env, monkeypatch):
    monkeypatch.setattr(requests, "post", Mock(return_value=response({"choices": [{"message": {"content": "not JSON"}, "finish_reason": "stop"}]})))
    with pytest.raises(ollama_client.APIError):
        ollama_client.analyze_sentiment("Customer: สวัสดีค่ะ")


def test_api_keys_are_redacted():
    assert audit.redact({"TYPHOON_API_KEY": "secret", "PYANNOTE_API_KEY": "secret"}) == {
        "TYPHOON_API_KEY": "***", "PYANNOTE_API_KEY": "***",
    }


def test_audio_removal_also_removes_api_checkpoint(tmp_path):
    audio = tmp_path / "call.wav"
    cache = tmp_path / "call.wav.smartvoice-api.json"
    audio.write_bytes(b"audio")
    cache.write_text("{}")
    assert file_manager.remove_audio_file(str(audio))
    assert not audio.exists() and not cache.exists()


def test_poll_network_failure_resumes_saved_job(api_env, monkeypatch, tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"test")
    post = Mock(side_effect=[response({"url": "https://storage.example/upload"}), response({"jobId": "resume-1"})])
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", Mock(return_value=response({})))
    monkeypatch.setattr(requests, "get", Mock(side_effect=requests.Timeout("signed-secret-url")))
    with pytest.raises(RuntimeError, match="timed out") as error:
        orchestrator.transcribe_diarized(str(audio))
    assert "signed-secret-url" not in str(error.value)
    monkeypatch.setattr(requests, "get", Mock(return_value=response({"status": "succeeded", "output": {
        "turnLevelTranscription": [{"speaker": "SPEAKER_01", "text": "ที่นอนค่ะ", "start": 1, "end": 2}],
    }})))
    assert orchestrator.transcribe_diarized(str(audio))[0]["speaker"] == "Speaker 1"
    assert post.call_count == 2


def test_uncertain_submission_is_not_automatically_repeated(api_env, monkeypatch, tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"test")
    post = Mock(side_effect=[response({"url": "https://storage.example/upload"}), requests.Timeout()])
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "put", Mock(return_value=response({})))
    with pytest.raises(RuntimeError):
        orchestrator.transcribe_diarized(str(audio))
    with pytest.raises(RuntimeError, match="unknown status"):
        orchestrator.transcribe_diarized(str(audio))
    assert post.call_count == 2


@pytest.mark.parametrize("turn", [
    {"start": 2, "end": 1, "text": "คำ", "speaker": "SPEAKER_00"},
    {"start": float("nan"), "end": 1, "text": "คำ", "speaker": "SPEAKER_00"},
    {"start": 0, "end": 1, "text": "คำ", "speaker": None},
])
def test_api_invalid_timestamps_and_speakers_rejected(turn):
    with pytest.raises(RuntimeError, match="invalid transcript"):
        orchestrator._api_segments({"turnLevelTranscription": [turn]})


def test_cancellation_prevents_audio_upload(api_env, monkeypatch, tmp_path):
    audio = tmp_path / "call.wav"
    audio.write_bytes(b"test")
    post = Mock()
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(processing_control, "check", Mock(side_effect=processing_control.ProcessingCancelled()))
    with pytest.raises(processing_control.ProcessingCancelled):
        orchestrator.transcribe_diarized(str(audio))
    post.assert_not_called()


@pytest.mark.parametrize("legacy", [False, True])
def test_settings_saves_api_choices_without_exposing_keys(api_env, monkeypatch, tmp_path, legacy):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    values = {"STT_PROVIDER": "pyannote_api", "LLM_PROVIDER": "typhoon", "TYPHOON_MODEL": "typhoon-v2.1-12b-instruct"}
    if legacy:
        values.update(STT_PROVIDER="local", LLM_PROVIDER="ollama")
        monkeypatch.setenv("STT_PROVIDER", "local")
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setattr(env_settings, "read_env", lambda: values)
    save = Mock()
    monkeypatch.setattr(env_settings, "write_env", save)
    monkeypatch.setattr(preflight, "run_preflight_checks", lambda: [])
    app = AppTest.from_file(str(Path("pages/4_Settings.py").resolve()))
    user_id, error = auth.create_user("tester", "synthetic-password", "Admin", "Tester")
    assert user_id is not None and error is None
    app.session_state["current_user"] = "Tester"
    app.session_state["current_user_role"] = "Admin"
    app.session_state["current_username"] = "tester"
    app.session_state["current_user_id"] = user_id
    app.session_state["current_user_source"] = "db"
    app.run(timeout=20)
    assert not app.exception
    app.text_input(key="_api_secret_TYPHOON_API_KEY").set_value("new-secret")
    next(button for button in app.button if button.label == "บันทึกการตั้งค่า").click()
    app.run(timeout=20)
    assert not app.exception
    saved = save.call_args.args[0]
    assert saved["TYPHOON_API_KEY"] == "new-secret"
    assert saved["TYPHOON_MODEL"] == "typhoon-v2.1-12b-instruct"
    assert saved["STT_PROVIDER"] == "pyannote_api"
    assert saved["LLM_PROVIDER"] == "typhoon"
    assert not any(key.startswith(("WHISPER_", "OLLAMA_")) or key == "HF_TOKEN" for key in saved)
    assert not any(widget.label in {"Whisper model", "Backend", "Device", "Compute", "Ollama model", "HuggingFace token"} for kind in (app.selectbox, app.text_input) for widget in kind)
    assert "new-secret" not in " ".join(item.value for item in app.caption)
    assert not any("ไม่พบ GPU" in item.value for item in app.warning)


def test_unsupported_speech_model_rejected_before_upload(api_env, monkeypatch, tmp_path):
    monkeypatch.setenv("PYANNOTE_API_MODEL", "community-1")
    post = Mock()
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(ValueError, match="precision-2"):
        orchestrator.transcribe_diarized(str(tmp_path / "unused.wav"))
    post.assert_not_called()


def test_missing_speech_key_prevents_upload(api_env, monkeypatch, tmp_path):
    monkeypatch.delenv("PYANNOTE_API_KEY")
    post = Mock()
    monkeypatch.setattr(requests, "post", post)
    with pytest.raises(ValueError, match="PYANNOTE_API_KEY"):
        orchestrator.transcribe_diarized(str(tmp_path / "unused.wav"))
    post.assert_not_called()


@pytest.fixture
def synthetic_pipeline(api_env, monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "integration.db"))
    monkeypatch.setenv("PYANNOTE_API_MODEL", "precision-2")
    monkeypatch.setenv("STT_API_MODEL", "faster-whisper-large-v3-turbo")
    monkeypatch.setattr(file_manager, "AUDIO_DIR", str(tmp_path / "audio"))
    blocked = Mock(side_effect=AssertionError("Unexpected network call"))
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)
    monkeypatch.setattr(requests.sessions.Session, "request", blocked)
    processing_control.clear_run()
    db.init_db()
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 80000)
    payload = audio.getvalue()
    filename = file_manager.sanitize_filename("synthetic-call.wav")
    assert file_manager.validate_upload(payload, filename) == (True, "")
    digest = file_manager.compute_file_hash(payload)
    assert db.get_call_by_hash(digest) is None
    path = file_manager.save_audio_file(payload, filename, digest)
    call_id = db.insert_call(filename, digest, path)
    assert Path(path).read_bytes() == payload
    assert db.get_call_by_id(call_id)["status"] == "uploaded"
    assert db.get_done_calls() == []
    agent = "สวัสดีค่ะ คุณลูกค้าสอบถามข้อมูลสินค้าได้ค่ะ"
    customer = "อยากสอบถามวัสดุของที่นอนค่ะ"
    turns = [
        {"speaker": "SPEAKER_00", "text": agent, "start": 0.0, "end": 4.0},
        {"speaker": "SPEAKER_01", "text": customer, "start": 5.0, "end": 9.0},
    ]
    summary = "ลูกค้าสอบถามวัสดุของที่นอน"
    answers = {
        prompts.TRANSCRIPT_CLEANUP_SYSTEM: f"[0] Agent: {agent}\n[1] Customer: {customer}",
        prompts.SPEAKER_CORRECTION_SYSTEM: [{"idx": 0, "speaker": "Agent"}, {"idx": 1, "speaker": "Customer"}],
        prompts.EXTRACTION_SYSTEM: {"summary": summary, "topic": "สอบถามข้อมูลสินค้า", "keywords": ["วัสดุ", "ที่นอน"]},
        prompts.SENTIMENT_SYSTEM: {"sentiment": "neutral", "customer_quote": customer, "sentiment_reason": "สอบถามข้อมูล"},
        prompts.AGENT_QA_SYSTEM: {"found": [{"item": "P1", "quote": agent}], "customer_had_problem": False},
        prompts.NEXT_ACTION_SYSTEM: {"pending": False},
        prompts.ANOMALY_SYSTEM: {"anomaly_detected": False},
    }
    seen = []

    def post(url, **kwargs):
        if url == "https://api.pyannote.ai/v1/media/input":
            return response({"url": "https://storage.example/synthetic-upload"})
        if url == "https://api.pyannote.ai/v1/diarize":
            assert kwargs["json"]["transcription"] is True
            return response({"jobId": "synthetic-job"})
        assert url == "https://api.opentyphoon.ai/v1/chat/completions"
        messages = kwargs["json"]["messages"]
        system = messages[0]["content"]
        assert customer in messages[1]["content"]
        answer = answers[system]
        seen.append(system)
        content = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
        return response({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})

    def put(url, **kwargs):
        assert url == "https://storage.example/synthetic-upload"
        assert kwargs["data"].read() == payload
        return response({})

    def get(url, **kwargs):
        assert url == "https://api.pyannote.ai/v1/jobs/synthetic-job"
        return response({"status": "succeeded", "output": {"turnLevelTranscription": turns}})

    post_mock, put_mock, get_mock = Mock(side_effect=post), Mock(side_effect=put), Mock(side_effect=get)
    monkeypatch.setattr(requests, "post", post_mock)
    monkeypatch.setattr(requests, "put", put_mock)
    monkeypatch.setattr(requests, "get", get_mock)
    return SimpleNamespace(
        call_id=call_id, path=path, digest=digest, agent=agent, customer=customer,
        summary=summary, answers=answers, seen=seen, post_mock=post_mock,
        put_mock=put_mock, get_mock=get_mock, blocked=blocked,
    )


def test_synthetic_audio_to_dashboard_queries(synthetic_pipeline):
    call_id = synthetic_pipeline.call_id
    summary = synthetic_pipeline.summary
    customer = synthetic_pipeline.customer
    agent = synthetic_pipeline.agent
    digest = synthetic_pipeline.digest
    seen = synthetic_pipeline.seen
    answers = synthetic_pipeline.answers
    post_mock = synthetic_pipeline.post_mock
    put_mock = synthetic_pipeline.put_mock
    get_mock = synthetic_pipeline.get_mock
    blocked = synthetic_pipeline.blocked
    statuses = []
    result = pipeline.process_call(call_id, step_callback=lambda step: statuses.append(db.get_call_by_id(call_id)["status"]))
    saved = db.get_call_by_id(call_id)
    assert statuses[0] == "processing" and statuses[-1] == "done"
    assert saved["status"] == "done" and saved["error_msg"] is None
    assert saved["summary"] == result["summary"] == summary
    assert saved["topic"] == "สอบถามข้อมูลสินค้า"
    assert saved["sentiment"] == "neutral"
    assert saved["anomaly_detected"] == 0
    assert f"Customer: {customer}" in saved["transcript"]
    assert f"Agent: {agent}" in saved["transcript"]
    assert json.loads(saved["keywords"]) == ["วัสดุ", "ที่นอน"]
    performance = json.loads(saved["agent_performance"])
    assert performance["overall_score"] == performance["politeness"] + performance["problem_solving"]
    assert db.count_done_calls() == 1
    assert db.get_done_calls(limit=1000) == [saved]
    assert db.get_call_by_hash(digest)["id"] == call_id
    assert set(seen) == set(answers)
    assert put_mock.call_count == get_mock.call_count == 1
    assert post_mock.call_count == len(seen) + 2
    blocked.assert_not_called()


@pytest.mark.parametrize("failure", ["stt_timeout", "stt_http", "llm_timeout", "llm_http", "invalid_json", "truncated", "empty"])
def test_pipeline_api_failure_keeps_audio_and_hides_incomplete_results(synthetic_pipeline, failure):
    run = synthetic_pipeline
    attempts = []
    if failure.startswith("stt_"):
        def fail_poll(url, **kwargs):
            attempts.append(url)
            if failure == "stt_timeout":
                raise requests.Timeout("synthetic timeout")
            return response({}, status=503)
        run.get_mock.side_effect = fail_poll
    else:
        original_post = run.post_mock.side_effect

        def fail_analysis(url, **kwargs):
            if url == "https://api.opentyphoon.ai/v1/chat/completions" and kwargs["json"]["messages"][0]["content"] == prompts.ANOMALY_SYSTEM:
                attempts.append(url)
                if failure == "llm_timeout":
                    raise requests.Timeout("synthetic timeout")
                if failure == "llm_http":
                    return response({}, status=429)
                content = "not JSON" if failure == "invalid_json" else "{}" if failure == "truncated" else ""
                return response({"choices": [{"message": {"content": content}, "finish_reason": "length" if failure == "truncated" else "stop"}]})
            return original_post(url, **kwargs)
        run.post_mock.side_effect = fail_analysis
    with pytest.raises(RuntimeError):
        pipeline.process_call(run.call_id)
    saved = db.get_call_by_id(run.call_id)
    assert len(attempts) == 1
    assert saved["status"] == "error" and saved["error_msg"]
    assert saved["transcript"] is None and saved["summary"] is None
    assert saved["case_id"] is None
    assert db.get_done_calls() == [] and db.count_done_calls() == 0
    assert Path(run.path).is_file()
    assert file_manager.compute_file_hash(Path(run.path).read_bytes()) == run.digest
    checkpoint = json.loads(Path(run.path + ".smartvoice-api.json").read_text(encoding="utf-8"))
    assert checkpoint["job_id"] == "synthetic-job"
    assert ("output" in checkpoint) == (not failure.startswith("stt_"))
    if not failure.startswith("stt_"):
        assert prompts.EXTRACTION_SYSTEM in run.seen
        assert prompts.NEXT_ACTION_SYSTEM in run.seen
    run.blocked.assert_not_called()


def test_pipeline_result_write_failure_rolls_back_and_sets_error(synthetic_pipeline, monkeypatch):
    run = synthetic_pipeline
    original_save = db.update_call_results

    def fail_save(**kwargs):
        kwargs["sentiment"] = "invalid-synthetic-sentiment"
        original_save(**kwargs)

    assign = Mock(wraps=pipeline._auto_assign_case)
    monkeypatch.setattr(db, "update_call_results", fail_save)
    monkeypatch.setattr(pipeline, "_auto_assign_case", assign)
    with pytest.raises(sqlite3.IntegrityError):
        pipeline.process_call(run.call_id)
    saved = db.get_call_by_id(run.call_id)
    assert saved["status"] == "error" and "IntegrityError" in saved["error_msg"]
    assert saved["summary"] is None and saved["transcript"] is None
    assert db.get_done_calls() == []
    assert Path(run.path).is_file()
    assert "output" in json.loads(Path(run.path + ".smartvoice-api.json").read_text(encoding="utf-8"))
    assign.assert_not_called()
    run.blocked.assert_not_called()


def test_case_link_failure_preserves_analysis_and_rolls_back_new_case(synthetic_pipeline):
    run = synthetic_pipeline
    customer_id = db.insert_customer("Synthetic", "Customer")
    db.link_call_customer(run.call_id, customer_id)
    with db.get_connection() as conn:
        conn.execute("CREATE TRIGGER fail_case_link BEFORE UPDATE OF case_id ON calls BEGIN SELECT RAISE(ABORT, 'synthetic failure'); END")
    result = pipeline.process_call(run.call_id)
    saved = db.get_call_by_id(run.call_id)
    assert saved["status"] == "done" and saved["error_msg"] is None
    assert saved["summary"] == result["summary"] == run.summary
    assert saved["transcript"] and saved["case_id"] is None
    assert saved["case_link_status"] == "failed"
    assert saved["case_link_error"] == "write_failed"
    assert json.loads(saved["case_link_plan"]) == {"action": "create", "customer_id": customer_id}
    assert db.get_done_calls() == [saved]
    assert db.get_cases_by_customer(customer_id) == []
    assert db.get_call_customer_link(run.call_id)["customer_id"] == customer_id
    with db.get_connection() as conn:
        conn.execute("DROP TRIGGER fail_case_link")
    before = run.post_mock.call_count
    assert db.retry_case_link(run.call_id) == "linked"
    assert db.retry_case_link(run.call_id) == "linked"
    assert run.post_mock.call_count == before
    assert len(db.get_cases_by_customer(customer_id)) == 1
    run.blocked.assert_not_called()
