# tools/analysis/oracle/knowledge_oracle.py
#
# Shared knowledge overlay - wraps knowledge.db, which holds
# knowledge_artifacts and semantic_summaries for all corpora.
#
# Separate from corpus DBs so findings survive corpus rebuilds and are
# visible across all corpus Assessors. See DESIGN.md section 7.

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


class KnowledgeOracle:
    """
    Thin wrapper around knowledge.db. Owns schema creation for the two
    intent tables. Passed to Assessor as an optional second connection;
    None means no persistent knowledge store (tests, one-off scripts).
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        from determined.intent.knowledge_artifact import ensure_knowledge_artifacts_table
        from determined.intent.semantic_summary import ensure_semantic_summaries_table
        from determined.intent.workflow_store import ensure_workflow_items_table
        cursor = self.conn.cursor()
        ensure_knowledge_artifacts_table(cursor)
        ensure_semantic_summaries_table(cursor)
        ensure_workflow_items_table(cursor)
        self.conn.commit()

    @classmethod
    def alongside(cls, corpus_db_path: str) -> "KnowledgeOracle":
        """Open knowledge.db in the same directory as the given corpus DB."""
        directory = os.path.dirname(os.path.abspath(corpus_db_path))
        knowledge_path = os.path.join(directory, "knowledge.db")
        return cls(knowledge_path)
