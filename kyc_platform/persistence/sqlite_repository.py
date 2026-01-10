import json
import os
import sqlite3
from typing import Optional

from kyc_platform.contracts.models import DocumentRecord, DocumentStatus
from kyc_platform.persistence.base import DocumentRepository
from kyc_platform.shared.config import config, DocumentType
from kyc_platform.shared.logging import get_logger

logger = get_logger(__name__)


class SQLiteDocumentRepository(DocumentRepository):
    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or config.SQLITE_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    verification_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    document_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    image_ref TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    extracted_data TEXT,
                    confidence REAL,
                    processing_time_ms INTEGER,
                    errors TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_verification_id ON documents(verification_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_status ON documents(status)
            """)
            conn.commit()
    
    def _row_to_record(self, row: sqlite3.Row) -> DocumentRecord:
        return DocumentRecord(
            document_id=row["document_id"],
            verification_id=row["verification_id"],
            client_id=row["client_id"],
            document_type=DocumentType(row["document_type"]),
            status=DocumentStatus(row["status"]),
            image_ref=row["image_ref"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            extracted_data=json.loads(row["extracted_data"]) if row["extracted_data"] else None,
            confidence=row["confidence"],
            processing_time_ms=row["processing_time_ms"],
            errors=json.loads(row["errors"]) if row["errors"] else None,
        )
    
    def save(self, record: DocumentRecord) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO documents 
                    (document_id, verification_id, client_id, document_type, status, 
                     image_ref, created_at, updated_at, extracted_data, confidence, 
                     processing_time_ms, errors)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.document_id,
                        record.verification_id,
                        record.client_id,
                        record.document_type.value,
                        record.status.value,
                        record.image_ref,
                        record.created_at,
                        record.updated_at,
                        json.dumps(record.extracted_data) if record.extracted_data else None,
                        record.confidence,
                        record.processing_time_ms,
                        json.dumps(record.errors) if record.errors else None,
                    ),
                )
                conn.commit()
            logger.info(f"Saved document record", extra={"document_id": record.document_id})
            return True
        except Exception as e:
            logger.error(f"Failed to save document: {e}")
            return False
    
    def get_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            return self._row_to_record(row) if row else None
    
    def get_by_verification_id(self, verification_id: str) -> list[DocumentRecord]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents WHERE verification_id = ?",
                (verification_id,),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]
    
    def update(self, record: DocumentRecord) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE documents SET
                        verification_id = ?,
                        client_id = ?,
                        document_type = ?,
                        status = ?,
                        image_ref = ?,
                        updated_at = ?,
                        extracted_data = ?,
                        confidence = ?,
                        processing_time_ms = ?,
                        errors = ?
                    WHERE document_id = ?
                    """,
                    (
                        record.verification_id,
                        record.client_id,
                        record.document_type.value,
                        record.status.value,
                        record.image_ref,
                        record.updated_at,
                        json.dumps(record.extracted_data) if record.extracted_data else None,
                        record.confidence,
                        record.processing_time_ms,
                        json.dumps(record.errors) if record.errors else None,
                        record.document_id,
                    ),
                )
                conn.commit()
            logger.info(f"Updated document record", extra={"document_id": record.document_id})
            return True
        except Exception as e:
            logger.error(f"Failed to update document: {e}")
            return False
    
    def delete(self, document_id: str) -> bool:
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete document: {e}")
            return False
    
    def list_all(self, limit: int = 100, offset: int = 0) -> list[DocumentRecord]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [self._row_to_record(row) for row in rows]
