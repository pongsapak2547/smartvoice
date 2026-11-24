"""Call text must not reach the application log or exception messages.

Logs leave the database's access controls (a cloud log service, a support
ticket), so they may carry sizes and ids, never what the customer said.
"""

import logging
from unittest.mock import patch

import pytest

from smartvoice import audit, ollama_client, pipeline

# Stands in for something a customer said on the call.
SPOKEN = "ลูกค้าชื่อสมชาย เบอร์ 0812345678"


class _Collect(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.DEBUG)
        self.messages: list[str] = []

    def emit(self, record):
        self.messages.append(record.getMessage())
        if record.exc_text:
            self.messages.append(record.exc_text)


@pytest.fixture
def app_log():
    # The "smartvoice" logger does not propagate, so pytest's caplog misses it.
    handler = _Collect()
    logger = logging.getLogger("smartvoice")
    logger.addHandler(handler)
    yield handler
    logger.removeHandler(handler)


def _logged(handler: _Collect) -> str:
    return "\n".join(handler.messages)


CONVERSATION = [{"speaker": "Speaker 1", "text": SPOKEN}]


@pytest.mark.parametrize("answer", [
    f"ขออภัย {SPOKEN}",               # no JSON array at all
    f'["{SPOKEN}", "{SPOKEN}"]',       # array of strings instead of objects
])
def test_correct_speakers_logs_no_call_text(app_log, answer):
    with patch.object(ollama_client, "chat", return_value=answer):
        result = ollama_client.correct_speakers(CONVERSATION)

    assert result == CONVERSATION
    assert app_log.messages, "the skip should still be logged"
    assert "0812345678" not in _logged(app_log)
    assert "สมชาย" not in _logged(app_log)


@pytest.mark.parametrize("evidence", [
    f"<{SPOKEN}>",                    # template leakage
    f"ร้านที่นอนพลอย {SPOKEN}",       # prompt-example token not in the call
])
def test_sanitize_evidence_logs_no_quote(app_log, evidence):
    assert ollama_client.sanitize_evidence(evidence, "บทสนทนาอื่น") == ollama_client._EVIDENCE_FALLBACK
    assert app_log.messages
    assert "0812345678" not in _logged(app_log)


def test_extract_json_error_has_no_excerpt():
    with pytest.raises(ValueError) as caught:
        ollama_client.extract_json(f"ไม่มี JSON {SPOKEN}")

    assert "0812345678" not in str(caught.value)
    assert "chars" in str(caught.value)


def test_pipeline_failure_logs_no_exception_payload(app_log):
    with patch.object(pipeline.db, "get_call_by_id", return_value={"status": "processing", "file_path": "synthetic.wav"}), \
         patch.object(pipeline.db, "update_processing_step"), \
         patch.object(pipeline.db, "update_call_status"), \
         patch.object(pipeline, "_transcribe_diarized", side_effect=OSError(SPOKEN)):
        with pytest.raises(OSError):
            pipeline.process_call(999)
    assert "0812345678" not in _logged(app_log)
    assert "OSError" in _logged(app_log)


def test_case_assignment_failure_logs_no_exception_payload(app_log):
    with patch.object(pipeline.db, "get_call_customer_link", side_effect=ValueError(SPOKEN)):
        pipeline._auto_assign_case(999, {})
    assert "0812345678" not in _logged(app_log)


def test_database_and_bootstrap_credentials_are_redacted():
    values = audit.redact({"DATABASE_URL": "postgresql://user:secret@host/db", "SMARTVOICE_BOOTSTRAP_PASSWORD": "synthetic-secret"})
    assert all(value == "***" for value in values.values())
