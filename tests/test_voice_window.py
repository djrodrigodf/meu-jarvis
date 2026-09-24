import threading
from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.config import VoiceSettings
from jarvis.voice import VoiceLoop


class FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def stop(self):
        pass

    def start(self):
        pass


def test_two_turns_use_one_wake_and_window_closes_after_silence(monkeypatch):
    monkeypatch.setattr("jarvis.voice.time.sleep", lambda _seconds: None)
    loop = VoiceLoop.__new__(VoiceLoop)
    loop.settings = VoiceSettings(followup_seconds=30)
    loop.core = SimpleNamespace(
        handle=Mock(side_effect=["Resposta um", "Resposta dois"]), awaiting_followup=False
    )
    loop.sd = SimpleNamespace(RawInputStream=lambda **_kwargs: FakeStream())
    loop.stop_event = threading.Event()
    loop.status = Mock()
    loop.speaker = SimpleNamespace(speak=Mock())
    wake = Mock(side_effect=[True, False])
    capture = Mock(side_effect=[b"primeiro", b"segundo", b""])
    loop._wait_for_wake = wake
    loop._capture_command = capture
    loop._transcribe = lambda audio: audio.decode("utf-8")

    loop.run()

    assert wake.call_count == 2
    assert loop.core.handle.call_count == 2
    assert [call.args[1:] for call in capture.call_args_list] == [
        (12, False),
        (30, True),
        (30, True),
    ]
    assert loop.speaker.speak.call_count == 2
