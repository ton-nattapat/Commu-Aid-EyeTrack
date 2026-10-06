"""English to Thai translation for typed messages, offline with Meta's NLLB-200.

The model (about 2.5 GB) downloads from Hugging Face on first use and is cached after that.
Needs tiles never come through here: each tile stores its own checked Thai phrase.
"""

from __future__ import annotations

import logging
import threading

from .config import TranslationConfig

log = logging.getLogger(__name__)


class TranslationError(RuntimeError):
    pass


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
            if self._model is not None:
                return
            try:
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            except ImportError as exc:
                raise TranslationError("Translation needs: pip install -r requirements-translate.txt") from exc
            self._tokenizer = AutoTokenizer.from_pretrained(self.cfg.model, src_lang=self.cfg.source_code)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.cfg.model)

    def translate(self, text: str) -> str:
        """Blocking; call from a worker thread. Raises TranslationError on any failure."""
        if not self.enabled:
            raise TranslationError("Translation is switched off")
        try:
            self._load()
            with self._lock:
                inputs = self._tokenizer(text, return_tensors="pt")
                target_id = self._tokenizer.convert_tokens_to_ids(self.cfg.target_code)
                tokens = self._model.generate(**inputs, forced_bos_token_id=target_id, max_new_tokens=128)
                return self._tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]
        except TranslationError:
            raise
        except Exception as exc:
            raise TranslationError(str(exc)) from exc
