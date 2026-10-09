# Word prediction v2: six better, less repetitive suggestions

Status: items 1, 2 and 5 are built. Items 3 and 4 need the Tatoeba data, which `tools/build_word_data.py` generates once the file can be downloaded.

## What the patient sees today

`commu_aid/predict.py` offers 4 words. Output from the current code with 6 slots asked for:

| Typed | Suggestions today | Problem |
|---|---|---|
| `WAN` | WANT, WANTED, WANTS, WANNA, WANTING, WANG | five forms of one word, plus a surname |
| `HEA` | HEAD, HEALTH, HEART, HEARD, HEAR, HEAVY | HEARD and HEAR both shown |
| `GO` | GOOD, GOING, GOT, GOD, GOVERNMENT, GONNA | GOVERNMENT is news vocabulary |
| `CAN ` | THE, TO, AND, OF, A, IN | no real next-word guess once past the 8 seeded openers |
| `THE ` | THE, TO, AND, OF, A, IN | offers THE right after THE |

## Changes

1. **Six suggestions.** The new keyboard layout (PR #21) already has 6 word buttons and sizes them from the space it gives the row; `Predictor.suggest` now returns 6 by default.
2. **One form per word.** Suggestions are grouped by a small built-in stemmer (plural `-s/-es/-ies`, `-ed`, `-ing`, `-'s`, plus a short irregular table such as HEAR/HEARD, GO/WENT/GONE). Only the best-scoring member of each group is shown. A form the patient has used himself still wins over the dictionary form.
3. **Everyday, informal words first.** Re-rank `english_words.txt` toward spoken English (subtitle and conversation frequency rather than web/news), drop proper nouns, abbreviations and offensive words, and keep the care-word boost. Informal forms such as OK, YEAH, GONNA, WANNA stay in.
4. **Real next-word guesses.** Replace the 8-entry `FOLLOWERS` table with a bundled bigram file (top 6 followers for the ~2,000 most common words), built once from a conversational sentence corpus and shipped as JSON so it works offline. Never suggest the word just typed.
5. **Patient habits stay on top.** Words and word pairs the patient has spoken still rank first; `words.json` keeps its format so nothing learned so far is lost.

## Defaults picked (tell me to change any)

- Corpus for re-ranking and bigrams: Tatoeba English sentences (short everyday sentences, CC BY 2.0 FR), with wordfreq kept as the fallback for words Tatoeba lacks. A build script under `tools/` regenerates the data files; the app only reads the shipped files.
- Stemming is hand-written rules, no new dependency.

## Tests

Extend `tests/test_predict.py`: 6 results; no two from one word group (`WAN`, `HEA`); no repeated previous word; `CAN ` gives verbs; learned words still first; existing tests keep passing.

## Coordination

The keyboard layout redesign (number row, bigger keys, yes/no, Delete) owns `KeyboardPage` geometry. This PR only changes `SUGGESTIONS` and relies on the top row staying a full-width row of word buttons.
