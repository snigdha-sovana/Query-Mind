"""F1 schema linking via lexical overlap (offline, deterministic)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import chromadb

from querymind.config import SCHEMA_TOP_K
from querymind.engine.catalog import SchemaCatalog, TableInfo, load_catalog

_STOP = {
    "a",
    "an",
    "the",
    "of",
    "and",
    "or",
    "in",
    "on",
    "for",
    "to",
    "from",
    "with",
    "what",
    "which",
    "who",
    "how",
    "many",
    "much",
    "is",
    "are",
    "was",
    "were",
    "do",
    "does",
    "did",
    "that",
    "this",
    "these",
    "those",
    "by",
    "at",
    "as",
    "be",
    "it",
    "its",
}


@dataclass
class LinkedSchema:
    tables: list[str]
    scores: dict[str, float]
    schema_text: str


class SchemaLinker:
    def __init__(
        self,
        db_path: str,
        description_dir: str | Path | None = None,
        description_json: str | Path | None = None,
        top_k: int | None = None,
        catalog: SchemaCatalog | None = None,
    ):
        self.db_path = db_path
        self.catalog = catalog or load_catalog(
            db_path, description_dir=description_dir, description_json=description_json
        )
        self.top_k = SCHEMA_TOP_K if top_k is None else top_k
        
        # Initialize ChromaDB in-memory client
        self.chroma_client = chromadb.Client()
        self.collection = self.chroma_client.get_or_create_collection(name="schema_tables")
        self._index_catalog()

    def _index_catalog(self):
        if self.collection.count() > 0:
            return
            
        docs = []
        ids = []
        for name, table in self.catalog.tables.items():
            docs.append(table.text_blob())
            ids.append(name)
            
        if docs:
            self.collection.add(documents=docs, ids=ids)

    def _sample_distinct_values(self) -> dict[str, set[str]]:
        if hasattr(self, "_value_index"):
            return self._value_index
        value_index: dict[str, set[str]] = {}
        try:
            from querymind.engine.db import DBExecutor
            executor = DBExecutor(self.db_path)
            for name, table in self.catalog.tables.items():
                table_values: set[str] = set()
                for col in table.columns:
                    if col.declared_type.upper() in {"TEXT", "VARCHAR", "CHAR", ""}:
                        success, rows = executor.execute(
                            f'SELECT DISTINCT "{col.name}" FROM "{name}" WHERE "{col.name}" IS NOT NULL LIMIT 5'
                        )
                        if success and rows:
                            for row in rows:
                                val = str(list(dict(row).values())[0]).lower()
                                table_values.update(_tokenize(val))
                value_index[name] = table_values
        except Exception:
            pass
        self._value_index = value_index
        return value_index

    def link(self, question: str) -> LinkedSchema:
        # 1. Lexical Scoring
        lexical_scores = {
            name: _score_table(question, table) for name, table in self.catalog.tables.items()
        }
        
        # 2. Embedding Scoring
        semantic_scores = {}
        if self.collection.count() > 0:
            k = min(len(self.catalog.tables), 20)
            if k > 0:
                results = self.collection.query(query_texts=[question], n_results=k)
                if results["distances"] and results["ids"]:
                    for dist, t_id in zip(results["distances"][0], results["ids"][0]):
                        semantic_scores[t_id] = 1.0 / (1.0 + dist)
        
        # 3. Value Match Bonus
        value_index = self._sample_distinct_values()
        q_tokens = _tokenize(question)
        value_scores = {}
        for name, values in value_index.items():
            overlap = q_tokens & values
            if overlap:
                value_scores[name] = 3.0 * len(overlap)

        # 4. Hybrid Scoring
        combined_scores = {}
        for name in self.catalog.tables:
            l_score = lexical_scores.get(name, 0.0)
            s_score = semantic_scores.get(name, 0.0)
            v_score = value_scores.get(name, 0.0)
            combined_scores[name] = l_score + (s_score * 5.0) + v_score
            
        ranked = sorted(combined_scores.items(), key=lambda item: item[1], reverse=True)
        selected: list[str] = []
        for name, score in ranked:
            if score > 0 and len(selected) < self.top_k:
                selected.append(name)
        if not selected:
            selected = [name for name, _ in ranked[: self.top_k]]
            
        return LinkedSchema(
            tables=selected,
            scores=combined_scores,
            schema_text=self.catalog.render(selected),
        )

    def get_schema(self, question: str) -> str:
        return self.link(question).schema_text

    def recall(self, question: str, gold_tables: list[str]) -> float:
        linked = set(name.lower() for name in self.link(question).tables)
        gold = {name.lower() for name in gold_tables}
        if not gold:
            return 1.0
        return len(linked & gold) / len(gold)


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9]+", (text or "").lower()))
    expanded = set(tokens)
    for token in list(tokens):
        expanded.update(token.split("_"))
    return {t for t in expanded if t and t not in _STOP and len(t) > 1}


def _score_table(question: str, table: TableInfo) -> float:
    q = _tokenize(question)
    blob = _tokenize(table.text_blob())
    overlap = q & blob
    name_hit = 2.0 if table.name.lower() in q or table.name.lower().replace("_", "") in q else 0.0
    return name_hit + float(len(overlap))
