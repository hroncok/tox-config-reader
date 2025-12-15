"""
Raw configuration readers for tox configuration files.

Supports the following formats (in priority order):
1. tox.ini (INI)
2. setup.cfg (INI)
3. pyproject.toml with legacy_tox_ini key (INI embedded in TOML)
4. pyproject.toml native under tool.tox (TOML)
5. tox.toml (TOML)

See: https://tox.wiki/en/stable/config.html#discovery-and-file-types
"""

from __future__ import annotations

import configparser
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    import tomllib as tomli
else:
    import tomli

if TYPE_CHECKING:
    from typing import Any


class BaseConfigReader(ABC):
    """Abstract base class for tox configuration readers."""

    def __init__(self, path: Path) -> None:
        """
        Initialize the reader with a path to the configuration file.

        Args:
            path: Path to the configuration file.
        """
        self.path = path

    @abstractmethod
    def read(self) -> dict[str, Any]:
        """
        Read the configuration and return it as a dictionary.

        Returns:
            Dictionary containing the parsed configuration.
        """
        ...

    @classmethod
    @abstractmethod
    def can_read(cls, path: Path) -> bool:
        """
        Check if this reader can handle the given file.

        Args:
            path: Path to check.

        Returns:
            True if this reader can handle the file.
        """
        ...


class INIConfigReader(BaseConfigReader):
    """Base reader for INI-based tox configuration."""

    #: Section name for core tox settings
    core_section: str = "tox"
    #: Prefix for environment sections (e.g., "testenv" -> "testenv:py39")
    env_section_prefix: str = "testenv"

    def _parse_ini(self, content: str) -> dict[str, Any]:
        """
        Parse INI content into a dictionary.

        Args:
            content: INI formatted string.

        Returns:
            Dictionary with parsed configuration.
        """
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(content)

        result: dict[str, Any] = {}

        for section in parser.sections():
            result[section] = dict(parser[section])

        return result

    def read(self) -> dict[str, Any]:
        """Read and parse the INI configuration file."""
        content = self.path.read_text(encoding="utf-8")
        return self._parse_ini(content)

    @classmethod
    def can_read(cls, path: Path) -> bool:
        """Check if the file exists."""
        return path.is_file()


class TOMLConfigReader(BaseConfigReader):
    """Base reader for TOML-based tox configuration."""

    #: Key path to extract from TOML (e.g., ["tool", "tox"] for pyproject.toml)
    key_path: list[str] = []

    def _parse_toml(self, content: str) -> dict[str, Any]:
        """
        Parse TOML content into a dictionary.

        Args:
            content: TOML formatted string.

        Returns:
            Dictionary with parsed configuration.
        """
        return tomli.loads(content)

    def _extract_tox_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Extract tox configuration from parsed TOML data.

        Args:
            data: Full parsed TOML data.

        Returns:
            Dictionary containing only tox configuration.
        """
        result = data
        for key in self.key_path:
            result = result.get(key, {})
        return result

    def read(self) -> dict[str, Any]:
        """Read and parse the TOML configuration file."""
        content = self.path.read_text(encoding="utf-8")
        data = self._parse_toml(content)
        return self._extract_tox_config(data)

    @classmethod
    def can_read(cls, path: Path) -> bool:
        """Check if the file exists."""
        return path.is_file()


class ToxINIConfigReader(INIConfigReader):
    """
    Reader for tox.ini files.

    Uses standard INI format with [tox] for core settings
    and [testenv:name] for environments.
    """

    @classmethod
    def can_read(cls, path: Path) -> bool:
        return path.name == "tox.ini" and path.is_file()


class SetupCfgConfigReader(INIConfigReader):
    """
    Reader for setup.cfg files with tox configuration.

    Uses [tox:tox] for core settings (instead of [tox])
    and [testenv:name] for environments.
    """

    core_section = "tox:tox"

    @classmethod
    def can_read(cls, path: Path) -> bool:
        if path.name != "setup.cfg" or not path.is_file():
            return False
        # Check if the file contains tox configuration
        content = path.read_text(encoding="utf-8")
        return "[tox:tox]" in content or "[testenv]" in content


class ToxTOMLConfigReader(TOMLConfigReader):
    """
    Reader for tox.toml files.

    Native TOML format without any prefix - configuration is at the root level.
    """

    key_path = []

    @classmethod
    def can_read(cls, path: Path) -> bool:
        return path.name == "tox.toml" and path.is_file()


class PyprojectTOMLConfigReader(TOMLConfigReader):
    """
    Reader for pyproject.toml with native tox configuration.

    Configuration is under [tool.tox] table.
    """

    key_path = ["tool", "tox"]

    @classmethod
    def can_read(cls, path: Path) -> bool:
        if path.name != "pyproject.toml" or not path.is_file():
            return False
        # Check it's native TOML (not legacy INI)
        content = path.read_text(encoding="utf-8")
        data = tomli.loads(content)
        tool_tox = data.get("tool", {}).get("tox", {})
        # If it has legacy_tox_ini, it's not native
        return bool(tool_tox) and "legacy_tox_ini" not in tool_tox


class PyprojectLegacyINIConfigReader(BaseConfigReader):
    """
    Reader for pyproject.toml with legacy_tox_ini key.

    The tox configuration is stored as an INI string inside
    the [tool.tox] legacy_tox_ini key.
    """

    def read(self) -> dict[str, Any]:
        """Read TOML file and parse the embedded INI configuration."""
        content = self.path.read_text(encoding="utf-8")
        data = tomli.loads(content)
        ini_content = data.get("tool", {}).get("tox", {}).get("legacy_tox_ini", "")

        # Parse the INI content
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(ini_content)

        result: dict[str, Any] = {}
        for section in parser.sections():
            result[section] = dict(parser[section])

        return result

    @classmethod
    def can_read(cls, path: Path) -> bool:
        if path.name != "pyproject.toml" or not path.is_file():
            return False
        content = path.read_text(encoding="utf-8")
        data = tomli.loads(content)
        tool_tox = data.get("tool", {}).get("tox", {})
        return "legacy_tox_ini" in tool_tox


# Configuration file discovery order (highest priority first)
# See: https://tox.wiki/en/stable/config.html#discovery-and-file-types
CONFIG_READERS: dict[str, list[type[BaseConfigReader]]] = {
    "tox.ini": [ToxINIConfigReader],
    "setup.cfg": [SetupCfgConfigReader],
    "pyproject.toml": [PyprojectLegacyINIConfigReader, PyprojectTOMLConfigReader],
    "tox.toml": [ToxTOMLConfigReader],
}


def find_config_file(directory: Path | None = None) -> tuple[Path, type[BaseConfigReader]]:
    """
    Find the tox configuration file in the given directory.

    Searches for configuration files in priority order as defined by tox.

    Args:
        directory: Directory to search in. Defaults to current working directory.

    Returns:
        Tuple of (path, reader_class).

    Raises:
        FileNotFoundError: If no tox configuration file is found.
    """
    if directory is None:
        directory = Path.cwd()

    for filename, reader_classes in CONFIG_READERS.items():
        path = directory / filename
        for reader_class in reader_classes:
            if reader_class.can_read(path):
                return path, reader_class

    raise FileNotFoundError(
        f"No tox configuration file found in {directory}. "
        f"Searched for: {', '.join(CONFIG_READERS.keys())}"
    )


def read_config(directory: Path | None = None) -> dict[str, Any]:
    """
    Read tox configuration from the appropriate file.

    Discovers and reads the tox configuration file from the given directory,
    following the standard tox priority order.

    Args:
        directory: Directory to search in. Defaults to current working directory.

    Returns:
        Dictionary containing the parsed tox configuration.

    Raises:
        FileNotFoundError: If no tox configuration file is found.
    """
    path, reader_class = find_config_file(directory)
    reader = reader_class(path)
    return reader.read()

