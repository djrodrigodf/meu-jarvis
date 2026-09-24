"""Conservative extraction of explicit personal facts and weather locations."""

from __future__ import annotations

import re
import unicodedata


def _clean(value: str) -> str:
    return value.strip(" \t\r\n.,!?;:")


def explicit_facts(prompt: str) -> list[tuple[str, str]]:
    patterns = (
        ("name", r"\b(?:meu nome [ée]|(?:eu )?me chamo|pode me chamar de)\s+(.+)$"),
        ("home_city", r"\b(?:moro em|minha cidade [ée]|resido em)\s+(.+)$"),
    )
    facts = []
    for key, pattern in patterns:
        match = re.search(pattern, prompt.strip(), flags=re.IGNORECASE)
        if match:
            value = re.split(
                r"[,;.!?]|\s+e\s+(?=(?:moro|resido|meu nome|quero|gostaria|preciso)\b)",
                match.group(1),
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
            value = _clean(value)
            if (
                1 <= len(value) <= 80
                and len(value.split()) <= 6
                and not re.search(
                    r"\b(?:quero|preciso|previsão|tempo|amanhã)\b", value, re.IGNORECASE
                )
            ):
                facts.append((key, value))
    return facts


def explicit_fact(prompt: str) -> tuple[str, str] | None:
    facts = explicit_facts(prompt)
    return facts[0] if facts else None


def weather_request(prompt: str) -> tuple[str | None, int] | None:
    normalized = "".join(
        c for c in unicodedata.normalize("NFKD", prompt.casefold()) if not unicodedata.combining(c)
    )
    if "temperatura" in normalized and re.search(r"\b(?:cpu|gpu|processador|placa)\b", normalized):
        return None
    if not (
        re.search(r"\b(?:previsao|clima|temperatura|chuva|chover)\b", normalized)
        or re.search(
            r"\b(?:como (?:esta|vai estar) o tempo|que tempo faz|"
            r"tempo (?:hoje|amanha|agora|em)|qual (?:e )?o tempo)\b",
            normalized,
        )
    ):
        return None
    day = 1 if "amanha" in normalized else 0
    match = re.search(r"\b(?:em|para)\s+([\wÀ-ÿ][\wÀ-ÿ .,'-]{1,79})", prompt, re.IGNORECASE)
    if not match:
        return None, day
    city = _clean(match.group(1))
    city = re.split(
        r"\s+(?:hoje|amanhã|agora|neste|nesse)\b", city, maxsplit=1, flags=re.IGNORECASE
    )[0]
    if city.casefold() in {"hoje", "amanhã", "amanha", "agora", "mim"}:
        city = ""
    return (city or None), day


def profile_question(prompt: str) -> str | None:
    normalized = "".join(
        c for c in unicodedata.normalize("NFKD", prompt.casefold()) if not unicodedata.combining(c)
    )
    if re.search(r"\b(?:qual|sabe|lembra)\b.*\b(?:meu nome|como me chamo)\b", normalized):
        return "name"
    if "como eu me chamo" in normalized or "como me chamo" in normalized:
        return "name"
    if "quem sou eu" in normalized or "sabe quem eu sou" in normalized:
        return "name"
    if re.search(r"\b(?:qual|sabe|lembra)\b.*\b(?:minha cidade|onde moro)\b", normalized):
        return "home_city"
    return None


def forget_request(prompt: str) -> str | None:
    normalized = "".join(
        c for c in unicodedata.normalize("NFKD", prompt.casefold()) if not unicodedata.combining(c)
    )
    if not re.search(r"\b(?:esqueca|apague|remova)\b", normalized):
        return None
    if "meu nome" in normalized:
        return "name"
    if "minha cidade" in normalized or "onde moro" in normalized:
        return "home_city"
    return None


def simple_profile_reply(prompt: str, key: str) -> str | None:
    """Accept a short answer only while Core is waiting for this specific fact."""
    value = _clean(prompt)
    if key == "name":
        value = re.sub(r"^(?:eu sou|sou)\s+", "", value, flags=re.IGNORECASE)
    elif key == "home_city":
        value = re.sub(r"^em\s+", "", value, flags=re.IGNORECASE)
    else:
        return None
    if not 1 <= len(value) <= 80 or len(value.split()) > 6 or "?" in prompt:
        return None
    if re.search(
        r"\b(?:nao sei|não sei|qual|como|que|quem|onde|horas|são|pode|"
        r"abre|abrir|previsao|previsão|tempo|cancela|esquece|preciso|"
        r"quero|jarvis|amanha|amanhã)\b",
        value,
        re.IGNORECASE,
    ):
        return None
    if key == "name" and not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' -]*", value):
        return None
    if key == "home_city" and not re.fullmatch(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ', .-]*", value):
        return None
    return value
