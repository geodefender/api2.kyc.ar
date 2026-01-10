import uuid
import time


def generate_document_id() -> str:
    timestamp = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    return f"doc_{timestamp}_{unique}"


def generate_verification_id() -> str:
    timestamp = int(time.time() * 1000)
    unique = uuid.uuid4().hex[:8]
    return f"ver_{timestamp}_{unique}"
