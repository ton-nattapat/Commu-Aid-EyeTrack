from commu_aid.predict import Predictor


def test_completes_the_word_being_typed():
    p = Predictor()
    assert p.suggest("I WANT WAT")[0] == "WATER"
    assert all(w.startswith("TH") for w in p.suggest("TH"))
    assert len(p.suggest("TH", n=4)) == 4


def test_care_words_are_known():
    p = Predictor(extra_words=["Call caregiver"])
    assert "SUCTION" in p.suggest("SUC")
    assert "CAREGIVER" in p.suggest("CAREG")


def test_offers_next_words_between_words():
    p = Predictor()
    assert p.suggest("") == ["I", "PLEASE", "YES", "NO"]
    assert p.suggest("I ")[0] == "WANT"


def test_learns_from_spoken_messages_and_remembers(tmp_path):
    path = tmp_path / "words.json"
    p = Predictor(path)
    p.learn("I want my daughter")
    assert p.suggest("I WANT ")[0] == "MY"
    assert p.suggest("I WANT MY D")[0] == "DAUGHTER"
    again = Predictor(path)
    assert again.suggest("I WANT MY ")[0] == "DAUGHTER"


def test_learns_words_it_did_not_know(tmp_path):
    p = Predictor(tmp_path / "words.json")
    assert "SOMCHAI" not in p.suggest("SOM")
    p.learn("call Somchai")
    assert p.suggest("SOM")[0] == "SOMCHAI"


def test_bad_learned_file_is_ignored(tmp_path):
    path = tmp_path / "words.json"
    path.write_text("not json", encoding="utf-8")
    assert Predictor(path).suggest("WAT")[0] == "WATER"
