import sys
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def perform_flaky_task() -> None:
    """Execute task which might fail or not"""
    if random.random() < 0.4:
        logging.info("Task succeeded")
        sys.exit(0)
    logging.error("Task failed")
    sys.exit(1)


if __name__ == "__main__":
    perform_flaky_task()
