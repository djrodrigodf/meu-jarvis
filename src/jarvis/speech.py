"""Response speech with an optional neural voice and local fallback."""

from __future__ import annotations

import asyncio
import io
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Protocol
from urllib.request import urlopen

from jarvis.config import VoiceSettings, default_data_dir

PIPER_VOICES = {
    "en_GB-alan-medium": "en/en_GB/alan/medium",
    "pt_BR-faber-medium": "pt/pt_BR/faber/medium",
}
PIPER_BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0"


def spoken_text(text: str) -> str:
    """Remove common Markdown marks before reading a model answer aloud."""
    text = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"(?m)^\s*(?:#{1,6}\s+|[-*]\s+)", "", text)
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip()


class Speaker(Protocol):
    def speak(self, text: str) -> None: ...


class SystemSpeaker:
    """Windows SAPI voice, available without a network connection."""

    def __init__(self) -> None:
        try:
            import pyttsx3
        except ImportError as exc:
            raise RuntimeError("Instale o extra de voz: pip install -e '.[voice]'.") from exc
        self.engine = pyttsx3.init()
        for voice in self.engine.getProperty("voices"):
            if "david" in voice.name.casefold():
                self.engine.setProperty("voice", voice.id)
                break
        self.engine.setProperty("rate", 165)

    def speak(self, text: str) -> None:
        self.engine.say(spoken_text(text))
        self.engine.runAndWait()


class PiperSpeaker:
    """Piper neural voice synthesized and played entirely on this computer."""

    def __init__(self, settings: VoiceSettings, fallback: Speaker) -> None:
        self.settings = settings
        self.fallback = fallback
        self.voice: Any = None

    def _model_path(self) -> Path:
        name = self.settings.tts_piper_voice
        model_dir = default_data_dir() / "models" / "piper"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / f"{name}.onnx"
        config_path = model_dir / f"{name}.onnx.json"
        for destination in (model_path, config_path):
            if destination.is_file() and destination.stat().st_size:
                continue
            suffix = ".onnx.json" if destination == config_path else ".onnx"
            url = f"{PIPER_BASE_URL}/{PIPER_VOICES[name]}/{name}{suffix}"
            partial = destination.with_name(destination.name + ".partial")
            print(f"Baixando voz local {name}: {destination.name}...")
            try:
                with urlopen(url, timeout=60) as response, partial.open("wb") as output:
                    shutil.copyfileobj(response, output)
                if not partial.stat().st_size:
                    raise RuntimeError("O download do modelo de voz ficou vazio.")
                os.replace(partial, destination)
            finally:
                partial.unlink(missing_ok=True)
        json.loads(config_path.read_text(encoding="utf-8"))
        return model_path

    def _speak_local(self, text: str) -> None:
        import numpy as np
        import sounddevice as sd
        from piper.config import SynthesisConfig
        from piper.voice import PiperVoice

        if self.voice is None:
            model_path = self._model_path()
            self.voice = PiperVoice.load(str(model_path), str(model_path) + ".json")
        config = SynthesisConfig(length_scale=1.08)
        samples = [chunk.audio_int16_array for chunk in self.voice.synthesize(text, config)]
        if not samples:
            raise RuntimeError("Piper não gerou áudio.")
        sd.play(np.concatenate(samples), self.voice.config.sample_rate)
        sd.wait()

    def speak(self, text: str) -> None:
        try:
            self._speak_local(spoken_text(text))
        except Exception as exc:
            print(f"Aviso: voz Piper indisponível ({exc}); usando voz do Windows.")
            self.fallback.speak(text)


class EdgeSpeaker:
    """Natural speech; only the response text is sent to the speech service."""

    def __init__(self, settings: VoiceSettings, fallback: Speaker) -> None:
        self.settings = settings
        self.fallback = fallback

    async def _synthesize(self, text: str) -> bytes:
        try:
            import edge_tts
        except ImportError as exc:
            raise RuntimeError("Instale o extra neural: pip install -e '.[neural]'.") from exc
        request = edge_tts.Communicate(
            text,
            voice=self.settings.tts_voice,
            rate=self.settings.tts_rate,
            pitch=self.settings.tts_pitch,
        )
        chunks = []
        async for chunk in request.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        if not chunks:
            raise RuntimeError("O serviço de voz não retornou áudio.")
        return b"".join(chunks)

    def _play(self, audio: bytes) -> None:
        try:
            import av
            import numpy as np
            import sounddevice as sd
            from av.audio.resampler import AudioResampler
        except ImportError as exc:
            raise RuntimeError("Instale os extras de voz e neural.") from exc
        samples: list[Any] = []
        resampler = AudioResampler(format="s16", layout="mono", rate=24000)
        with av.open(io.BytesIO(audio), format="mp3") as container:
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    samples.append(
                        np.frombuffer(bytes(converted.planes[0]), dtype=np.int16)[
                            : converted.samples
                        ].copy()
                    )
            for converted in resampler.resample(None):
                samples.append(
                    np.frombuffer(bytes(converted.planes[0]), dtype=np.int16)[
                        : converted.samples
                    ].copy()
                )
        if not samples:
            raise RuntimeError("Não foi possível decodificar o áudio recebido.")
        sd.play(np.concatenate(samples), 24000)
        sd.wait()

    def speak(self, text: str) -> None:
        try:
            audio = asyncio.run(asyncio.wait_for(self._synthesize(spoken_text(text)), timeout=30))
            self._play(audio)
        except Exception as exc:
            print(f"Aviso: voz neural indisponível ({exc}); usando voz local.")
            self.fallback.speak(text)


def make_speaker(settings: VoiceSettings) -> Speaker:
    fallback = SystemSpeaker()
    if settings.tts_provider == "piper":
        return PiperSpeaker(settings, fallback)
    if settings.tts_provider == "edge":
        return EdgeSpeaker(settings, fallback)
    return fallback
