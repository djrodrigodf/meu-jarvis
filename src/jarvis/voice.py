"""Local wake word, speech recognition and speech synthesis."""

from __future__ import annotations

import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

from jarvis.config import VoiceSettings
from jarvis.core import Core
from jarvis.speech import make_speaker

SAMPLE_RATE = 16000
CHUNK = 1280  # 80 ms, as expected by openWakeWord.


class VoiceLoop:
    def __init__(self, settings: VoiceSettings, core: Core) -> None:
        if sys.platform != "win32" and sys.version_info >= (3, 12):
            raise RuntimeError(
                "A voz com openWakeWord e Python 3.12+ é suportada neste projeto no Windows."
            )
        try:
            import numpy as np
            import openwakeword
            import sounddevice as sd
            from faster_whisper import WhisperModel
            from openwakeword.model import Model
        except ImportError as exc:
            raise RuntimeError("Instale o extra de voz: pip install -e '.[voice]'.") from exc
        self.np = np
        self.sd = sd
        self.settings = settings
        self.core = core
        openwakeword.utils.download_models(model_names=[settings.wake_model.replace(" ", "_")])
        self.wake = Model(wakeword_models=[settings.wake_model], inference_framework="onnx")
        self.whisper = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
        self.speaker = make_speaker(settings)

    def _read_frame(self, stream: Any) -> Any:
        data, overflowed = stream.read(CHUNK)
        if overflowed:
            print("Aviso: houve perda de áudio do microfone.")
        return self.np.frombuffer(data, dtype=self.np.int16).copy()

    def _wait_for_wake(self, stream: Any) -> None:
        print(f"Aguardando '{self.settings.wake_model}'... (Ctrl+C para sair)")
        while True:
            scores = self.wake.predict(self._read_frame(stream))
            if scores and max(scores.values()) >= self.settings.wake_threshold:
                self.wake.reset()
                return

    def _capture_command(self, stream: Any) -> bytes:
        print("Ouvindo o pedido...")
        frames: list[bytes] = []
        heard_speech = False
        silence_frames = 0
        for _ in range(150):  # up to 12 seconds
            frame = self._read_frame(stream)
            frames.append(frame.tobytes())
            rms = float(self.np.sqrt(self.np.mean(frame.astype(self.np.float32) ** 2)))
            if rms > 400:
                heard_speech = True
                silence_frames = 0
            elif heard_speech:
                silence_frames += 1
                if silence_frames >= 15:  # 1.2 seconds of silence
                    break
        return b"".join(frames) if heard_speech else b""

    def _transcribe(self, audio: bytes) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temporary:
            path = Path(temporary.name)
        try:
            with wave.open(str(path), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(SAMPLE_RATE)
                wav.writeframes(audio)
            segments, _info = self.whisper.transcribe(
                str(path),
                language=self.settings.language,
                beam_size=1,
                condition_on_previous_text=False,
            )
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            path.unlink(missing_ok=True)

    def run(self) -> None:
        with self.sd.RawInputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=CHUNK,
        ) as stream:
            while True:
                self._wait_for_wake(stream)
                audio = self._capture_command(stream)
                if not audio:
                    print("Nenhum pedido detectado.")
                    continue
                stream.stop()
                try:
                    prompt = self._transcribe(audio)
                    if not prompt:
                        print("Não consegui transcrever o pedido.")
                        continue
                    print(f"Você: {prompt}")
                    answer = self.core.handle(prompt)
                    print(f"JARVIS: {answer}")
                    self.speaker.speak(answer)
                finally:
                    stream.start()
