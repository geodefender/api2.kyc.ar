from kyc_platform.persistence.base import DocumentRepository
from kyc_platform.persistence.sqlite_repository import SQLiteDocumentRepository
from kyc_platform.shared.config import config


def get_repository() -> DocumentRepository:
    return SQLiteDocumentRepository()


__all__ = ["DocumentRepository", "SQLiteDocumentRepository", "get_repository"]
