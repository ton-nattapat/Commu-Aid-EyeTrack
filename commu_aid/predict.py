"""Offline word prediction for the keyboard.

While the patient types a word, the predictor offers the most likely ways to finish it. Between
words it offers the words that usually come next. It knows 10,000 common English words, ranked
toward everyday spoken English, plus a short list of care words, and it learns from every message
the patient speaks: words he uses are offered first, and so are the words he tends to say after
them. What it learns is saved in a small JSON file so it carries over to the next day.

Only one form of a word is offered at a time (HEAR or HEARD, not both), so the six buttons show
six different words.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path
from typing import FrozenSet, Iterable, List, Optional, Set

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

# Forms that share their first letters with the base word but that the suffix rules below miss.
IRREGULAR = {
    "HEARD": "HEAR", "SAID": "SAY", "SAYS": "SAY", "MADE": "MAKE", "GOES": "GO", "GONE": "GO", "GOING": "GO", "DOING": "DO",
    "DOES": "DO", "DID": "DO", "DONE": "DO", "HAS": "HAVE", "HAD": "HAVE", "SEEN": "SEE",
    "TAKEN": "TAKE", "GIVEN": "GIVE", "KNOWN": "KNOW", "EATEN": "EAT", "FELT": "FEEL",
    "LEFT": "LEAVE", "THOUGHT": "THINK", "CHILDREN": "CHILD", "MEN": "MAN", "WOMEN": "WOMAN",
    "LAID": "LAY", "PAID": "PAY", "SLEPT": "SLEEP", "KEPT": "KEEP", "MET": "MEET",
    "WRITTEN": "WRITE", "WROTE": "WRITE", "DRANK": "DRINK", "DRUNK": "DRINK", "BEGAN": "BEGIN",
    "SAT": "SIT", "STOOD": "STAND", "SPOKE": "SPEAK", "SPOKEN": "SPEAK", "BROUGHT": "BRING",
    "BOUGHT": "BUY", "FOUND": "FIND", "WORN": "WEAR", "WORE": "WEAR", "TOLD": "TELL",
}
# Words that end like an inflection but are words of their own.
NOT_INFLECTED = {
    "NEWS", "THIS", "HIS", "YES", "ITS", "ALWAYS", "PERHAPS", "SERIES", "SPECIES", "CLOTHES",
    "MORNING", "EVENING", "NOTHING", "SOMETHING", "ANYTHING", "EVERYTHING", "CEILING", "WEDDING",
    "PUDDING", "DURING", "HUNDRED", "NEED", "SPEED", "INDEED", "EXCEED", "PROCEED", "SUCCEED",
}


def word_family(word: str) -> FrozenSet[str]:
    """Rough stems of a word. Two words whose stems overlap are forms of one word, so HEAR, HEARS,
    HEARD and HEARING all match, and so do MAKE and MAKING or STOP and STOPPED."""
    w = word.upper()
    if w in IRREGULAR:
        return word_family(IRREGULAR[w])
    if w in NOT_INFLECTED:
        return frozenset([w])
    for suffix, repl, keep in (("IES", "Y", 2), ("IED", "Y", 2), ("ING", "", 3), ("ED", "", 3)):
        if w.endswith(suffix) and len(w) - len(suffix) >= keep:
            stem = w[: -len(suffix)] + repl
            if repl:
                return frozenset([stem])
            if stem[-1] == stem[-2] and stem[-1] not in "AEIOU":
                return frozenset([stem, stem[:-1]])  # FALL(ING), STOP(PED)
            return frozenset([stem, stem + "E"])  # WALK(ED), MAK(ING)
    if w.endswith("ES") and w[:-2].endswith(("S", "X", "Z", "CH", "SH")) and len(w) > 4:
        return frozenset([w[:-2], w[:-1]])  # BOX(ES), HOUS(ES)
    if w.endswith("S") and not w.endswith(("SS", "US", "IS")) and len(w) > 3:
        return frozenset([w[:-1]])
    return frozenset([w])


def _distinct(words: Iterable[str], n: int, skip: Iterable[str] = ()) -> List[str]:
    """The first n words that are not forms of a word already taken (or of a word in skip)."""
    seen: Set[str] = set()
    for w in skip:
        seen |= word_family(w)
    out = []
    for w in words:
        keys = word_family(w)
        if keys & seen:
            continue
        seen |= keys
        out.append(w)
        if len(out) >= n:
            break
    return out


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
        self.next_words = {}  # word -> the words that most often follow it in everyday sentences
        try:
            data = json.loads((DATA / "next_words.json").read_text(encoding="utf-8"))
            self.next_words = {k: [w for w in v if isinstance(w, str)] for k, v in data.items() if isinstance(v, list)}
        except (OSError, ValueError, AttributeError):
            log.info("No next-word table; using the built-in followers only")
        self.used: Counter = Counter()  # word -> times spoken
        self.pairs: Counter = Counter()  # "PREV NEXT" -> times spoken
        self._load()

    # Suggestions

    def suggest(self, text: str, n: int = 6) -> List[str]:
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

        def candidates():
            yield from sorted((w for w in self.used if w.startswith(prefix) and w != prefix), key=score)
            for w in self.by_rank:
                if w.startswith(prefix) and w != prefix:
                    yield w

        # Collect a few spare words so the best form of each word can be chosen before trimming.
        pool = []
        for w in candidates():
            if w not in pool:
                pool.append(w)
            if len(pool) >= n * 4:
                break
        return sorted(_distinct(sorted(pool, key=score), n), key=score)

    def _next(self, prev: str, n: int) -> List[str]:
        followers = [(c, pair.split(" ", 1)[1]) for pair, c in self.pairs.items() if pair.startswith(prev + " ")]
        learned = [w for _, w in sorted(followers, key=lambda cw: (-cw[0], self.rank.get(cw[1], UNKNOWN_RANK)))]
        if prev == START:
            fallback = STARTERS + self.next_words.get(START, [])
        else:
            fallback = FOLLOWERS.get(prev, []) + self.next_words.get(prev, [])
        skip = [] if prev == START else [prev]  # never offer the word just said
        return _distinct(learned + fallback + self.by_rank, n, skip)

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
