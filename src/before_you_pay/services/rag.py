"""Lightweight, zero-dependency User Document RAG service using standard SQLite."""

import sqlite3
import sys
from pathlib import Path
from uuid import UUID

from before_you_pay.models import (
    BoundingBox,
    CoordinateUnit,
    DocumentClassification,
    RagEvidenceChunk,
    RagQuery,
)


def _resolve_db_path() -> str:
    """Return a writable SQLite path for the current runtime environment.

    - Windows (local development): keeps the existing ``./data/user_documents.db``
      behaviour, relative to the process working directory.
    - Linux / Vercel serverless: ``/var/task`` is read-only; ``/tmp`` is the
      only writable area.  The database is therefore ephemeral — it is reset
      on each cold-start — which is acceptable for the current RAG store used
      for intra-session cross-document context.
    """
    if sys.platform == "win32":
        return "./data/user_documents.db"
    return "/tmp/data/user_documents.db"


class SqliteRagService:
    """User Document RAG store utilizing SQLite with strict user_id tenant isolation."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path if db_path is not None else _resolve_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_chunks (
                    evidence_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    source_document_id TEXT NOT NULL,
                    source_document_type TEXT NOT NULL,
                    page_number INTEGER NOT NULL,
                    source_text TEXT NOT NULL,
                    box_x REAL,
                    box_y REAL,
                    box_w REAL,
                    box_h REAL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_chunks_user ON user_chunks (user_id)")
            conn.commit()

    async def index_document_chunks(
        self,
        user_id: UUID,
        document_id: UUID,
        chunks: list[RagEvidenceChunk],
    ) -> int:
        """Store chunk text and provenance strictly tagged with user_id."""
        if not chunks:
            return 0

        with self._get_connection() as conn:
            for chunk in chunks:
                box_x = chunk.bounding_box.x if chunk.bounding_box else None
                box_y = chunk.bounding_box.y if chunk.bounding_box else None
                box_w = chunk.bounding_box.width if chunk.bounding_box else None
                box_h = chunk.bounding_box.height if chunk.bounding_box else None

                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_chunks (
                        evidence_id, user_id, source_document_id, source_document_type,
                        page_number, source_text, box_x, box_y, box_w, box_h
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(chunk.evidence_id),
                        str(user_id),
                        str(chunk.source_document_id),
                        chunk.source_document_type.value,
                        chunk.page_number,
                        chunk.source_text,
                        box_x,
                        box_y,
                        box_w,
                        box_h,
                    ),
                )
            conn.commit()
        return len(chunks)

    async def retrieve(
        self,
        query: RagQuery,
    ) -> list[RagEvidenceChunk]:
        """Search historical documents strictly scoped to query.user_id."""
        query_words = set(query.query_text.lower().split())
        if not query_words:
            return []

        sql = "SELECT * FROM user_chunks WHERE user_id = ?"
        params: list = [str(query.user_id)]

        if query.current_document_id:
            sql += " AND source_document_id != ?"
            params.append(str(query.current_document_id))

        if query.document_types:
            placeholders = ",".join("?" for _ in query.document_types)
            sql += f" AND source_document_type IN ({placeholders})"
            params.extend([dt.value for dt in query.document_types])

        with self._get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()

        scored_chunks: list[tuple[float, RagEvidenceChunk]] = []

        for row in rows:
            text_lower = row["source_text"].lower()
            text_words = set(text_lower.split())
            overlap = query_words.intersection(text_words)

            # Compute genuine query term recall score (0.0 to 1.0)
            sim_score = round(len(overlap) / max(len(query_words), 1), 2)

            if sim_score < query.min_similarity:
                continue

            bounding_box = None
            if row["box_x"] is not None:
                bounding_box = BoundingBox(
                    x=row["box_x"],
                    y=row["box_y"],
                    width=row["box_w"],
                    height=row["box_h"],
                    coordinate_unit=CoordinateUnit.NORMALIZED_PERCENTAGE,
                )

            chunk = RagEvidenceChunk(
                evidence_id=UUID(row["evidence_id"]),
                user_id=query.user_id,
                source_document_id=UUID(row["source_document_id"]),
                source_document_type=DocumentClassification(row["source_document_type"]),
                page_number=row["page_number"],
                source_text=row["source_text"],
                bounding_box=bounding_box,
                similarity_score=sim_score,
            )
            scored_chunks.append((sim_score, chunk))

        # Sort by similarity descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored_chunks[: query.top_k]]
