import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import build_word_data as b  # noqa: E402

LINES = ["I want water.", "I want to sleep.", "I want my bed.", "Tom wants water.", "Can you help me?",
         "Can you call Tom?", "Don't go.", "I don't know.", "Can you help her?", "Please help me."] * 3


def test_ranks_common_words_and_drops_names():
    ranked, _ = b.build(LINES, use_wordfreq=False)
    assert ranked[0] in {"i", "want", "can", "you"}
    assert "tom" not in ranked  # a name: always written with a capital
    assert "dont" in ranked  # no apostrophe key, so DON'T is DONT


def test_next_words_come_from_the_sentences():
    _, nxt = b.build(LINES, use_wordfreq=False)
    assert nxt["I"][0] == "WANT"
    assert nxt["CAN"] == ["YOU"]
    assert nxt[b.START][0] == "I"
    assert all("TOM" not in v for v in nxt.values())


def test_writes_files_the_app_can_read(tmp_path):
    src = tmp_path / "eng_sentences.tsv"
    src.write_text("".join(f"{i}\teng\t{t}\n" for i, t in enumerate(LINES)), encoding="utf-8")
    b.main([str(src), "--no-wordfreq", "--out", str(tmp_path)])
    words = [w for w in (tmp_path / "english_words.txt").read_text().splitlines() if not w.startswith("#")]
    assert "want" in words
    assert json.loads((tmp_path / "next_words.json").read_text())["I"][0] == "WANT"
