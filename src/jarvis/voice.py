"""Local wake word, speech recognition and speech synthesis."""

from __future__ import annotations

import sys
import tempfile
import threading
import time
import wave
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from jarvis.config import VoiceSettings
from jarvis.core import Core
from jarvis.speech import make_speaker

SAMPLE_RATE = 16000
CHUNK = 1280  # 80 ms, as expected by openWakeWord.


class VoiceLoop:
    def __init__(
        self,
        settings: VoiceSettings,
        core: Core,
        status: Callable[[str, str], None] | None = None,
        stop_event: threading.Event | None = None,
    ) -> None:
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
        self.status = status or (lambda _state, _detail: None)
        self.stop_event = stop_event or threading.Event()
        self.status("loading", "Preparando ativação por voz")
        openwakeword.utils.download_models(model_names=[settings.wake_model.replace(" ", "_")])
        self.wake = Model(wakeword_models=[settings.wake_model], inference_framework="onnx")
        self.status("loading", "Carregando reconhecimento de fala")
        self.whisper = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
        self.status("loading", "Preparando a voz")
        self.speaker = make_speaker(settings)

    def _read_frame(self, stream: Any) -> Any:
        data, overflowed = stream.read(CHUNK)
        if overflowed:
            print("Aviso: houve perda de áudio do microfone.")
        return self.np.frombuffer(data, dtype=self.np.int16).copy()

    def _wait_for_wake(self, stream: Any) -> bool:
        print(f"Aguardando '{self.settings.wake_model}'... (Ctrl+C para sair)")
        self.status("idle", "Diga Hey Jarvis")
        while not self.stop_event.is_set():
            scores = self.wake.predict(self._read_frame(stream))
            if scores and max(scores.values()) >= self.settings.wake_threshold:
                self.wake.reset()
                try:
                    name = self.core.catalog.get_profile("name") if self.core.catalog else None
                except Exception:
                    name = None
                greeting = (
                    f"Olá, {name}! O que você precisa?" if name else "Olá! O que você precisa?"
                )
                self.greeting = greeting
                self.status("awake", greeting)
                if sys.platform == "win32":
                    import winsound

                    winsound.Beep(880, 110)
                return True
        return False

    def _capture_command(self, stream: Any, wait_seconds: int, followup: bool) -> bytes:
        print("Aguardando continuação..." if followup else "Ouvindo o pedido...")
        if not followup:
            self.status("listening", getattr(self, "greeting", "Olá! O que você precisa?"))
        deadline = time.monotonic() + wait_seconds
        countdown = -1
        pre_roll: deque[bytes] = deque(maxlen=6)
        frames: list[bytes] = []
        heard_speech = False
        silence_frames = 0
        while not self.stop_event.is_set():
            if not heard_speech:
                remaining = max(0, int(deadline - time.monotonic() + 0.99))
                if remaining == 0:
                    break
                if followup and remaining != countdown:
                    self.status("followup", f"Pode continuar falando · {remaining}s")
                    countdown = remaining
            elif len(frames) >= 150:  # 12 seconds of speech at most
                break
            frame = self._read_frame(stream)
            chunk = frame.tobytes()
            rms = float(self.np.sqrt(self.np.mean(frame.astype(self.np.float32) ** 2)))
            if not heard_speech:
                pre_roll.append(chunk)
                if rms > 400:
                    heard_speech = True
                    frames.extend(pre_roll)
                    self.status("listening", "Ouvindo seu pedido")
            else:
                frames.append(chunk)
                if rms > 400:
                    silence_frames = 0
                else:
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
            while not self.stop_event.is_set():
                if not self._wait_for_wake(stream):
                    break
                followup = False
                while not self.stop_event.is_set():
                    wait_seconds = 12
                    if followup:
                        wait_seconds = self.settings.followup_seconds
                        if self.core.awaiting_followup:
                            wait_seconds = max(wait_seconds, 45)
                    audio = self._capture_command(stream, wait_seconds, followup)
                    if not audio:
                        print("Janela de conversa encerrada.")
                        self.status("idle", "Diga Hey Jarvis para conversar")
                        break
                    stream.stop()
                    try:
                        self.status("transcribing", "Entendendo sua voz")
                        prompt = self._transcribe(audio)
                        if not prompt:
                            print("Não consegui transcrever o pedido.")
                            followup = True
                            continue
                        print(f"Você: {prompt}")
                        if prompt.casefold().strip(" .!?") in {"tchau jarvis", "pode descansar"}:
                            answer = "Até logo."
                            self.status("speaking", answer)
                            self.speaker.speak(answer)
                            break
                        self.status("thinking", "Interpretando seu pedido")
                        answer = self.core.handle(prompt)
                        print(f"JARVIS: {answer}")
                        self.status("speaking", answer[:115])
                        self.speaker.speak(answer)
                        followup = True
                    finally:
                        time.sleep(0.2)
                        stream.start()
