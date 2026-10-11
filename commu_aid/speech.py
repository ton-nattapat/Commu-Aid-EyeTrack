"""Text-to-speech, offline.

macOS uses the built-in `say` command (Thai voice: Kanya); other systems use pyttsx3 with
whatever voices the operating system has installed. Speech runs on a worker thread, and a new
message interrupts one still being spoken.

Siri voices cannot be named to `say`; the voice "system" leaves the name out, so `say` speaks
with the Mac's System Voice, which can be a Siri voice.
"""

from __future__ import annotations

import logging
import platform
import queue
import re
import shutil
import subprocess
import threading
from typing import List, Optional

from .config import SYSTEM_VOICE, SpeechConfig

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
        # Voice and rate are read now, so a Settings change applies to the next message.
        self._queue.put((text, lang, self._voice_for(lang), self.cfg.rate))

    def preview(self, text: str, lang: str, voice: str, rate: int) -> None:
        """Speak with a voice and rate not saved yet (the Settings page's Try button)."""
        if self.engine == "none":
            return
        self._interrupt()
        self._queue.put((text, lang, "" if voice == SYSTEM_VOICE else voice, rate))

    def voices(self, lang: str) -> List[str]:
        """Names of the installed voices for a language, for the Settings page."""
        if self.engine != "say":
            return []
        try:
            out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=5).stdout
        except (OSError, subprocess.SubprocessError):
            log.exception("Could not list voices")
            return []
        return parse_say_voices(out, lang)

    def close(self) -> None:
        self._interrupt()
        self._queue.put(None)

    def _voice_for(self, lang: str) -> str:
        voice = self.cfg.voice_th if lang == "th" else self.cfg.voice_en
        return "" if voice == SYSTEM_VOICE else voice

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
            text, lang, voice, rate = item
            try:
                if self.engine == "say":
                    cmd = ["say", "-r", str(rate)]
                    if voice:
                        cmd += ["-v", voice]
                    self._proc = subprocess.Popen(cmd + [text])
                    self._proc.wait()
                elif self.engine == "pyttsx3":
                    if tts is None:
                        import pyttsx3

                        tts = pyttsx3.init()
                    tts.setProperty("rate", rate)
                    voice_id = _find_pyttsx3_voice(tts, voice, lang)
                    if voice_id:
                        tts.setProperty("voice", voice_id)
                    tts.say(text)
                    tts.runAndWait()
            except Exception:
                log.exception("Speech failed for %r", text)


# One line of `say -v ?`: name (may hold spaces and brackets), locale, then "# sample text".
_SAY_VOICE_LINE = re.compile(r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2,3}[_-][A-Za-z0-9_-]+)\s+#")


def parse_say_voices(listing: str, lang: str) -> List[str]:
    names = []
    for line in listing.splitlines():
        m = _SAY_VOICE_LINE.match(line)
        if m and m.group("locale").split("_")[0].split("-")[0] == lang and m.group("name") not in names:
            names.append(m.group("name"))
    return names


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
