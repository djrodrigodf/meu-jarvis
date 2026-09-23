from pathlib import Path
from unittest.mock import Mock

from jarvis.config import Project, Settings
from jarvis.core import Core, LocalPlanner, Plan, ToolCall
from jarvis.tools import make_registry


def core(settings=None, planner=None, confirm=None):
    settings = settings or Settings()
    return Core(
        settings,
        make_registry(),
        planner or LocalPlanner(settings),
        confirm or Mock(return_value=False),
    )


def test_heavy_pc_request_returns_status_and_processes():
    answer = core().handle("Jarvis, meu PC está pesado")
    assert "CPU:" in answer
    assert "RAM:" in answer
    assert "Maiores processos:" in answer


def test_docker_requires_explicit_confirmation(tmp_path, monkeypatch):
    compose = tmp_path / "compose.yaml"
    compose.write_text("services: {}", encoding="utf-8")
    settings = Settings(projects={"AgenciaFlow": Project(tmp_path, "compose.yaml")})
    run = Mock()
    monkeypatch.setattr("jarvis.tools.subprocess.run", run)
    denied = core(settings).handle("Jarvis, sobe o Docker do AgenciaFlow")
    assert "cancelado" in denied
    run.assert_not_called()

    confirmation = Mock(return_value=True)
    run.return_value.returncode = 0
    allowed = core(settings, confirm=confirmation).handle("sobe o Docker do AgenciaFlow")
    assert "concluído" in allowed
    assert str(tmp_path) in confirmation.call_args.args[0]
    run.assert_called_once()
    assert run.call_args.args[0] == ["docker", "compose", "-f", str(compose), "up", "-d"]
    assert run.call_args.kwargs["shell"] is False


def test_compose_cannot_leave_project(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (tmp_path / "outside.yaml").write_text("services: {}", encoding="utf-8")
    settings = Settings(projects={"x": Project(project, "../outside.yaml")})
    run = Mock()
    monkeypatch.setattr("jarvis.tools.subprocess.run", run)
    answer = core(settings, confirm=Mock(return_value=True)).handle("sobe docker x")
    assert "deve existir dentro" in answer
    run.assert_not_called()


class MaliciousPlanner:
    def __init__(self, call):
        self.call = call

    def plan(self, _prompt, _registry):
        return Plan(calls=[self.call])

    def finish(self, _prompt, _plan, _results):
        raise AssertionError("Results with errors must not reach the model")


def test_unknown_tool_and_extra_arguments_are_rejected():
    unknown = core(planner=MaliciousPlanner(ToolCall("delete_files", {"path": "C:\\"})))
    assert "Ferramenta desconhecida" in unknown.handle("delete")
    invalid = core(planner=MaliciousPlanner(ToolCall("get_system_status", {"shell": "whoami"})))
    assert "Argumentos" in invalid.handle("status")


def test_url_rejects_embedded_credentials(monkeypatch):
    browser = Mock(return_value=True)
    monkeypatch.setattr("jarvis.tools.webbrowser.open", browser)
    planner = MaliciousPlanner(ToolCall("open_url", {"url": "https://user:secret@example.com"}))
    assert "sem credenciais" in core(planner=planner).handle("abra")
    browser.assert_not_called()


def test_local_planner_routes_compound_project_request(tmp_path):
    settings = Settings(projects={"AgenciaFlow": Project(Path(tmp_path), "compose.yaml")})
    plan = LocalPlanner(settings).plan(
        "Jarvis, abre o AgenciaFlow e sobe o Docker", make_registry()
    )
    assert [call.name for call in plan.calls] == ["open_project", "docker_up"]


def test_completed_action_is_reported_when_ai_summary_fails():
    class FailingSummary:
        def plan(self, _prompt, _registry):
            return Plan(calls=[ToolCall("get_system_status", {})])

        def finish(self, _prompt, _plan, _results):
            raise RuntimeError("network unavailable")

    answer = core(planner=FailingSummary()).handle("status")
    assert "CPU:" in answer
    assert "não consegui gerar o resumo com IA" in answer
