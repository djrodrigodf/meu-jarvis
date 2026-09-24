from unittest.mock import Mock

from jarvis.config import Settings
from jarvis.core import Core, LocalPlanner
from jarvis.profile import explicit_fact, explicit_facts, weather_request
from jarvis.tools import ToolError, make_registry
from jarvis.weather import get_weather


class ProfileStore:
    def __init__(self):
        self.facts = {}

    def set_profile(self, key, value):
        self.facts[key] = value

    def get_profile(self, key):
        return self.facts.get(key)

    def delete_profile(self, key):
        return self.facts.pop(key, None) is not None


def assistant(store=None, progress=None):
    settings = Settings()
    return Core(
        settings,
        make_registry(),
        LocalPlanner(settings),
        lambda _message: False,
        catalog=store,
        progress=progress,
    )


def test_explicit_profile_facts_persist_and_can_be_recalled():
    store = ProfileStore()
    jarvis = assistant(store)
    assert "Rodrigo" in jarvis.handle("Meu nome é Rodrigo")
    assert "Brasília" in jarvis.handle("Moro em Brasília")
    assert store.facts == {"name": "Rodrigo", "home_city": "Brasília"}
    another_session = assistant(store)
    assert another_session.handle("Qual é meu nome?") == "Seu nome é Rodrigo."
    assert another_session.handle("Qual é minha cidade?") == "Você mora em Brasília."
    assert another_session.handle("Esqueça minha cidade.") == "Esqueci sua cidade."
    assert "Em qual cidade você mora?" in another_session.handle("Qual é minha cidade?")
    assert explicit_fact("O nome do Rodrigo é conhecido") is None
    assert explicit_facts("Meu nome é Ana Maria e moro em Recife") == [
        ("name", "Ana Maria"),
        ("home_city", "Recife"),
    ]
    combined = assistant(ProfileStore())
    assert "Ana Maria" in combined.handle("Meu nome é Ana Maria e moro em Recife")
    assert combined.catalog.facts == {"name": "Ana Maria", "home_city": "Recife"}


def test_profile_followup_accepts_short_answer_and_new_request_cancels_it():
    store = ProfileStore()
    jarvis = assistant(store)
    assert "Como você se chama?" in jarvis.handle("Qual é meu nome?")
    assert jarvis.awaiting_followup
    assert jarvis.handle("Rodrigo") == "Prazer, Rodrigo. Vou lembrar seu nome."
    assert store.get_profile("name") == "Rodrigo"
    assert not jarvis.awaiting_followup
    assert "Em qual cidade" in jarvis.handle("Qual é minha cidade?")
    assert "Agora são" in jarvis.handle("Que horas são?")
    assert store.get_profile("home_city") is None
    assert "Em qual cidade" in jarvis.handle("Qual é minha cidade?")
    assert "Recife" in jarvis.handle("Recife")
    assert assistant(store).handle("Qual é minha cidade?") == "Você mora em Recife."
    assert "Como você se chama?" in assistant(ProfileStore()).handle("Quem sou eu?")


def test_weather_asks_city_then_learns_only_after_success(monkeypatch):
    store = ProfileStore()
    jarvis = assistant(store)
    calls = []

    def fake_weather(city, day):
        calls.append((city, day))
        if city == "cidade inventada":
            raise ToolError("Cidade desconhecida")
        return {
            "city": city,
            "region": "DF",
            "day": day,
            "condition": "nublado",
            "min_c": 18,
            "max_c": 27,
            "rain_percent": 20,
            "current_c": 23,
        }

    monkeypatch.setattr("jarvis.weather.get_weather", fake_weather)
    assert jarvis.handle("Qual a previsão do tempo amanhã?") == (
        "Qual cidade devo usar para a previsão?"
    )
    assert "Cidade desconhecida" in jarvis.handle("cidade inventada")
    assert store.facts == {}
    assert "Fonte: Open-Meteo" in jarvis.handle("Brasília")
    assert store.facts == {"weather_city": "Brasília"}
    assert "Brasília" in jarvis.handle("Vai chover amanhã?")
    assert calls[-1] == ("Brasília", 1)
    assert weather_request("Qual é a previsão do tempo para amanhã?") == (None, 1)
    assert weather_request("Quanto tempo leva para abrir o projeto?") is None
    assert weather_request("Qual a temperatura da CPU?") is None


def test_home_city_has_precedence_but_explicit_weather_city_does_not_replace_it(monkeypatch):
    store = ProfileStore()
    store.set_profile("home_city", "Recife")
    weather = Mock(
        return_value={
            "city": "São Paulo",
            "region": "SP",
            "day": 0,
            "condition": "céu limpo",
            "min_c": 20,
            "max_c": 30,
            "rain_percent": 0,
        }
    )
    monkeypatch.setattr("jarvis.weather.get_weather", weather)
    jarvis = assistant(store)
    jarvis.handle("Como está o tempo em São Paulo?")
    weather.assert_called_with("São Paulo", 0)
    assert store.facts == {"home_city": "Recife"}
    jarvis.handle("Como está o tempo hoje?")
    weather.assert_called_with("Recife", 0)


def test_weather_source_parses_structured_forecast(monkeypatch):
    def fake_get(url, _params):
        if "geocoding" in url:
            return {
                "results": [{"name": "Recife", "latitude": -8, "longitude": -35, "admin1": "PE"}]
            }
        return {
            "current": {"temperature_2m": 26},
            "daily": {
                "time": ["2026-09-23", "2026-09-24"],
                "weather_code": [3, 61],
                "temperature_2m_min": [22, 21],
                "temperature_2m_max": [29, 28],
                "precipitation_probability_max": [30, 90],
            },
        }

    monkeypatch.setattr("jarvis.weather._get", fake_get)
    result = get_weather("Recife", 1)
    assert result["condition"] == "chuva"
    assert result["rain_percent"] == 90
    assert result["source"] == "Open-Meteo"
