from commu_aid.config import SpeechConfig
from commu_aid.speech import Speaker, parse_say_voices

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
