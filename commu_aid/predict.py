"""Offline word prediction for the keyboard.

While the patient types a word, the predictor offers the most likely ways to finish it. Between
words it offers the words that usually come next. It knows 10,000 common English words plus a
short list of care words, and it learns from every message the patient speaks: words he uses
are offered first, and so are the words he tends to say after them. What it learns is saved in
a small JSON file so it carries over to the next day.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, List, Optional

log = logging.getLogger(__name__)

DATA = Path(__file__).resolve().parent / "data"
CARE_RANK = 500  # care words rank as if they were this common
UNKNOWN_RANK = 1_000_000
START = "<s>"  # the "previous word" at the start of a message

# Offered before anything has been typed, until the patient's own habits take over.
STARTERS = ["I", "PLEASE", "YES", "NO", "CAN", "WHERE", "WHAT", "THANK"]

# Likely next words after a few common openers, until the patient's own habits take over.
FOLLOWERS = {
    "I": ["WANT", "NEED", "AM", "FEEL"],
    "AM": ["TIRED", "COLD", "HOT", "OK"],
    "WANT": ["TO", "WATER", "MY", "THE"],
    "NEED": ["TO", "HELP", "THE", "MY"],
    "FEEL": ["SICK", "TIRED", "COLD", "HOT"],
    "PLEASE": ["HELP", "TURN", "CALL", "GIVE"],
    "MY": ["WIFE", "HEAD", "BACK", "LEG"],
    "THANK": ["YOU"],
}

_WORD = re.compile(r"[A-Za-z]+")


def _read_words(path: Path) -> List[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [w.strip().upper() for w in lines if w.strip() and not w.startswith("#")]


class Predictor:
    def __init__(self, learned_path: Optional[Path] = None, extra_words: Iterable[str] = ()):
        self.learned_path = learned_path
        self.rank = {}
        for i, w in enumerate(_read_words(DATA / "english_words.txt")):
            self.rank.setdefault(w, i)
        for w in _read_words(DATA / "care_words.txt"):
            self.rank[w] = min(self.rank.get(w, UNKNOWN_RANK), CARE_RANK)
        for text in extra_words:  # e.g. the Needs tile labels
            for w in _WORD.findall(text.upper()):
                self.rank[w] = min(self.rank.get(w, UNKNOWN_RANK), CARE_RANK)
        self.by_rank = sorted(self.rank, key=self.rank.get)
        self.used: Counter = Counter()  # word -> times spoken
        self.pairs: Counter = Counter()  # "PREV NEXT" -> times spoken
        self._load()

    # Suggestions

    def suggest(self, text: str, n: int = 4) -> List[str]:
        """The best n words for the text typed so far, in capitals like the keys."""
        words = _WORD.findall(text.upper())
        ends_mid_word = bool(text) and text[-1].isalpha()
        prefix = words[-1] if ends_mid_word else ""
        before = words[:-1] if ends_mid_word else words
        prev = before[-1] if before else START

        if prefix:
            return self._complete(prefix, prev, n)
        return self._next(prev, n)

    def _complete(self, prefix: str, prev: str, n: int) -> List[str]:
        def score(w: str):
            return (-self.pairs[f"{prev} {w}"], -self.used[w], self.rank.get(w, UNKNOWN_RANK))

        known = [w for w in self.used if w.startswith(prefix) and w != prefix]
        out = sorted(known, key=score)[:n]
        for w in self.by_rank:
            if len(out) >= n:
                break
            if w.startswith(prefix) and w != prefix and w not in out:
                out.append(w)
        return sorted(out, key=score)

    def _next(self, prev: str, n: int) -> List[str]:
        followers = [(c, pair.split(" ", 1)[1]) for pair, c in self.pairs.items() if pair.startswith(prev + " ")]
        out = [w for _, w in sorted(followers, key=lambda cw: (-cw[0], self.rank.get(cw[1], UNKNOWN_RANK)))][:n]
        fallback = STARTERS if prev == START else FOLLOWERS.get(prev, []) + self.by_rank
        for w in fallback:
            if len(out) >= n:
                break
            if w not in out:
                out.append(w)
        return out

    # Learning

    def learn(self, message: str) -> None:
        """Remember a message the patient spoke."""
        words = _WORD.findall(message.upper())
        if not words:
            return
        self.used.update(words)
        self.pairs.update(f"{a} {b}" for a, b in zip([START] + words, words))
        self._save()

    def _load(self) -> None:
        if self.learned_path is None or not self.learned_path.exists():
            return
        try:
            data = json.loads(self.learned_path.read_text(encoding="utf-8"))
            self.used.update({w: int(c) for w, c in data.get("words", {}).items()})
            self.pairs.update({p: int(c) for p, c in data.get("pairs", {}).items()})
        except (OSError, ValueError, AttributeError):
            log.exception("Could not read learned words from %s", self.learned_path)

    def _save(self) -> None:
        if self.learned_path is None:
            return
        try:
            self.learned_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"words": dict(self.used), "pairs": dict(self.pairs)}
            self.learned_path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            log.exception("Could not save learned words")
