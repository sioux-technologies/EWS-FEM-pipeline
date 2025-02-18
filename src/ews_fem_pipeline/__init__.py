import tomllib
import logging.config
from pathlib import Path


# Setup for logging
class MaxLevelFilter(logging.Filter):
    def __init__(self, level):
        self.maximum_level = getattr(logging, level)

    def filter(self, record):
        return record.levelno <= self.maximum_level


with open(Path(__file__).parent / "logging_config.toml", 'rb') as f:
    logging.config.dictConfig(tomllib.load(f))
