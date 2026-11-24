"""Speaker diarization using Pyannote + word-level speaker assignment."""

from smartvoice.stt.audio import has_thai

_PAUSE_SPLIT_SEC = 0.8
_LONG_SEGMENT_SEC = 18.0
_LONG_SEGMENT_PAUSE_SPLIT_SEC = 0.35


def _normalize_speaker_label(speaker: str) -> str:
    if speaker.startswith("SPEAKER_"):
        num = speaker.replace("SPEAKER_", "").lstrip("0") or "0"
        return f"Speaker {num}"
    return speaker


def _pick_speaker_for_word(start: float, end: float, diar_turns: list[tuple[float, float, str]]) -> str:
    if not diar_turns:
        return "Speaker 0"

    best_spk = "Speaker 0"
    best_overlap = 0.0
    closest_spk = "Speaker 0"
    closest_distance = float("inf")
    word_mid = (start + end) / 2.0

    for d_start, d_end, spk in diar_turns:
        overlap = max(0.0, min(end, d_end) - max(start, d_start))
        if overlap > best_overlap:
            best_overlap = overlap
            best_spk = spk

        diar_mid = (d_start + d_end) / 2.0
        distance = abs(word_mid - diar_mid)
        if distance < closest_distance:
            closest_distance = distance
            closest_spk = spk

    chosen = best_spk if best_overlap > 0 else closest_spk
    return _normalize_speaker_label(chosen)


def _group_words_by_speaker_and_pause(words: list[dict]) -> list[dict]:
    if not words:
        return []

    output: list[dict] = []
    cur_spk = words[0].get("speaker", "Speaker 0")
    cur_words: list[str] = []
    cur_start = float(words[0].get("start", 0) or 0)
    cur_end = float(words[0].get("end", cur_start) or cur_start)

    for w in words:
        word = w.get("word", "")
        if not word:
            continue

        speaker = w.get("speaker", "Speaker 0")
        start = float(w.get("start", 0) or 0)
        end = float(w.get("end", start) or start)
        gap = start - cur_end
        seg_duration = cur_end - cur_start
        split_due_to_pause = gap > _PAUSE_SPLIT_SEC
        split_due_to_long_segment = seg_duration >= _LONG_SEGMENT_SEC and gap > _LONG_SEGMENT_PAUSE_SPLIT_SEC

        if cur_words and (speaker != cur_spk or split_due_to_pause or split_due_to_long_segment):
            text = "".join(cur_words).strip()
            if text and has_thai(text):
                output.append({"speaker": cur_spk, "text": text, "start": cur_start, "end": cur_end})
            cur_spk = speaker
            cur_words = [word]
            cur_start = start
            cur_end = end
            continue

        if not cur_words:
            cur_spk = speaker
            cur_start = start
        cur_words.append(word)
        cur_end = end

    if cur_words:
        text = "".join(cur_words).strip()
        if text and has_thai(text):
            output.append({"speaker": cur_spk, "text": text, "start": cur_start, "end": cur_end})
    return output


def group_words_by_pause(words: list[dict], speaker: str,
                         pause_threshold: float = 1.0) -> list[dict]:
    """Group words into segments separated by pauses (for non-diarized output)."""
    if not words:
        return []
    output: list[dict] = []
    cur = [words[0]]
    for w in words[1:]:
        if w["start"] - cur[-1]["end"] > pause_threshold:
            text = "".join(x["word"] for x in cur).strip()
            if text and has_thai(text):
                output.append({"speaker": speaker, "text": text,
                               "start": cur[0]["start"], "end": cur[-1]["end"]})
            cur = [w]
        else:
            cur.append(w)
    if cur:
        text = "".join(x["word"] for x in cur).strip()
        if text and has_thai(text):
            output.append({"speaker": speaker, "text": text,
                           "start": cur[0]["start"], "end": cur[-1]["end"]})
    return output
