"""Read a structured forecast from Open-Meteo without browser automation."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jarvis.tools import ToolError

GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"


def _get(url: str, params: dict[str, Any]) -> dict[str, Any]:
    request = Request(f"{url}?{urlencode(params)}", headers={"User-Agent": "MeuJarvis/0.3"})
    try:
        with urlopen(request, timeout=8) as response:
            content = response.read(1_000_001)
    except (OSError, HTTPError, URLError) as exc:
        raise ToolError("Serviço de previsão indisponível. Tente novamente em instantes.") from exc
    if len(content) > 1_000_000:
        raise ToolError("Resposta de previsão grande demais.")
    try:
        data = json.loads(content)
    except (UnicodeError, ValueError) as exc:
        raise ToolError("O serviço de previsão retornou dados inválidos.") from exc
    if not isinstance(data, dict) or data.get("error"):
        raise ToolError("O serviço de previsão não aceitou a consulta.")
    return data


def _condition(code: int) -> str:
    if code == 0:
        return "céu limpo"
    if code in {1, 2, 3}:
        return "parcialmente nublado" if code < 3 else "nublado"
    if code in {45, 48}:
        return "neblina"
    if code in {51, 53, 55, 56, 57}:
        return "garoa"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "chuva"
    if code in {71, 73, 75, 77, 85, 86}:
        return "neve"
    if code in {95, 96, 99}:
        return "trovoadas"
    return "condição variável"


def get_weather(location: str, day: int) -> dict[str, Any]:
    place = _get(GEOCODING, {"name": location, "count": 5, "language": "pt", "format": "json"})
    matches = place.get("results") or []
    if not matches:
        raise ToolError(
            f"Não encontrei a cidade '{location}'. Diga cidade e estado, se necessário."
        )
    query = location.casefold()
    chosen = next(
        (item for item in matches if item.get("name", "").casefold() == query), matches[0]
    )
    try:
        latitude, longitude = chosen["latitude"], chosen["longitude"]
    except (KeyError, TypeError) as exc:
        raise ToolError("O serviço não retornou coordenadas para essa cidade.") from exc
    forecast = _get(
        FORECAST,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,weather_code",
            "daily": (
                "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code"
            ),
            "timezone": "auto",
            "forecast_days": 2,
        },
    )
    try:
        daily = forecast["daily"]
        data = {
            "city": chosen["name"],
            "region": chosen.get("admin1") or chosen.get("country") or "",
            "country": chosen.get("country_code") or "",
            "date": daily["time"][day],
            "day": day,
            "condition": _condition(daily["weather_code"][day]),
            "min_c": round(daily["temperature_2m_min"][day]),
            "max_c": round(daily["temperature_2m_max"][day]),
            "rain_percent": daily["precipitation_probability_max"][day],
            "source": "Open-Meteo",
        }
        if day == 0:
            data["current_c"] = round(forecast["current"]["temperature_2m"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ToolError("O serviço retornou uma previsão incompleta.") from exc
    return data
