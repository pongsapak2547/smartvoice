import unittest


class TestAudioHelpers(unittest.TestCase):
    def test_has_thai_positive(self):
        from smartvoice.stt.audio import has_thai
        self.assertTrue(has_thai("สวัสดีครับ"))
        self.assertTrue(has_thai("สวัสดี hello"))

    def test_has_thai_negative(self):
        from smartvoice.stt.audio import has_thai
        self.assertFalse(has_thai("hello world"))
        self.assertFalse(has_thai(""))
        self.assertFalse(has_thai("   "))

    def test_has_thai_ratio_threshold(self):
        from smartvoice.stt.audio import has_thai
        # Very low Thai ratio — should fail default threshold
        self.assertFalse(has_thai("a" * 100 + "ก"))


class TestDiarizeGrouping(unittest.TestCase):
    def test_group_words_by_pause_basic(self):
        from smartvoice.stt.diarize import group_words_by_pause
        words = [
            {"word": "สวัสดี", "start": 0.0, "end": 0.5},
            {"word": "ครับ", "start": 0.5, "end": 0.8},
            # pause > 1.0s
            {"word": "ขอบคุณ", "start": 2.0, "end": 2.5},
            {"word": "ค่ะ", "start": 2.5, "end": 2.8},
        ]
        result = group_words_by_pause(words, "Speaker 0")
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["speaker"], "Speaker 0")
        self.assertIn("สวัสดี", result[0]["text"])
        self.assertIn("ขอบคุณ", result[1]["text"])

    def test_group_words_empty(self):
        from smartvoice.stt.diarize import group_words_by_pause
        self.assertEqual(group_words_by_pause([], "Speaker 0"), [])
