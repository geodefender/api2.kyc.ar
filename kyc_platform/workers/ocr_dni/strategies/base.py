from abc import ABC, abstractmethod
from typing import Any
from PIL import Image


class DNIOCRStrategy(ABC):
    @abstractmethod
    def extract(self, image: Image.Image) -> dict[str, Any]:
        pass
    
    @abstractmethod
    def get_confidence(self) -> float:
        pass
