from kyc_platform.queue.base import EventQueue
from kyc_platform.queue.mock_queue import MockQueue
from kyc_platform.queue.sqs_queue import SQSQueue
from kyc_platform.shared.config import config, Environment


def get_queue() -> EventQueue:
    if config.is_local():
        return MockQueue()
    return SQSQueue()


__all__ = ["EventQueue", "MockQueue", "SQSQueue", "get_queue"]
