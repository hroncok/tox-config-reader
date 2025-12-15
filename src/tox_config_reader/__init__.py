"""A tool to read tox configuration."""

__version__ = "0.1.0"

from tox_config_reader.raw import (
    BaseConfigReader,
    INIConfigReader,
    PyprojectLegacyINIConfigReader,
    PyprojectTOMLConfigReader,
    SetupCfgConfigReader,
    TOMLConfigReader,
    ToxINIConfigReader,
    ToxTOMLConfigReader,
    find_config_file,
    read_config,
)
from tox_config_reader.substitutions import (
    substitute_config,
    substitute_string,
    substitute_value,
)

__all__ = [
    "BaseConfigReader",
    "INIConfigReader",
    "TOMLConfigReader",
    "ToxINIConfigReader",
    "SetupCfgConfigReader",
    "ToxTOMLConfigReader",
    "PyprojectTOMLConfigReader",
    "PyprojectLegacyINIConfigReader",
    "find_config_file",
    "read_config",
    "substitute_config",
    "substitute_string",
    "substitute_value",
]

