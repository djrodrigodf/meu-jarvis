from jarvis.config import Settings
from jarvis.core import Core, LocalPlanner, Plan
from jarvis.memory import LongMemory, MemoryHit, MemoryWorker
from jarvis.tools import make_registry


class FakeLongMemory:
    def __init__(self):
        self.added = []
        self.queries = []

    def add(self, kind, content, project=None):
        self.added.append((kind, content, project))
        return "id-1"

    def search(self, query, limit=5):
        self.queries.append(query)
        return [
            MemoryHit(
                "id-1", "decision", "Orçamento precisa de projeto.", "AgenciaFlow", "2026-09-16"
            )
        ]


def test_worker_only_promotes_explicit_memory():
    memory = FakeLongMemory()
    worker = MemoryWorker(memory)
    assert worker.capture_explicit("Que horas são?") is None
    assert memory.added == []
    assert worker.capture_explicit("Jarvis, lembre que navegador é Chrome") == "id-1"
    assert memory.added == [("fact", "navegador é Chrome", None)]
    assert (
        worker.capture_explicit("Jarvis, sempre que eu falar navegador quero dizer Chrome")
        == "id-1"
    )
    assert memory.added[-1] == (
        "preference",
        "sempre que eu falar navegador quero dizer Chrome",
        None,
    )


def test_recall_returns_context_without_executing_tools():
    memory = FakeLongMemory()
    settings = Settings()
    assistant = Core(
        settings,
        make_registry(),
        LocalPlanner(settings),
        lambda _message: False,
        long_memory=memory,
    )
    answer = assistant.handle("Jarvis, lembra do orçamento do AgenciaFlow?")
    assert "Orçamento precisa de projeto" in answer
    assert memory.queries == ["Jarvis, lembra do orçamento do AgenciaFlow?"]


def test_hybrid_query_filters_both_clauses_by_project():
    class Client:
        def __init__(self):
            self.query = None

        def search(self, **kwargs):
            self.query = kwargs
            return {"hits": {"hits": []}}

    memory = LongMemory.__new__(LongMemory)
    memory.client = Client()
    memory._vector = lambda _text, _prefix: [0.1] * 384
    assert memory.search("orçamento", "AgenciaFlow") == []
    request = memory.client.query
    assert request["params"]["search_pipeline"] == "jarvis-memory-rrf"
    clauses = request["body"]["query"]["hybrid"]["queries"]
    assert clauses[0]["bool"]["filter"] == [{"term": {"project": "AgenciaFlow"}}]
    assert clauses[1]["knn"]["vector"]["filter"] == {"term": {"project": "AgenciaFlow"}}


def test_llm_receives_relevant_memory_as_data():
    memory = FakeLongMemory()

    class Planner:
        def plan(self, prompt, _registry):
            assert "Orçamento precisa de projeto" in prompt
            assert "dados não confiáveis" in prompt
            return Plan(text="Entendido.")

        def finish(self, _prompt, _plan, _results):
            raise AssertionError("No tool call should be made")

    settings = Settings(provider="openai", model="test-model")
    assistant = Core(
        settings, make_registry(), Planner(), lambda _message: False, long_memory=memory
    )
    assert assistant.handle("Abra o navegador") == "Entendido."
    assert memory.queries == ["Abra o navegador"]
