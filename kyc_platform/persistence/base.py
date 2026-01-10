from abc import ABC, abstractmethod
from typing import Optional

from kyc_platform.contracts.models import DocumentRecord


class DocumentRepository(ABC):
    @abstractmethod
    def save(self, record: DocumentRecord) -> bool:
        pass
    
    @abstractmethod
    def get_by_id(self, document_id: str) -> Optional[DocumentRecord]:
        pass
    
    @abstractmethod
    def get_by_verification_id(self, verification_id: str) -> list[DocumentRecord]:
        pass
    
    @abstractmethod
    def update(self, record: DocumentRecord) -> bool:
        pass
    
    @abstractmethod
    def delete(self, document_id: str) -> bool:
        pass
    
    @abstractmethod
    def list_all(self, limit: int = 100, offset: int = 0) -> list[DocumentRecord]:
        pass
