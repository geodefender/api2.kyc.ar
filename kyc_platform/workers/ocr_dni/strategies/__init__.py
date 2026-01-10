from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_nuevo import DNINuevoStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_viejo import DNIViejoStrategy

__all__ = ["DNIOCRStrategy", "DNINuevoStrategy", "DNIViejoStrategy"]
