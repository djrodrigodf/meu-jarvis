from types import SimpleNamespace
from unittest.mock import Mock

from jarvis.config import Settings
from jarvis.core import Core, ToolResult
from jarvis.llm import AnthropicPlanner, OpenAIPlanner, RoutedPlanner
from jarvis.tools import make_registry


def test_openai_planner_passes_function_result_back_to_model():
    planner = OpenAIPlanner.__new__(OpenAIPlanner)
    planner.settings = Settings(provider="openai", model="test-model")
    call = SimpleNamespace(
        type="function_call", name="get_system_status", arguments="{}", call_id="call-1"
    )
    planner.client = SimpleNamespace(
        responses=SimpleNamespace(
            create=Mock(
                side_effect=[
                    SimpleNamespace(output=[call], output_text=""),
                    SimpleNamespace(output=[], output_text="CPU está normal."),
                ]
            )
        )
    )
    plan = planner.plan("Como está o PC?", make_registry())
    assert plan.calls[0].name == "get_system_status"
    answer = planner.finish(
        "Como está o PC?",
        plan,
        [ToolResult("get_system_status", "ok", {"cpu_percent": 10}, "call-1")],
    )
    assert answer == "CPU está normal."
    calls = planner.client.responses.create.call_args_list
    assert calls[0].kwargs["tools"][0]["strict"] is True
    assert calls[1].kwargs["input"][-1]["type"] == "function_call_output"
    assert calls[1].kwargs["input"][-1]["call_id"] == "call-1"


def test_anthropic_planner_passes_tool_result_back_to_model():
    planner = AnthropicPlanner.__new__(AnthropicPlanner)
    planner.settings = Settings(provider="anthropic", model="test-model")
    block = SimpleNamespace(type="tool_use", name="get_processes", input={"limit": 5}, id="u1")
    planner.client = SimpleNamespace(
        messages=SimpleNamespace(
            create=Mock(
                side_effect=[
                    SimpleNamespace(content=[block]),
                    SimpleNamespace(
                        content=[SimpleNamespace(type="text", text="Processos listados.")]
                    ),
                ]
            )
        )
    )
    plan = planner.plan("Liste processos", make_registry())
    assert plan.calls[0].arguments == {"limit": 5}
    answer = planner.finish(
        "Liste processos",
        plan,
        [ToolResult("get_processes", "ok", {"processes": []}, "u1")],
    )
    assert answer == "Processos listados."
    messages = planner.client.messages.create.call_args_list[1].kwargs["messages"]
    assert messages[-1]["content"][0]["tool_use_id"] == "u1"
    assert messages[1]["content"][0]["type"] == "tool_use"


def test_simple_request_uses_local_router_even_with_ai_configured():
    remote = Mock()
    settings = Settings(provider="openai", model="test-model")
    routed = RoutedPlanner(settings, remote)
    assistant = Core(settings, make_registry(), routed, lambda _message: False)
    assert "CPU:" in assistant.handle("Jarvis, meu PC está pesado")
    remote.plan.assert_not_called()
