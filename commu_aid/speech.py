"""Text-to-speech, offline.

macOS uses the built-in `say` command (Thai voice: Kanya); other systems use pyttsx3 with
whatever voices the operating system has installed. Speech runs on a worker thread, and a new
message interrupts one still being spoken.
"""

from __future__ import annotations

import logging
import platform
import queue
import shutil
import subprocess
import threading
from typing import Optional

from .config import SpeechConfig

log = logging.getLogger(__name__)


class Speaker:
    def __init__(self, cfg: SpeechConfig):
        self.cfg = cfg
        self.engine = self._pick_engine(cfg.engine)
        self._queue: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._proc: Optional[subprocess.Popen] = None
        self._thread = threading.Thread(target=self._run, name="speech", daemon=True)
        self._thread.start()

    @staticmethod
    def _pick_engine(name: str) -> str:
        if name == "auto":
            if platform.system() == "Darwin" and shutil.which("say"):
                return "say"
            return "pyttsx3"
        return name

    def speak(self, text: str, lang: str) -> None:
        text = text.strip()
        if not text or self.engine == "none":
            return
        self._interrupt()
        self._queue.put((text, lang))

    def close(self) -> None:
        self._interrupt()
        self._queue.put(None)

    def _voice_for(self, lang: str) -> str:
        return self.cfg.voice_th if lang == "th" else self.cfg.voice_en

    def _interrupt(self) -> None:
        # Drop anything not yet spoken, and stop what is speaking now.
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def _run(self) -> None:
        tts = None
        while True:
            item = self._queue.get()
            if item is None:
                return
            text, lang = item
            try:
                if self.engine == "say":
                    cmd = ["say", "-r", str(self.cfg.rate)]
                    voice = self._voice_for(lang)
                    if voice:
                        cmd += ["-v", voice]
                    self._proc = subprocess.Popen(cmd + [text])
                    self._proc.wait()
                elif self.engine == "pyttsx3":
                    if tts is None:
                        import pyttsx3

                        tts = pyttsx3.init()
                        tts.setProperty("rate", self.cfg.rate)
                    voice_id = _find_pyttsx3_voice(tts, self._voice_for(lang), lang)
                    if voice_id:
                        tts.setProperty("voice", voice_id)
                    tts.say(text)
                    tts.runAndWait()
            except Exception:
                log.exception("Speech failed for %r", text)


def _find_pyttsx3_voice(tts, name: str, lang: str) -> Optional[str]:
    voices = tts.getProperty("voices") or []
    for v in voices:
        if name and name.lower() in f"{v.name} {v.id}".lower():
            return v.id
    for v in voices:
        langs = " ".join(str(x) for x in (getattr(v, "languages", None) or [])).lower()
        if lang in langs or lang in str(v.id).lower():
            return v.id
    return None
