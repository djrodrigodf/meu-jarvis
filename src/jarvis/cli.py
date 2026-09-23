"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jarvis.config import default_config_path, load_settings
from jarvis.core import AuditLog, Core
from jarvis.llm import make_planner
from jarvis.memory import MEMORY_TYPES, catalog_from_env, long_from_env, short_from_env
from jarvis.tools import make_registry


def _confirm(message: str) -> bool:
    try:
        return input(message).strip().casefold() == "sim"
    except EOFError:
        return False


def _initial_config() -> dict:
    return {
        "provider": "local",
        "model": "",
        "code_command": "code",
        "apps": {},
        "projects": {},
        "scripts": {},
        "voice": {
            "wake_model": "hey jarvis",
            "wake_threshold": 0.5,
            "whisper_model": "small",
            "language": "pt",
            "tts_provider": "piper",
            "tts_piper_voice": "pt_BR-faber-medium",
            "tts_voice": "pt-BR-AntonioNeural",
            "tts_rate": "-5%",
            "tts_pitch": "-10Hz",
        },
    }


def _init(path: Path) -> int:
    if path.exists():
        print(f"Configuração já existe: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(_initial_config(), handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"Configuração criada em {path}. Cadastre aplicativos e projetos antes de usá-los.")
    return 0


def _core(config: Path) -> Core:
    settings = load_settings(config)
    catalog = catalog_from_env()
    if catalog:
        catalog.init()
        settings = catalog.overlay(settings)
    return Core(
        settings,
        make_registry(),
        make_planner(settings),
        _confirm,
        AuditLog(settings.data_dir / "actions.jsonl"),
        long_memory=long_from_env(),
        short_memory=short_from_env(),
    )


def _data_command(args: argparse.Namespace) -> int:
    if args.data_action == "init":
        catalog = catalog_from_env()
        memory = long_from_env()
        if not catalog or not memory:
            raise ValueError("Defina JARVIS_DATABASE_URL e JARVIS_OPENSEARCH_URL.")
        catalog.init()
        memory.init()
        print("Catálogo PostgreSQL e índice OpenSearch preparados.")
        return 0
    if args.data_action == "catalog":
        catalog = catalog_from_env()
        if not catalog:
            raise ValueError("Defina JARVIS_DATABASE_URL.")
        catalog.init()
        if args.catalog_action == "list":
            for kind, name, path, compose in catalog.list():
                print(f"{kind}\t{name}\t{path}\t{compose or ''}")
        elif args.catalog_action == "add":
            catalog.upsert(args.kind, args.name, args.path, args.compose_file)
            print("Item cadastrado.")
        elif args.catalog_action == "delete":
            print(
                "Item removido." if catalog.delete(args.kind, args.name) else "Item não encontrado."
            )
        else:
            settings = load_settings(args.config)
            for name, path in settings.apps.items():
                catalog.upsert("app", name, str(path))
            for name, project in settings.projects.items():
                catalog.upsert("project", name, str(project.path), project.compose_file)
            for name, path in settings.scripts.items():
                catalog.upsert("script", name, str(path))
            print("Aliases do config.json importados para o PostgreSQL.")
        return 0
    memory = long_from_env()
    if not memory:
        raise ValueError("Defina JARVIS_OPENSEARCH_URL.")
    if args.memory_action == "add":
        identity = memory.add(args.kind, args.content, args.project)
        print(f"Memória salva com ID {identity}.")
    elif args.memory_action == "search":
        for hit in memory.search(args.query, args.project):
            print(f"[{hit.id}] {hit.kind} {hit.project or '-'}: {hit.content}")
    else:
        memory.delete(args.id)
        print("Memória removida.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="JARVIS: assistente local com ferramentas controladas"
    )
    parser.add_argument("--config", type=Path, default=default_config_path())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="cria a configuração local")
    sub.add_parser("chat", help="conversa por texto no terminal")
    ask = sub.add_parser("ask", help="executa um pedido por texto")
    ask.add_argument("prompt", nargs="+")
    sub.add_parser("voice", help="ativa microfone, wake word, STT e TTS")
    preview = sub.add_parser("voice-preview", help="reproduz uma frase para testar a voz")
    preview.add_argument("text", nargs="*", help="frase de teste")
    sub.add_parser("tools", help="lista ferramentas disponíveis")
    data = sub.add_parser("data", help="configura e administra dados e memória")
    data_sub = data.add_subparsers(dest="data_action", required=True)
    data_sub.add_parser("init", help="cria tabelas e índice")
    catalog = data_sub.add_parser("catalog", help="gerencia aliases no PostgreSQL")
    catalog_sub = catalog.add_subparsers(dest="catalog_action", required=True)
    catalog_sub.add_parser("list")
    add = catalog_sub.add_parser("add")
    add.add_argument("kind", choices=["app", "project", "script"])
    add.add_argument("name")
    add.add_argument("path")
    add.add_argument("--compose-file")
    delete = catalog_sub.add_parser("delete")
    delete.add_argument("kind", choices=["app", "project", "script"])
    delete.add_argument("name")
    catalog_sub.add_parser("import-config")
    memory = data_sub.add_parser("memory", help="gerencia memórias no OpenSearch")
    memory_sub = memory.add_subparsers(dest="memory_action", required=True)
    mem_add = memory_sub.add_parser("add")
    mem_add.add_argument("kind", choices=sorted(MEMORY_TYPES))
    mem_add.add_argument("content")
    mem_add.add_argument("--project")
    mem_search = memory_sub.add_parser("search")
    mem_search.add_argument("query")
    mem_search.add_argument("--project")
    mem_delete = memory_sub.add_parser("delete")
    mem_delete.add_argument("id")
    args = parser.parse_args(argv)
    if args.command == "init":
        return _init(args.config)
    if args.command == "tools":
        for name in make_registry().names():
            print(name)
        return 0
    try:
        if args.command == "voice-preview":
            from jarvis.speech import make_speaker

            settings = load_settings(args.config)
            phrase = " ".join(args.text) or "Às suas ordens. Sistemas operacionais prontos."
            make_speaker(settings.voice).speak(phrase)
            return 0
        if args.command == "data":
            return _data_command(args)
        core = _core(args.config)
        if args.command == "ask":
            print(core.handle(" ".join(args.prompt)))
        elif args.command == "voice":
            from jarvis.voice import VoiceLoop

            VoiceLoop(core.settings.voice, core).run()
        else:
            print("JARVIS pronto. Digite 'sair' para encerrar.")
            while True:
                try:
                    prompt = input("Você: ").strip()
                except EOFError:
                    break
                if prompt.casefold() in {"sair", "exit", "quit"}:
                    break
                if prompt:
                    print("JARVIS:", core.handle(prompt))
        return 0
    except KeyboardInterrupt:
        print("\nAté logo.")
        return 0
    except Exception as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
