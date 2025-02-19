import logging.config
import tomllib
from pathlib import Path

try:
    from ews_fem_pipeline._version import __version__, __version_tuple__
except ImportError:
    __version__ = version = '0.0.0'
    __version_tuple__ = version_tuple = (0, 0, 0, '', '')


# Setup for logging
class MaxLevelFilter(logging.Filter):
    def __init__(self, level):
        self.maximum_level = getattr(logging, level)

    def filter(self, record):
        return record.levelno <= self.maximum_level


with open(Path(__file__).parent / "logging_config.toml", 'rb') as f:
    logging.config.dictConfig(tomllib.load(f))
