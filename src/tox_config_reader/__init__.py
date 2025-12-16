"""A tool to read tox configuration."""

__version__ = "0.1.0"

from tox_config_reader.raw import find_config_file
from tox_config_reader.raw import read_config
from tox_config_reader.substitutions import substitute_config

__all__ = [
    "find_config_file",
    "read_config",
    "substitute_config",
]
