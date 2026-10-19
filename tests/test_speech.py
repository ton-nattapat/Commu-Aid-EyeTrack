from commu_aid.config import SpeechConfig
from commu_aid.speech import Speaker, parse_say_voices, pick_voice, sapi_languages, sapi_rate

SAY_LISTING = """\
Albert              en_US    # Hello! My name is Albert.
Eddy (English (UK)) en_GB    # Hello! My name is Eddy.
Kanya               th_TH    # สวัสดีค่ะ ดิฉันชื่อคันยา
Kanya (Enhanced)    th_TH    # สวัสดีค่ะ ดิฉันชื่อคันยา
Narisa (Premium)    th_TH    # สวัสดีค่ะ
"""


def test_parse_say_voices_keeps_names_with_spaces_and_brackets():
    assert parse_say_voices(SAY_LISTING, "th") == ["Kanya", "Kanya (Enhanced)", "Narisa (Premium)"]
    assert parse_say_voices(SAY_LISTING, "en") == ["Albert", "Eddy (English (UK))"]


def test_system_voice_leaves_the_voice_name_out():
    speaker = Speaker(SpeechConfig(engine="none", voice_th="system", voice_en="Samantha"))
    assert speaker._voice_for("th") == "" and speaker._voice_for("en") == "Samantha"
    speaker.close()


def test_sapi_languages_reads_hex_lcids():
    assert sapi_languages("41E") == ["th"]
    assert sapi_languages("409;9") == ["en"]
    assert sapi_languages("809") == ["en"]  # English (UK)
    assert sapi_languages("411") == [] and sapi_languages("") == []


def test_sapi_rate_follows_words_per_minute():
    assert sapi_rate(180) == 0
    assert sapi_rate(120) < 0 < sapi_rate(300)
    assert sapi_rate(540) == 10 and sapi_rate(20) == -10


WINDOWS_VOICES = [("Microsoft David", ["en"]), ("Microsoft Pattara", ["th"]), ("Microsoft Zira", ["en"])]


def test_pick_voice_by_name_then_by_language():
    assert pick_voice(WINDOWS_VOICES, "Pattara", "th") == 1
    assert pick_voice(WINDOWS_VOICES, "zira", "en") == 2
    # A Mac voice name saved in config.yaml, or "system": the first voice for the language.
    assert pick_voice(WINDOWS_VOICES, "Kanya", "th") == 1
    assert pick_voice(WINDOWS_VOICES, "", "en") == 0
    assert pick_voice(WINDOWS_VOICES[:1], "", "th") is None
