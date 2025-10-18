import logging
from dataclasses import dataclass
from functools import wraps


@dataclass
class Utils:
    @staticmethod
    def __set_logger():
        logger = logging.getLogger(__class__.__name__)
        logger.setLevel(logging.DEBUG)

        if not logger.handlers:
            stream_handler = logging.StreamHandler()
            stream_handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            stream_handler.setFormatter(formatter)

            logger.addHandler(stream_handler)

        return logger


class Decorators:
    def __init__(self):
        self.logger = Utils.__set_logger()

    def log_query(func):
        """Decorator for logging SQL queries"""

        @wraps
        def wrapper(self, query, *args, **kwargs):
            self.logger.debug(f"Executing query: {query}")
            return func(self, query, *args, **kwargs)

        return wrapper
