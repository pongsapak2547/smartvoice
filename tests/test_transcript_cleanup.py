import re
from unittest.mock import Mock, patch

import pytest

from smartvoice import ollama_client


@pytest.mark.parametrize(("source", "replacement"), [
    ("Please cancel my order today", "Please"),
    ("Please deliver it", "Please deliver"),
    ("Please send it tomorrow", "Please send tomorrow"),
    ("ไม่ยกเลิกการจัดส่ง", "ยกเลิกการจัดส่ง"),
    ("ส่งวันที่ 20", "ส่งวันที่ 21"),
    ("เดิม", "ใหม่"),
])
def test_unverified_short_edit_keeps_both_speakers_and_warns(monkeypatch, source, replacement):
    turns = [{"speaker": "Agent", "text": "สวัดดีค่ะ", "start": 1, "end": 2},
             {"speaker": "Customer", "text": source, "start": 2, "end": 3}]
    monkeypatch.setattr(ollama_client, "chat", Mock(return_value=f"[0] Agent: สวัสดีค่ะ\n[1] Customer: {replacement}"))
    with patch.object(ollama_client.log, "warning") as warning:
        result = ollama_client.cleanup_transcript(turns, call_id=42, cleanup_pass=2)
    assert result == turns
    fmt, *args = warning.call_args.args
    message = fmt % tuple(args)
    assert all(field in message for field in ("call_id=42", "cleanup_pass=2", "chunk_index=1"))
    assert source not in message and replacement not in message


def test_short_typo_and_verified_noise(monkeypatch):
    turns = [{"speaker": "Agent", "text": "สวัดดีค่ะ"},
             {"speaker": "Customer", "text": "[เสียงรบกวน] รับแล้ว"},
             {"speaker": "Agent", "text": "[noise]"}]
    monkeypatch.setattr(ollama_client, "chat", Mock(return_value="[0] Agent: สวัสดีค่ะ\n[1] Customer: รับแล้ว\n[2] Agent: <REMOVE>"))
    result = ollama_client.cleanup_transcript(turns)
    assert [turn["text"] for turn in result] == ["สวัสดีค่ะ", "รับแล้ว", ""]


def test_short_cleanup_preserves_metadata_and_empty_turn(monkeypatch):
    turns = [{"speaker": "Agent", "text": "สวัดดี", "start": 0, "end": 3}, {"text": ""}]
    chat = Mock(return_value="[0] Agent: สวัสดี")
    monkeypatch.setattr(ollama_client, "chat", chat)
    assert ollama_client.cleanup_transcript(turns) == [{**turns[0], "text": "สวัสดี"}, turns[1]]
    assert turns[0]["text"] == "สวัดดี"
    chat.assert_called_once()


@pytest.mark.parametrize("output", [
    "unparseable", "[0] Agent: edit", "[0] Agent: edit\n[0] Agent: edit",
    "[0] Agent: edit\n[2] Customer: extra", "[0] Customer: edit\n[1] Customer: ok",
    "[0] Agent: edit\n[1] Customer: ", "[0] Agent: <REMOVE>\n[1] Customer: ok",
])
def test_invalid_cleanup_keeps_entire_chunk(monkeypatch, output):
    turns = [{"speaker": "Agent", "text": "first"}, {"speaker": "Customer", "text": "second"}]
    monkeypatch.setattr(ollama_client, "chat", Mock(return_value=output))
    assert ollama_client.cleanup_transcript(turns) == turns


def test_long_cleanup_merges_global_indices_and_split_turns(monkeypatch):
    monkeypatch.setenv("TYPHOON_CLEANUP_CHUNK_CHARS", "128")
    turns = [{"speaker": ["Customer", "Agent"][i % 2], "start": i, "end": i + 1,
              "text": f"{i} before " + "ทดสอบ " * (80 if i == 4 else 4) + "before"} for i in range(20)]
    requests = []

    def edit(system, user):
        rows = re.findall(r"^\[\d+\] [^\n]+", user, re.M)
        body = "\n".join(rows)
        assert 0 < len(body) <= 128
        requests.append(body)
        return body.replace("before", "Before")

    monkeypatch.setattr(ollama_client, "chat", edit)
    assert ollama_client.cleanup_transcript(turns) == [
        {**turn, "text": turn["text"].replace("before", "Before")} for turn in turns
    ]
    assert len(requests) > 1


def test_truncated_chunk_kept_once_other_chunk_cleaned(monkeypatch):
    monkeypatch.setenv("TYPHOON_CLEANUP_CHUNK_CHARS", "128")
    turns = [{"speaker": "Agent", "text": "a" * 90}, {"speaker": "Customer", "text": "b" * 90}]
    responses = [
        {"choices": [{"finish_reason": reason, "message": {"content": content}}]}
        for reason, content in [("length", "[0] Agent: partial"), ("stop", "[1] Customer: " + "b" * 89 + "c")]
    ]
    post = Mock(side_effect=[Mock(status_code=200, json=Mock(return_value=r)) for r in responses])
    monkeypatch.setattr(ollama_client.requests, "post", post)
    with patch.object(ollama_client.log, "warning") as warning:
        assert ollama_client.cleanup_transcript(turns, call_id=42, cleanup_pass=1) == [
            turns[0], {**turns[1], "text": "b" * 89 + "c"}
        ]
    assert warning.call_args.args[1:] == (42, 1, 1)
    assert post.call_count == 2


def test_structurally_complete_but_abbreviated_long_turn_keeps_source(monkeypatch):
    turns = [{"speaker": "Customer", "text": "ติดตามการจัดส่ง " * 20}]
    monkeypatch.setattr(ollama_client, "chat", Mock(return_value="[0] Customer: ติดตามการจัดส่ง"))
    assert ollama_client.cleanup_transcript(turns) == turns


def test_unbroken_oversized_text_and_line_breaks_preserved(monkeypatch):
    monkeypatch.setenv("TYPHOON_CLEANUP_CHUNK_CHARS", "40")
    long_word = "ทดสอบ" * 60
    text = "  firsst\r\n" + long_word + "\t lasst  "
    chat = Mock(side_effect=["[0] Agent: first", "[0] Agent: last"])
    monkeypatch.setattr(ollama_client, "chat", chat)
    with patch.object(ollama_client.log, "warning") as warning:
        assert ollama_client.cleanup_transcript([{"speaker": "Agent", "text": text}], call_id=42, cleanup_pass=2) == [
            {"speaker": "Agent", "text": text.replace("firsst", "first").replace("lasst", "last")}
        ]
    assert warning.call_args.args[1:] == (42, 2, 2)
    assert chat.call_count == 2


@pytest.mark.parametrize("limit", [4096, 8192])
def test_cleanup_request_token_limit_and_numeric_usage(monkeypatch, limit):
    monkeypatch.setenv("TYPHOON_MAX_TOKENS", str(limit))
    payload = {"choices": [{"message": {"content": "[0] Agent: synthetic"}, "finish_reason": "stop"}],
               "usage": {"prompt_tokens": 420, "completion_tokens": 8}}
    post = Mock(return_value=Mock(status_code=200, json=Mock(return_value=payload)))
    monkeypatch.setattr(ollama_client.requests, "post", post)
    info = Mock()
    monkeypatch.setattr(ollama_client.log, "info", info)
    ollama_client.cleanup_transcript([{"speaker": "Agent", "text": "synthetic"}])
    assert post.call_args.kwargs["json"]["max_tokens"] == limit
    assert info.call_args.args[1:] == (420, 8, limit)
