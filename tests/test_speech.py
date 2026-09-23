"""Speech configuration and failure behavior without external audio services."""

import json
from unittest.mock import Mock

import pytest

from jarvis.config import VoiceSettings, load_settings
from jarvis.speech import EdgeSpeaker, PiperSpeaker, spoken_text


def test_markdown_is_removed_before_speech():
    assert spoken_text("**Status:**\n- CPU: 5%\n- [Ajuda](https://example.com)") == (
        "Status: CPU: 5% Ajuda"
    )


def test_config_rejects_unregistered_piper_model(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"voice": {"tts_piper_voice": "../../unsafe"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="tts_piper_voice"):
        load_settings(path)


def test_piper_failure_uses_system_voice(capsys):
    fallback = Mock()
    speaker = PiperSpeaker(VoiceSettings(), fallback)
    speaker._speak_local = Mock(side_effect=RuntimeError("modelo indisponível"))

    speaker.speak("Teste")

    fallback.speak.assert_called_once_with("Teste")
    assert "modelo indisponível" in capsys.readouterr().out


def test_edge_failure_uses_system_voice(capsys):
    fallback = Mock()
    speaker = EdgeSpeaker(VoiceSettings(tts_provider="edge"), fallback)
    speaker._play = Mock(side_effect=RuntimeError("áudio indisponível"))

    async def synthesize(_text):
        return b"audio"

    speaker._synthesize = synthesize

    speaker.speak("Teste")

    fallback.speak.assert_called_once_with("Teste")
    assert "áudio indisponível" in capsys.readouterr().out
