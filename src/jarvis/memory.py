"""Structured catalog, ephemeral context and hybrid long-term memory."""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jarvis.config import Project, Settings

MEMORY_TYPES = {
    "fact",
    "preference",
    "decision",
    "meeting",
    "document",
    "note",
    "person",
    "machine",
    "routine",
    "event",
}
INDEX = "jarvis-memory-v1"
PIPELINE = "jarvis-memory-rrf"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"


@dataclass(frozen=True)
class MemoryHit:
    id: str
    kind: str
    content: str
    project: str | None
    created_at: str


class Catalog:
    """PostgreSQL is the authority for registered app, project and script aliases."""

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("Instale o extra de memória: pip install -e '.[memory]'.") from exc
        self.psycopg = psycopg
        self.dsn = dsn

    def init(self) -> None:
        with self.psycopg.connect(self.dsn) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS catalog (
                    kind TEXT NOT NULL CHECK (kind IN ('app', 'project', 'script')),
                    name TEXT NOT NULL,
                    path TEXT NOT NULL,
                    compose_file TEXT,
                    PRIMARY KEY (kind, name)
                )
            """)

    def upsert(self, kind: str, name: str, path: str, compose_file: str | None = None) -> None:
        if kind not in {"app", "project", "script"} or not name.strip() or not path.strip():
            raise ValueError("Tipo, nome ou caminho inválido para o catálogo.")
        with self.psycopg.connect(self.dsn) as conn:
            conn.execute(
                """
                INSERT INTO catalog (kind, name, path, compose_file)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (kind, name) DO UPDATE
                SET path = EXCLUDED.path, compose_file = EXCLUDED.compose_file
            """,
                (kind, name.strip(), path.strip(), compose_file),
            )

    def list(self) -> list[tuple[str, str, str, str | None]]:
        with self.psycopg.connect(self.dsn) as conn:
            return list(
                conn.execute(
                    "SELECT kind, name, path, compose_file FROM catalog ORDER BY kind, name"
                ).fetchall()
            )

    def delete(self, kind: str, name: str) -> bool:
        if kind not in {"app", "project", "script"}:
            raise ValueError("Tipo de catálogo inválido.")
        with self.psycopg.connect(self.dsn) as conn:
            return (
                conn.execute(
                    "DELETE FROM catalog WHERE kind = %s AND name = %s", (kind, name)
                ).rowcount
                > 0
            )

    def overlay(self, settings: Settings) -> Settings:
        apps: dict[str, Path] = {}
        projects: dict[str, Project] = {}
        scripts: dict[str, Path] = {}
        for kind, name, path, compose_file in self.list():
            if kind == "app":
                apps[name] = Path(path)
            elif kind == "project":
                projects[name] = Project(Path(path), compose_file)
            else:
                scripts[name] = Path(path)
        return replace(settings, apps=apps, projects=projects, scripts=scripts)


class ShortMemory:
    """Last turns for one local user; Redis expires them after a day."""

    def __init__(self, url: str) -> None:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Instale o extra de memória: pip install -e '.[memory]'.") from exc
        self.client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=3)
        self.key = "jarvis:recent:local"

    def append(self, prompt: str, answer: str) -> None:
        entry = json.dumps({"prompt": prompt[:1000], "answer": answer[:1000]}, ensure_ascii=False)
        with self.client.pipeline() as pipe:
            pipe.lpush(self.key, entry)
            pipe.ltrim(self.key, 0, 9)
            pipe.expire(self.key, 86400)
            pipe.execute()

    def recent(self) -> list[dict[str, str]]:
        return [json.loads(item) for item in self.client.lrange(self.key, 0, 4)]


class LongMemory:
    """OpenSearch hybrid BM25 + vector retrieval with a local multilingual embedding."""

    def __init__(self, url: str) -> None:
        try:
            from opensearchpy import OpenSearch
        except ImportError as exc:
            raise RuntimeError("Instale o extra de memória: pip install -e '.[memory]'.") from exc
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("JARVIS_OPENSEARCH_URL deve ser uma URL HTTP(S) válida.")
        auth = None
        if os.environ.get("JARVIS_OPENSEARCH_USER"):
            auth = (
                os.environ["JARVIS_OPENSEARCH_USER"],
                os.environ.get("JARVIS_OPENSEARCH_PASSWORD", ""),
            )
        self.client = OpenSearch(
            hosts=[url],
            http_auth=auth,
            use_ssl=parsed.scheme == "https",
            verify_certs=True,
            timeout=10,
        )
        self.model: Any = None

    def init(self) -> None:
        if not self.client.indices.exists(index=INDEX):
            self.client.indices.create(
                index=INDEX,
                body={
                    "settings": {"index": {"knn": True}},
                    "mappings": {
                        "properties": {
                            "kind": {"type": "keyword"},
                            "project": {"type": "keyword"},
                            "content": {"type": "text"},
                            "created_at": {"type": "date"},
                            "vector": {
                                "type": "knn_vector",
                                "dimension": 384,
                                "method": {
                                    "name": "hnsw",
                                    "engine": "lucene",
                                    "space_type": "cosinesimil",
                                },
                            },
                        }
                    },
                },
            )
        self.client.transport.perform_request(
            "PUT",
            f"/_search/pipeline/{PIPELINE}",
            body={
                "description": "JARVIS hybrid memory search",
                "phase_results_processors": [
                    {"score-ranker-processor": {"combination": {"technique": "rrf"}}}
                ],
            },
        )

    def _vector(self, text: str, prefix: str) -> list[float]:
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "Instale o extra de memória: pip install -e '.[memory]'."
                ) from exc
            try:
                self.model = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True)
            except OSError:
                self.model = SentenceTransformer(EMBEDDING_MODEL)
        vector = self.model.encode([f"{prefix}: {text}"], normalize_embeddings=True)[0]
        values = vector.tolist()
        if len(values) != 384:
            raise ValueError("O modelo de embeddings não produziu 384 dimensões.")
        return values

    def add(self, kind: str, content: str, project: str | None = None) -> str:
        if kind not in MEMORY_TYPES or not content.strip() or len(content) > 4000:
            raise ValueError("Tipo ou conteúdo de memória inválido (máximo: 4000 caracteres).")
        identity = str(uuid.uuid4())
        self.client.index(
            index=INDEX,
            id=identity,
            refresh=True,
            body={
                "kind": kind,
                "content": content.strip(),
                "project": project,
                "created_at": datetime.now(UTC).isoformat(),
                "vector": self._vector(content, "passage"),
            },
        )
        return identity

    def search(self, query: str, project: str | None = None, limit: int = 5) -> list[MemoryHit]:
        if not query.strip():
            return []
        if not 1 <= limit <= 10:
            raise ValueError("Limite de busca inválido.")
        lexical: dict[str, Any] = {"match": {"content": query}}
        semantic: dict[str, Any] = {
            "knn": {"vector": {"vector": self._vector(query, "query"), "k": limit * 2}}
        }
        if project:
            # Apply the project filter to both clauses so neither can leak another project's data.
            filter_clause = {"term": {"project": project}}
            lexical = {"bool": {"must": [lexical], "filter": [filter_clause]}}
            semantic["knn"]["vector"]["filter"] = filter_clause
        response = self.client.search(
            index=INDEX,
            params={"search_pipeline": PIPELINE},
            body={
                "size": limit,
                "_source": {"excludes": ["vector"]},
                "query": {"hybrid": {"queries": [lexical, semantic]}},
            },
        )
        return [
            MemoryHit(
                id=hit["_id"],
                kind=hit["_source"]["kind"],
                content=hit["_source"]["content"],
                project=hit["_source"].get("project"),
                created_at=hit["_source"]["created_at"],
            )
            for hit in response["hits"]["hits"]
        ]

    def delete(self, identity: str) -> None:
        if not re.fullmatch(r"[0-9a-f-]{36}", identity):
            raise ValueError("ID de memória inválido.")
        self.client.delete(index=INDEX, id=identity, refresh=True)


class MemoryWorker:
    """Promote only explicit 'remember' statements to durable memory."""

    def __init__(self, long_memory: LongMemory) -> None:
        self.long_memory = long_memory

    def capture_explicit(self, prompt: str) -> str | None:
        match = re.match(r"^\s*(?:jarvis[, ]+)?(?:lembre|lembra) que\s+(.+)$", prompt, re.I)
        if match:
            content = match.group(1).strip()
            kind = "preference" if re.match(r"sempre que eu\b", content, re.I) else "fact"
        else:
            preference = re.match(
                r"^\s*(?:jarvis[, ]+)?(sempre que eu (?:falar|disser)\b.+)$",
                prompt,
                re.I,
            )
            if not preference:
                return None
            content = preference.group(1).strip()
            kind = "preference"
        if not content or len(content) > 4000:
            raise ValueError("Memória vazia ou longa demais.")
        return self.long_memory.add(kind, content)


def catalog_from_env() -> Catalog | None:
    dsn = os.environ.get("JARVIS_DATABASE_URL")
    return Catalog(dsn) if dsn else None


def short_from_env() -> ShortMemory | None:
    url = os.environ.get("JARVIS_REDIS_URL")
    return ShortMemory(url) if url else None


def long_from_env() -> LongMemory | None:
    url = os.environ.get("JARVIS_OPENSEARCH_URL")
    return LongMemory(url) if url else None
