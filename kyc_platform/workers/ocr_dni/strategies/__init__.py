from kyc_platform.workers.ocr_dni.strategies.base import DNIOCRStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_nuevo import DNINuevoStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_viejo import DNIViejoStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_new_front import DNINewFrontStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_new_back import DNINewBackStrategy
from kyc_platform.workers.ocr_dni.strategies.dni_old import DNIOldStrategy

__all__ = [
    "DNIOCRStrategy",
    "DNINuevoStrategy",
    "DNIViejoStrategy",
    "DNINewFrontStrategy",
    "DNINewBackStrategy",
    "DNIOldStrategy",
]
