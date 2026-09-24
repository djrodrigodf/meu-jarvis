"""Explicit, validated tools exposed to the assistant."""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import psutil

from jarvis.config import Project, Settings


class ToolError(Exception):
    """A tool could not run safely or complete its task."""


class Level(IntEnum):
    READ = 0
    SIMPLE = 1
    CONTROLLED = 2
    DESTRUCTIVE = 3


def field_string(description: str, *, max_length: int = 200) -> dict[str, Any]:
    return {"type": "string", "description": description, "minLength": 1, "maxLength": max_length}


def field_integer(description: str, minimum: int, maximum: int) -> dict[str, Any]:
    return {"type": "integer", "description": description, "minimum": minimum, "maximum": maximum}


def object_schema(**fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    level: Level
    schema: dict[str, Any]
    handler: Callable[[Settings, dict[str, Any]], dict[str, Any]]
    target: Callable[[Settings, dict[str, Any]], str]

    def validate(self, arguments: Any) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            raise ToolError("Argumentos devem ser um objeto JSON.")
        properties = self.schema["properties"]
        if set(arguments) != set(properties):
            raise ToolError(
                f"Argumentos de {self.name}: esperado {', '.join(properties) or 'nenhum'}."
            )
        for key, value in arguments.items():
            rule = properties[key]
            if rule["type"] == "string":
                if not isinstance(value, str) or not value.strip():
                    raise ToolError(f"'{key}' deve ser texto não vazio.")
                if len(value) > rule.get("maxLength", 200):
                    raise ToolError(f"'{key}' é longo demais.")
                if value != value.strip():
                    raise ToolError(f"'{key}' não pode ter espaços nas extremidades.")
            elif rule["type"] == "integer":
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ToolError(f"'{key}' deve ser um número inteiro.")
                if not rule["minimum"] <= value <= rule["maximum"]:
                    raise ToolError(f"'{key}' está fora do intervalo permitido.")
            if "enum" in rule and value not in rule["enum"]:
                raise ToolError(f"'{key}' deve ser um dos valores permitidos.")
        return arguments

    def model_definition(self, provider: str) -> dict[str, Any]:
        if provider == "openai":
            return {
                "type": "function",
                "name": self.name,
                "description": self.description,
                "parameters": self.schema,
                "strict": True,
            }
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError as exc:
            raise ToolError(f"Ferramenta desconhecida: {name}.") from exc

    def definitions(self, provider: str) -> list[dict[str, Any]]:
        return [spec.model_definition(provider) for spec in self._specs.values()]

    def names(self) -> list[str]:
        return list(self._specs)


def _known(items: dict[str, Any], alias: str, kind: str) -> tuple[str, Any]:
    matches = [
        (name, value) for name, value in items.items() if name.casefold() == alias.casefold()
    ]
    if not matches:
        raise ToolError(f"{kind} '{alias}' não cadastrado. Cadastre-o no config.json.")
    if len(matches) > 1:
        raise ToolError(f"{kind} '{alias}' é ambíguo no config.json.")
    return matches[0]


def _project(settings: Settings, alias: str) -> tuple[str, Project]:
    name, project = _known(settings.projects, alias, "Projeto")
    path = project.path.expanduser().resolve()
    if not path.is_dir():
        raise ToolError(f"Diretório do projeto não encontrado: {path}")
    return name, Project(path, project.compose_file)


def _compose_path(project: Project) -> Path:
    if not project.compose_file:
        raise ToolError("O projeto não possui 'compose_file' configurado.")
    candidate = (project.path / project.compose_file).resolve()
    if not candidate.is_relative_to(project.path) or not candidate.is_file():
        raise ToolError("O arquivo Compose deve existir dentro do diretório do projeto.")
    return candidate


def _windows() -> None:
    if sys.platform != "win32":
        raise ToolError("Esta ferramenta requer Windows.")


def _system_status(_settings: Settings, _args: dict[str, Any]) -> dict[str, Any]:
    memory = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / 1024**3, 2),
        "memory_total_gb": round(memory.total / 1024**3, 2),
    }


def _current_time(_settings: Settings, _args: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now().astimezone()
    return {
        "hour": now.hour,
        "minute": now.minute,
        "date": now.date().isoformat(),
        "timezone": now.tzname() or "local",
        "iso": now.isoformat(timespec="seconds"),
    }


def _weather(_settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    from jarvis.weather import get_weather

    return get_weather(args["location"], args["day"])


def _processes(_settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    entries = []
    for process in psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            info = process.info
            memory = info["memory_info"]
            entries.append(
                {
                    "pid": info["pid"],
                    "name": info["name"] or "?",
                    "memory_mb": round(memory.rss / 1024**2, 1) if memory else 0,
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    entries.sort(key=lambda item: item["memory_mb"], reverse=True)
    return {"processes": entries[: args["limit"]]}


def _open_app(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    _windows()
    name, path = _known(settings.apps, args["app"], "Aplicativo")
    path = path.resolve()
    if not path.is_file() or path.suffix.lower() not in {".exe", ".lnk"}:
        raise ToolError(f"Executável ou atalho não encontrado: {path}")
    os.startfile(str(path))  # type: ignore[attr-defined]
    return {"opened": name}


def _open_url(_settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    url = args["url"]
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ToolError("Use uma URL http(s) válida, sem credenciais embutidas.")
    if not webbrowser.open(url):
        raise ToolError("Não foi possível abrir o navegador.")
    return {"opened": url}


def _open_project(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    name, project = _project(settings, args["project"])
    subprocess.Popen([settings.code_command, str(project.path)], cwd=project.path, shell=False)
    return {"opened": name, "path": str(project.path)}


def _docker(settings: Settings, args: dict[str, Any], action: str) -> dict[str, Any]:
    name, project = _project(settings, args["project"])
    compose = _compose_path(project)
    command = ["docker", "compose", "-f", str(compose)]
    command += ["up", "-d"] if action == "up" else ["down"]
    try:
        result = subprocess.run(
            command,
            cwd=project.path,
            shell=False,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"Docker não pôde concluir a ação: {exc}") from exc
    if result.returncode:
        raise ToolError(f"Docker retornou código {result.returncode}: {result.stderr[-500:]}")
    return {"project": name, "action": action, "exit_code": result.returncode}


def _docker_up(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    return _docker(settings, args, "up")


def _docker_down(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    return _docker(settings, args, "down")


def _set_volume(_settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    _windows()
    try:
        from pycaw.pycaw import AudioUtilities
    except ImportError as exc:
        raise ToolError("Instale o extra Windows: pip install -e '.[windows]'.") from exc
    endpoint = AudioUtilities.GetSpeakers().EndpointVolume
    endpoint.SetMasterVolumeLevelScalar(args["percent"] / 100, None)
    return {"volume_percent": args["percent"]}


def _search_files(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    name, project = _project(settings, args["project"])
    query = args["query"].casefold()
    found: list[str] = []
    visited = 0
    for directory, dirs, files in os.walk(project.path, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__"}]
        for filename in files:
            visited += 1
            if query in filename.casefold():
                found.append(str((Path(directory) / filename).relative_to(project.path)))
                if len(found) >= 20:
                    return {"project": name, "files": found, "truncated": True}
            if visited >= 20000:
                return {"project": name, "files": found, "truncated": True}
    return {"project": name, "files": found, "truncated": False}


def _powershell(settings: Settings, args: dict[str, Any]) -> dict[str, Any]:
    _windows()
    name, path = _known(settings.scripts, args["script"], "Script")
    path = path.resolve()
    if path.suffix.lower() != ".ps1" or not path.is_file():
        raise ToolError("O script cadastrado deve ser um arquivo .ps1 existente.")
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(path)],
            cwd=path.parent,
            shell=False,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolError(f"PowerShell não pôde concluir a ação: {exc}") from exc
    if result.returncode:
        raise ToolError(f"Script '{name}' terminou com código {result.returncode}.")
    return {"script": name, "exit_code": result.returncode}


def make_registry() -> ToolRegistry:
    alias = field_string("Nome exato do item cadastrado no config.json", max_length=80)
    return ToolRegistry(
        [
            ToolSpec(
                "get_current_time",
                "Consulta a hora e data atuais do computador",
                Level.READ,
                object_schema(),
                _current_time,
                lambda _s, _a: "relógio local",
            ),
            ToolSpec(
                "get_weather",
                "Consulta previsão do tempo por cidade; day=0 para hoje, day=1 para amanhã",
                Level.READ,
                object_schema(
                    location=field_string("Cidade, opcionalmente com estado e país", max_length=80),
                    day=field_integer("0 para hoje, 1 para amanhã", 0, 1),
                ),
                _weather,
                lambda _s, a: a["location"],
            ),
            ToolSpec(
                "get_system_status",
                "Consulta CPU e uso de memória",
                Level.READ,
                object_schema(),
                _system_status,
                lambda _s, _a: "sistema local",
            ),
            ToolSpec(
                "get_processes",
                "Lista processos que mais usam memória",
                Level.READ,
                object_schema(limit=field_integer("Máximo de processos", 1, 20)),
                _processes,
                lambda _s, _a: "processos locais",
            ),
            ToolSpec(
                "open_app",
                "Abre um aplicativo cadastrado",
                Level.SIMPLE,
                object_schema(app=alias),
                _open_app,
                lambda s, a: str(_known(s.apps, a["app"], "Aplicativo")[1]),
            ),
            ToolSpec(
                "open_url",
                "Abre uma URL http(s) no navegador",
                Level.SIMPLE,
                object_schema(url=field_string("URL completa", max_length=1000)),
                _open_url,
                lambda _s, a: a["url"],
            ),
            ToolSpec(
                "open_project",
                "Abre um projeto cadastrado no VS Code",
                Level.SIMPLE,
                object_schema(project=alias),
                _open_project,
                lambda s, a: str(_known(s.projects, a["project"], "Projeto")[1].path),
            ),
            ToolSpec(
                "set_volume",
                "Ajusta o volume principal do Windows",
                Level.SIMPLE,
                object_schema(percent=field_integer("Percentual de volume", 0, 100)),
                _set_volume,
                lambda _s, a: f"{a['percent']}%",
            ),
            ToolSpec(
                "search_files",
                "Procura nomes de arquivos em um projeto cadastrado",
                Level.READ,
                object_schema(project=alias, query=field_string("Parte do nome do arquivo")),
                _search_files,
                lambda s, a: str(_known(s.projects, a["project"], "Projeto")[1].path),
            ),
            ToolSpec(
                "docker_up",
                "Inicia o Compose de um projeto cadastrado",
                Level.CONTROLLED,
                object_schema(project=alias),
                _docker_up,
                lambda s, a: str(_known(s.projects, a["project"], "Projeto")[1].path),
            ),
            ToolSpec(
                "docker_down",
                "Para o Compose de um projeto cadastrado",
                Level.CONTROLLED,
                object_schema(project=alias),
                _docker_down,
                lambda s, a: str(_known(s.projects, a["project"], "Projeto")[1].path),
            ),
            ToolSpec(
                "run_powershell",
                "Executa um script PowerShell cadastrado, sem argumentos",
                Level.CONTROLLED,
                object_schema(script=alias),
                _powershell,
                lambda s, a: str(_known(s.scripts, a["script"], "Script")[1]),
            ),
        ]
    )
