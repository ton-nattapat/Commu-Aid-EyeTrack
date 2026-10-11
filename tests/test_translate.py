"""Translator behaviour without the real NLLB model: Thai clean-up, the length cap and the timeout."""

import threading
import unicodedata

import pytest

from commu_aid import translate
from commu_aid.config import TranslationConfig
from commu_aid.translate import TranslationError, Translator, clean_thai


def test_model_spelling_of_sara_am_is_put_back():
    # What NLLB writes for these words: its tokenizer's NFKC splits ำ into ํา.
    for word in ["น้ำ", "ทำ", "กำลัง", "น้ำตา", "ขอน้ำหน่อยครับ"]:
        model_output = unicodedata.normalize("NFKC", word)
        assert model_output != word
        assert clean_thai(model_output) == word


def test_tone_mark_between_nikhahit_and_sara_aa_is_handled():
    assert clean_thai("นํ้า") == "น้ำ"


def test_runaway_repeat_is_cut_to_one_copy():
    assert clean_thai("ผมหิว น้ำ น้ำ น้ำ น้ำ น้ำ") == "ผมหิว น้ำ"
    assert clean_thai("ขอบคุณขอบคุณขอบคุณขอบคุณ") == "ขอบคุณ"


def test_normal_sentence_is_unchanged():
    assert clean_thai("ผมอยากดื่มน้ำครับ") == "ผมอยากดื่มน้ำครับ"
    assert clean_thai("นานา") == "นานา"  # said twice is still a word, not a loop


class FakeIds:
    def __init__(self, n):
        self.shape = (1, n)


class FakeTokenizer:
    def __call__(self, text, return_tensors):
        return {"input_ids": FakeIds(len(text.split()))}

    def convert_tokens_to_ids(self, code):
        return 7

    def batch_decode(self, tokens, skip_special_tokens):
        return [tokens]


class FakeModel:
    def __init__(self, output, delay=0.0, clock=None):
        self.output, self.delay, self.clock = output, delay, clock
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs
        if self.clock is not None:
            self.clock.t += self.delay
        return self.output


class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def make_translator(model, timeout_s=8.0):
    t = Translator(TranslationConfig(timeout_s=timeout_s))
    t._tokenizer, t._model = FakeTokenizer(), model
    return t


def test_translate_caps_length_and_time_and_cleans_output():
    model = FakeModel(unicodedata.normalize("NFKC", "ขอน้ำ"))
    t = make_translator(model)
    assert t.translate("water please") == "ขอน้ำ"
    assert model.kwargs["max_new_tokens"] == 3 * 2 + 10
    assert model.kwargs["max_time"] == 8.0
    assert model.kwargs["no_repeat_ngram_size"] == 4
    assert model.kwargs["forced_bos_token_id"] == 7


def test_translation_that_runs_out_of_time_fails(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(translate.time, "monotonic", clock)
    t = make_translator(FakeModel("น้ำน้ำ", delay=9.0, clock=clock))
    with pytest.raises(TranslationError, match="longer than 8 s"):
        t.translate("water")
    assert not t._lock.locked()


def test_busy_translator_fails_instead_of_waiting_forever():
    t = make_translator(FakeModel("น้ำ"), timeout_s=0.5)
    t._lock.acquire()  # an earlier translation still stuck
    try:
        with pytest.raises(TranslationError, match="busy"):
            t.translate("water")
    finally:
        t._lock.release()


def test_empty_output_fails():
    with pytest.raises(TranslationError, match="empty"):
        make_translator(FakeModel("   ")).translate("hmm")
