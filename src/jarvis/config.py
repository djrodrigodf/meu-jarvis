"""Load local configuration without persisting credentials."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def default_config_path() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".config")
    return base / "Jarvis" / "config.json"


def default_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share")
    return base / "Jarvis"


@dataclass(frozen=True)
class Project:
    path: Path
    compose_file: str | None = None


@dataclass(frozen=True)
class VoiceSettings:
    wake_model: str = "hey jarvis"
    wake_threshold: float = 0.5
    followup_seconds: int = 30
    whisper_model: str = "small"
    language: str = "pt"
    tts_provider: str = "piper"
    tts_piper_voice: str = "pt_BR-faber-medium"
    tts_voice: str = "pt-BR-AntonioNeural"
    tts_rate: str = "-5%"
    tts_pitch: str = "-10Hz"


@dataclass(frozen=True)
class Settings:
    provider: str = "local"
    model: str = ""
    code_command: str = "code"
    apps: dict[str, Path] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    scripts: dict[str, Path] = field(default_factory=dict)
    voice: VoiceSettings = field(default_factory=VoiceSettings)
    data_dir: Path = field(default_factory=default_data_dir)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise ValueError(f"'{name}' deve ser um objeto JSON.")
    return value


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{name}' deve ser uma string não vazia.")
    return value.strip()


def load_settings(path: Path | None = None) -> Settings:
    path = path or default_config_path()
    if not path.exists():
        return Settings()
    raw = _mapping(json.loads(path.read_text(encoding="utf-8")), "configuração")
    provider = raw.get("provider", "local")
    if provider not in {"local", "openai", "anthropic"}:
        raise ValueError("'provider' deve ser local, openai ou anthropic.")
    model = raw.get("model", "")
    if not isinstance(model, str):
        raise ValueError("'model' deve ser uma string.")
    if provider != "local" and not model.strip():
        raise ValueError("Configure 'model' ao escolher um provedor de IA.")
    apps = {
        _string(name, "nome do aplicativo"): Path(_string(value, f"apps.{name}")).expanduser()
        for name, value in _mapping(raw.get("apps", {}), "apps").items()
    }
    projects: dict[str, Project] = {}
    for name, item in _mapping(raw.get("projects", {}), "projects").items():
        item = _mapping(item, f"projects.{name}")
        compose_file = item.get("compose_file")
        if compose_file is not None:
            compose_file = _string(compose_file, f"projects.{name}.compose_file")
        projects[_string(name, "nome do projeto")] = Project(
            Path(_string(item.get("path"), f"projects.{name}.path")).expanduser(), compose_file
        )
    scripts = {
        _string(name, "nome do script"): Path(_string(value, f"scripts.{name}")).expanduser()
        for name, value in _mapping(raw.get("scripts", {}), "scripts").items()
    }
    voice_raw = _mapping(raw.get("voice", {}), "voice")
    threshold = voice_raw.get("wake_threshold", 0.5)
    if (
        isinstance(threshold, bool)
        or not isinstance(threshold, (int, float))
        or not 0 < threshold <= 1
    ):
        raise ValueError("'voice.wake_threshold' deve estar entre 0 e 1.")
    followup_seconds = voice_raw.get("followup_seconds", 30)
    if (
        isinstance(followup_seconds, bool)
        or not isinstance(followup_seconds, int)
        or not 5 <= followup_seconds <= 120
    ):
        raise ValueError("'voice.followup_seconds' deve estar entre 5 e 120 segundos.")
    tts_provider = voice_raw.get("tts_provider", "piper")
    if tts_provider not in {"system", "piper", "edge"}:
        raise ValueError("'voice.tts_provider' deve ser system, piper ou edge.")
    tts_piper_voice = _string(
        voice_raw.get("tts_piper_voice", "pt_BR-faber-medium"), "voice.tts_piper_voice"
    )
    if tts_piper_voice not in {"en_GB-alan-medium", "pt_BR-faber-medium"}:
        raise ValueError(
            "'voice.tts_piper_voice' deve ser en_GB-alan-medium ou pt_BR-faber-medium."
        )
    tts_voice = _string(voice_raw.get("tts_voice", "pt-BR-AntonioNeural"), "voice.tts_voice")
    if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}-[A-Za-z]+Neural", tts_voice):
        raise ValueError("'voice.tts_voice' deve ser um nome de voz neural válido.")
    tts_rate = _string(voice_raw.get("tts_rate", "-5%"), "voice.tts_rate")
    tts_pitch = _string(voice_raw.get("tts_pitch", "-10Hz"), "voice.tts_pitch")
    if not re.fullmatch(r"[+-](?:[0-4]?\d|50)%", tts_rate):
        raise ValueError("'voice.tts_rate' deve estar entre -50% e +50%.")
    if not re.fullmatch(r"[+-](?:[0-4]?\d|50)Hz", tts_pitch):
        raise ValueError("'voice.tts_pitch' deve estar entre -50Hz e +50Hz.")
    voice = VoiceSettings(
        wake_model=_string(voice_raw.get("wake_model", "hey jarvis"), "voice.wake_model"),
        wake_threshold=float(threshold),
        followup_seconds=followup_seconds,
        whisper_model=_string(voice_raw.get("whisper_model", "small"), "voice.whisper_model"),
        language=_string(voice_raw.get("language", "pt"), "voice.language"),
        tts_provider=tts_provider,
        tts_piper_voice=tts_piper_voice,
        tts_voice=tts_voice,
        tts_rate=tts_rate,
        tts_pitch=tts_pitch,
    )
    return Settings(
        provider=provider,
        model=model.strip(),
        code_command=_string(raw.get("code_command", "code"), "code_command"),
        apps=apps,
        projects=projects,
        scripts=scripts,
        voice=voice,
    )
