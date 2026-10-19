"""Windows speech through SAPI, on a real Windows machine (skipped elsewhere)."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_auto_engine_is_sapi_on_windows():
    from commu_aid.config import SpeechConfig
    from commu_aid.speech import Speaker

    speaker = Speaker(SpeechConfig(engine="auto"))
    try:
        assert speaker.engine == "sapi"
        assert isinstance(speaker.voices("en"), list)
    finally:
        speaker.close()


def test_sapi_speaks_with_a_listed_voice(tmp_path):
    import win32com.client

    from commu_aid import speech

    speech._com_init()
    tokens = speech._sapi_tokens()
    print("SAPI voices:", [(name, langs) for name, langs, _ in tokens])
    if not tokens:
        pytest.skip("this Windows has no speech voices installed")
    i = speech.pick_voice([(n, l) for n, l, _ in tokens], "", "en")
    token = tokens[i if i is not None else 0][2]

    out = tmp_path / "speech.wav"
    stream = win32com.client.Dispatch("SAPI.SpFileStream")
    stream.Open(str(out), 3, False)  # SSFMCreateForWrite
    voice = win32com.client.Dispatch("SAPI.SpVoice")
    voice.AudioOutputStream = stream
    voice.Voice = token
    voice.Rate = speech.sapi_rate(200)
    voice.Speak("Water please", 0)
    stream.Close()
    assert out.stat().st_size > 10_000
