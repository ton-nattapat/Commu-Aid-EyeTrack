from commu_aid.predict import Predictor, word_family


def test_completes_the_word_being_typed():
    p = Predictor()
    assert p.suggest("I WANT WAT")[0] == "WATER"
    assert all(w.startswith("TH") for w in p.suggest("TH"))
    assert len(p.suggest("TH", n=4)) == 4
    assert len(p.suggest("TH")) == 6


def test_care_words_are_known():
    p = Predictor(extra_words=["Call caregiver"])
    assert "SUCTION" in p.suggest("SUC")
    assert "CAREGIVER" in p.suggest("CAREG")


def test_offers_next_words_between_words():
    p = Predictor()
    assert p.suggest("")[:4] == ["I", "PLEASE", "YES", "NO"]
    assert p.suggest("I ")[0] == "WANT"


def same_word(a, b):
    return bool(word_family(a) & word_family(b))


def test_offers_one_form_of_each_word():
    p = Predictor()
    for typed in ["WAN", "HEA", "PLE", "NEE", "LIK", "LOO", "CAL"]:
        words = p.suggest(typed)
        assert not any(same_word(a, b) for i, a in enumerate(words) for b in words[i + 1 :]), (typed, words)


def test_word_families():
    for forms in [
        ["HEAR", "HEARS", "HEARD", "HEARING"],
        ["WANT", "WANTS", "WANTED", "WANTING"],
        ["MAKE", "MAKES", "MAKING", "MADE"],
        ["STOP", "STOPS", "STOPPED", "STOPPING"],
        ["FALL", "FALLS", "FALLING"],
        ["CRY", "CRIES", "CRIED"],
        ["HOUSE", "HOUSES"],
        ["BOX", "BOXES"],
        ["GO", "GOES", "GOING", "GONE"],
    ]:
        assert all(same_word(forms[0], f) for f in forms), forms
    for a, b in [("HEART", "HEAR"), ("EVENING", "EVEN"), ("NEWS", "NEW"), ("CUT", "CUTE"),
                 ("CUTTING", "CUTE"), ("TIME", "TIM"), ("NOT", "NOTE"), ("THIS", "THE")]:
        assert not same_word(a, b), (a, b)


def test_never_offers_the_word_just_said():
    p = Predictor()
    for typed in ["THE ", "I ", "WATER ", "HELP "]:
        assert typed.strip() not in p.suggest(typed)


def test_learned_form_wins_over_the_dictionary_form(tmp_path):
    p = Predictor(tmp_path / "words.json")
    p.learn("I heard you")
    assert "HEARD" in p.suggest("HEA")
    assert "HEAR" not in p.suggest("HEA")


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
