"""English to Thai translation for typed messages, offline with Meta's NLLB-200.

The model (about 2.5 GB) downloads from Hugging Face on first use and is cached after that.
Needs tiles never come through here: each tile stores its own checked Thai phrase.
"""

from __future__ import annotations

import logging
import re
import threading
import time

from .config import TranslationConfig

log = logging.getLogger(__name__)

# NLLB's tokenizer NFKC-normalises its text, which splits SARA AM (ำ) into NIKHAHIT + SARA AA (ํา).
# The model therefore writes every ำ that way, "น้ำ" comes out as "น้ํา", and the macOS Thai voice
# misreads it. Put the single character back, with any tone mark that landed between the two.
_SPLIT_SARA_AM = re.compile("ํ([่-๋]?)า")
# A piece of two or more characters said three or more times in a row: the model got stuck repeating.
_RUNAWAY_REPEAT = re.compile(r"(\S.+?)(?:\s*\1){2,}")


class TranslationError(RuntimeError):
    pass


def clean_thai(text: str) -> str:
    """Fix the model's spelling of ำ and cut a runaway repeat down to one copy."""
    text = _SPLIT_SARA_AM.sub(lambda m: m.group(1) + "ำ", text)
    text = _RUNAWAY_REPEAT.sub(r"\1", text)
    return " ".join(text.split())


class Translator:
    def __init__(self, cfg: TranslationConfig):
        self.cfg = cfg
        self._lock = threading.Lock()
        self._model = None
        self._tokenizer = None

    @property
    def enabled(self) -> bool:
        return self.cfg.engine == "nllb"

    def preload(self) -> None:
        """Load the model in the background at start-up so the first Speak is not slow."""
        if self.enabled:
            threading.Thread(target=self._safe_load, name="translator-load", daemon=True).start()

    def _safe_load(self) -> None:
        try:
            self._load()
        except Exception:
            log.exception("Could not load translation model")

    def _load(self) -> None:
        with self._lock:
            self._load_locked()

    def _load_locked(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        except ImportError as exc:
            raise TranslationError("Translation needs: pip install -r requirements-translate.txt") from exc
        self._tokenizer = AutoTokenizer.from_pretrained(self.cfg.model, src_lang=self.cfg.source_code)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.cfg.model)

    def translate(self, text: str) -> str:
        """Blocking; call from a worker thread. Raises TranslationError on any failure.

        Gives up after cfg.timeout_s, so a sentence the model gets stuck on fails quickly and the
        caller can speak the English instead of waiting.
        """
        if not self.enabled:
            raise TranslationError("Translation is switched off")
        timeout = max(0.5, float(self.cfg.timeout_s))
        try:
            if not self._lock.acquire(timeout=timeout):
                raise TranslationError("Translator is still loading or busy with an earlier message")
            try:
                self._load_locked()
                inputs = self._tokenizer(text, return_tensors="pt")
                target_id = self._tokenizer.convert_tokens_to_ids(self.cfg.target_code)
                # Thai needs a few more tokens than the English; anything far longer is a loop.
                limit = min(128, 3 * int(inputs["input_ids"].shape[-1]) + 10)
                start = time.monotonic()
                tokens = self._model.generate(
                    **inputs,
                    forced_bos_token_id=target_id,
                    max_new_tokens=limit,
                    no_repeat_ngram_size=4,
                    max_time=timeout,
                )
                if time.monotonic() - start >= timeout:
                    raise TranslationError(f"Translation took longer than {timeout:g} s")
                thai = clean_thai(self._tokenizer.batch_decode(tokens, skip_special_tokens=True)[0])
            finally:
                self._lock.release()
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(str(exc)) from exc
        if not thai:
            raise TranslationError("Translation came back empty")
        return thai
