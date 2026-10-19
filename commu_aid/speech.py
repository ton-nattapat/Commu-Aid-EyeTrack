"""Text-to-speech, offline.

macOS uses the built-in `say` command (Thai voice: Kanya). Windows uses its own speech voices
through SAPI (Thai voice: Microsoft Pattara, added with the Thai speech pack in Settings > Time &
language > Speech). Other systems use pyttsx3 with whatever voices are installed. Speech runs on a
worker thread, and a new message interrupts one still being spoken.

Siri voices cannot be named to `say`; the voice "system" leaves the name out, so `say` speaks
with the Mac's System Voice, which can be a Siri voice. On Windows "system" means the first
installed voice for the language, and so does a saved voice that is not installed (e.g. Kanya).
"""

from __future__ import annotations

import logging
import math
import platform
import queue
import re
import shutil
import subprocess
import threading
from typing import List, Optional, Sequence, Tuple

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
            if platform.system() == "Windows" and _has_sapi():
                return "sapi"
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
        if self.engine == "sapi":
            try:
                return [name for name, langs in sapi_voices() if lang in langs]
            except Exception:
                log.exception("Could not list voices")
                return []
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
        sapi = None
        while True:
            item = self._queue.get()
            if item is None:
                if sapi is not None:
                    sapi.stop()
                return
            text, lang, voice, rate = item
            try:
                if self.engine == "sapi":
                    if sapi is None:
                        sapi = _SapiVoice()
                    sapi.speak(text, lang, voice, rate)  # returns at once; the next message cuts it off
                elif self.engine == "say":
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


# Windows speech (SAPI). Voices added in Settings > Time & language > Speech, such as the Thai
# Microsoft Pattara, are "OneCore" voices that SAPI only lists when asked for that category.
SAPI_CATEGORIES = (
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech_OneCore\Voices",
    r"HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Speech\Voices",
)
SAPI_ASYNC = 1  # SVSFlagsAsync
SAPI_PURGE = 2  # SVSFPurgeBeforeSpeak: stop what is being spoken
SAPI_NORMAL_WPM = 180  # about how fast SAPI speaks at rate 0
# Windows language ids (the low 10 bits of an LCID) for the languages the app speaks.
WINDOWS_LANGUAGE_IDS = {0x1E: "th", 0x09: "en"}


def _has_sapi() -> bool:
    try:
        import win32com.client  # noqa: F401  (pywin32)
    except ImportError:
        return False
    return True


def sapi_languages(attribute: str) -> List[str]:
    """Languages in a SAPI voice's Language attribute: hex LCIDs such as "41E" or "409;9"."""
    langs = []
    for part in attribute.split(";"):
        try:
            lang = WINDOWS_LANGUAGE_IDS.get(int(part.strip(), 16) & 0x3FF)
        except ValueError:
            continue
        if lang and lang not in langs:
            langs.append(lang)
    return langs


def sapi_rate(wpm: int) -> int:
    """Words per minute to SAPI's rate, -10 (a third as fast) to 10 (three times as fast)."""
    return max(-10, min(10, round(10 * math.log(wpm / SAPI_NORMAL_WPM) / math.log(3))))


def pick_voice(voices: Sequence[Tuple[str, List[str]]], name: str, lang: str) -> Optional[int]:
    """Index of the voice whose name contains `name`, else the first voice for the language."""
    if name:
        for i, (voice_name, _) in enumerate(voices):
            if name.lower() in voice_name.lower():
                return i
    for i, (_, langs) in enumerate(voices):
        if lang in langs:
            return i
    return None


def _sapi_tokens():
    """(name, languages, token) for every installed SAPI voice, OneCore voices first."""
    import win32com.client

    found, names = [], set()
    for category_id in SAPI_CATEGORIES:
        try:
            category = win32com.client.Dispatch("SAPI.SpObjectTokenCategory")
            category.SetId(category_id, False)
            tokens = category.EnumerateTokens()
        except Exception:
            log.debug("No SAPI voices in %s", category_id)
            continue
        for i in range(tokens.Count):
            token = tokens.Item(i)
            try:
                name = token.GetAttribute("Name")
                langs = sapi_languages(token.GetAttribute("Language"))
            except Exception:
                continue
            if name not in names:
                names.add(name)
                found.append((name, langs, token))
    return found


def sapi_voices() -> List[Tuple[str, List[str]]]:
    _com_init()
    return [(name, langs) for name, langs, _ in _sapi_tokens()]


def _com_init() -> None:
    import pythoncom

    try:
        pythoncom.CoInitialize()
    except pythoncom.com_error:
        pass  # this thread already uses COM in another mode, which is fine for SAPI


class _SapiVoice:
    """One SAPI voice, used only from the speech thread."""

    def __init__(self):
        import win32com.client

        _com_init()
        self._voice = win32com.client.Dispatch("SAPI.SpVoice")
        self._tokens = _sapi_tokens()
        log.info("Windows voices: %s", ", ".join(f"{n} ({'/'.join(l) or '?'})" for n, l, _ in self._tokens))

    def speak(self, text: str, lang: str, name: str, rate: int) -> None:
        self.stop()
        i = pick_voice([(n, l) for n, l, _ in self._tokens], name, lang)
        if i is None:
            log.warning("No Windows voice for %r is installed; using the default voice", lang)
        else:
            self._voice.Voice = self._tokens[i][2]
        self._voice.Rate = sapi_rate(rate)
        self._voice.Speak(text, SAPI_ASYNC | SAPI_PURGE)

    def stop(self) -> None:
        self._voice.Speak("", SAPI_ASYNC | SAPI_PURGE)
