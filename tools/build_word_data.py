"""Rebuild the word prediction data from Tatoeba's English sentences.

    python tools/build_word_data.py eng_sentences.tsv.bz2

Download the input from https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2
(short everyday sentences, CC BY 2.0 FR). If wordfreq is installed (pip install wordfreq) its
web-wide frequencies are blended in with a small weight, so common words that Tatoeba happens to
lack still rank sensibly.

Writes two files that the app reads offline:
- commu_aid/data/english_words.txt: the 10,000 words to complete, most useful first
- commu_aid/data/next_words.json: for each common word, the words that most often follow it
"""

from __future__ import annotations

import argparse
import bz2
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, Iterator, List

OUT = Path(__file__).resolve().parent.parent / "commu_aid" / "data"
START = "<s>"  # must match commu_aid.predict.START
WORDS = 10_000
NEXT_FOR = 3_000  # words that get a next-word list
NEXT_PER_WORD = 10  # spares, so the app still has 6 after dropping forms of one word
MIN_PAIR = 3
TATOEBA_WEIGHT = 0.75  # the rest goes to wordfreq

# Never offered, even if common.
BLOCKED = {
    "fuck", "fucking", "fucked", "shit", "bitch", "bastard", "cunt", "dick", "pussy", "asshole",
    "nigger", "nigga", "fag", "faggot", "retard", "whore", "slut", "cock", "damn", "goddamn",
}
SINGLE_LETTERS = {"a", "i"}
# Written with a capital but still worth offering; other capitalised words (Tom, Mary) are names.
CAPITALISED_OK = {
    "ok", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "english", "thai", "thailand", "christmas", "god",
    "mr", "mrs", "ms", "dr", "tv", "internet",
}

_TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def sentences(path: Path) -> Iterator[str]:
    """The text column of a Tatoeba sentences export (id, lang, text), plain or .bz2."""
    opener = bz2.open if path.suffix == ".bz2" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 3:
                yield parts[2]


def tokens(sentence: str) -> List[str]:
    # The keyboard has no apostrophe, so DON'T is typed DONT.
    return [t.replace("'", "") for t in _TOKEN.findall(sentence)]


def count(lines: Iterable[str]):
    words: Counter = Counter()
    pairs: Counter = Counter()
    capitalised: Counter = Counter()  # seen with a capital letter away from the sentence start
    lower: Counter = Counter()
    for line in lines:
        toks = tokens(line)
        for i, t in enumerate(toks):
            if i > 0:
                (capitalised if t[0].isupper() else lower)[t.lower()] += 1
        low = [t.lower() for t in toks]
        words.update(low)
        pairs.update(zip([START] + low, low))
    names = {w for w, c in capitalised.items() if c > lower[w] and w not in CAPITALISED_OK and w != "i"}
    return words, pairs, names


def zipf(c: int, total: int) -> float:
    return math.log10(c / total * 1e9) if c else 0.0


def keep(w: str, names) -> bool:
    return w.isalpha() and w.isascii() and (len(w) > 1 or w in SINGLE_LETTERS) and w not in BLOCKED and w not in names


def build(lines: Iterable[str], use_wordfreq: bool = True, size: int = WORDS):
    words, pairs, names = count(lines)
    total = sum(words.values()) or 1
    web: Dict[str, float] = {}
    if use_wordfreq:
        try:
            from wordfreq import top_n_list, zipf_frequency
        except ImportError:
            print("wordfreq is not installed; ranking from Tatoeba alone", file=sys.stderr)
        else:
            for w in top_n_list("en", 30_000):
                w = w.replace("'", "")
                web.setdefault(w, zipf_frequency(w, "en"))
    weight = TATOEBA_WEIGHT if web else 1.0
    candidates = {w for w in set(words) | set(web) if keep(w, names)}
    score = {w: weight * zipf(words[w], total) + (1 - weight) * web.get(w, 0.0) for w in candidates}
    ranked = sorted(candidates, key=lambda w: (-score[w], w))[:size]

    known = set(ranked)
    nxt: Dict[str, List[str]] = {}
    for prev in [START] + ranked[:NEXT_FOR]:
        nxt[prev.upper() if prev != START else START] = []
    for (a, b), c in sorted(pairs.items(), key=lambda kv: (-kv[1], kv[0])):
        key = START if a == START else a.upper()
        if c < MIN_PAIR or key not in nxt or b not in known or b == a:
            continue
        if len(nxt[key]) < NEXT_PER_WORD:
            nxt[key].append(b.upper())
    return ranked, {k: v for k, v in nxt.items() if v}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sentences", type=Path, help="Tatoeba eng_sentences.tsv or .tsv.bz2")
    ap.add_argument("--no-wordfreq", action="store_true", help="rank from Tatoeba alone")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)

    ranked, nxt = build(sentences(args.sentences), use_wordfreq=not args.no_wordfreq)
    args.out.mkdir(parents=True, exist_ok=True)
    header = [
        f"# {len(ranked):,} common English words, most useful first, ranked toward everyday speech.",
        "# Built by tools/build_word_data.py from Tatoeba English sentences (https://tatoeba.org,",
        "# CC BY 2.0 FR) blended with wordfreq (https://github.com/rspeer/wordfreq, CC BY-SA 4.0).",
    ]
    (args.out / "english_words.txt").write_text("\n".join(header + ranked) + "\n", encoding="utf-8")
    (args.out / "next_words.json").write_text(json.dumps(nxt, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"{len(ranked)} words, next words for {len(nxt)}", file=sys.stderr)


if __name__ == "__main__":
    main()
