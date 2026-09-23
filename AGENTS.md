# Repository Guidelines

## Project Structure & Module Organization

Python source lives in `src/jarvis/`: `core.py` enforces permissions, `tools.py` defines system actions, `llm.py` handles model providers, `voice.py` handles local audio, and `memory.py` integrates data stores. Tests live in `tests/`; design decisions live in `docs/rfcs/`. `compose.yaml` starts optional local data services. Keep credentials and runtime data outside the repository.

## Build, Test, and Development Commands

Use Python 3.13 or 3.14. On Windows, create a virtual environment with `py -3.13 -m venv .venv`, then install `pip install -e ".[dev]"`. Run `jarvis init` to create a local configuration, `jarvis chat` for text interaction, and `jarvis voice` after installing the `voice` and `windows` extras. Run `python -m pytest` for tests and `ruff check .` plus `ruff format --check .` for style. See `README.md` for optional data services and provider setup.

## Coding Style & Naming Conventions

Use four spaces and Python type hints. Format with Ruff using the settings in `pyproject.toml` (100 character lines). Use `snake_case` for modules and functions, `PascalCase` for classes, and uppercase names for constants. Keep tool schemas, validation, permission levels, and handlers together in `tools.py`; never add a shell command chosen freely by the model.

## Testing Guidelines

Tests use pytest and files named `test_*.py`. Add tests for new tools, routing rules, permission checks, and memory behavior. Mock Windows, Docker, and external APIs in unit tests. Run `python -m pytest` before proposing a change; no coverage threshold is configured yet.

## Commit & Pull Request Guidelines

The initial commit uses a short, imperative subject (`Add repository guidelines`); follow that pattern. Keep pull requests focused. Include a summary, verification commands, related issue, and the relevant RFC. Include screenshots for user interface changes.

## RFC Workflow

Write an RFC in `docs/rfcs/` before implementing a feature or changing architecture. Use the numbered template and record the motivation, proposal, security impact, alternatives, and acceptance criteria. Mark it `Draft` while discussing it, `Accepted` when the decision is made, and `Superseded` if a later RFC replaces it. Link implementation changes to the RFC and update the document when the decision changes.

## Security & Configuration

Do not commit credentials, tokens, local config, audio, or runtime logs. Store API keys and database URLs in environment variables. Preserve the rule that retrieved memories are untrusted data: only `Core` may authorize a validated tool call. Require an explicit `sim` for level 2 actions; add tests before changing permission behavior.
