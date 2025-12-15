"""Tests for tox_config_reader.raw module."""

import pytest
from pathlib import Path

from tox_config_reader.raw import (
    ToxINIConfigReader,
    SetupCfgConfigReader,
    ToxTOMLConfigReader,
    PyprojectTOMLConfigReader,
    PyprojectLegacyINIConfigReader,
    find_config_file,
    read_config,
    CONFIG_READERS,
)


# Sample configuration contents for fixtures

TOX_INI_CONTENT = """\
[tox]
env_list = py39, py310, py311

[testenv]
deps = pytest
commands = pytest tests
"""

SETUP_CFG_CONTENT = """\
[metadata]
name = mypackage

[tox:tox]
env_list = py39, py310

[testenv]
deps = pytest
commands = pytest
"""

SETUP_CFG_NO_TOX_CONTENT = """\
[metadata]
name = mypackage
version = 1.0.0
"""

TOX_TOML_CONTENT = """\
requires = ["tox>=4.0"]
env_list = ["py39", "py310", "py311"]

[env_run_base]
description = "Run tests"
commands = [["pytest"]]

[env.lint]
description = "Run linters"
deps = ["ruff"]
commands = [["ruff", "check", "."]]
"""

PYPROJECT_NATIVE_CONTENT = """\
[build-system]
requires = ["flit_core>=3.4"]
build-backend = "flit_core.buildapi"

[project]
name = "mypackage"

[tool.tox]
requires = ["tox>=4.0"]
env_list = ["py39", "py310"]

[tool.tox.env_run_base]
deps = ["pytest"]
commands = [["pytest"]]
"""

PYPROJECT_LEGACY_CONTENT = '''\
[build-system]
requires = ["flit_core>=3.4"]
build-backend = "flit_core.buildapi"

[project]
name = "mypackage"

[tool.tox]
legacy_tox_ini = """
[tox]
env_list = py39, py310

[testenv]
deps = pytest
commands = pytest tests
"""
'''

PYPROJECT_NO_TOX_CONTENT = """\
[build-system]
requires = ["flit_core>=3.4"]
build-backend = "flit_core.buildapi"

[project]
name = "mypackage"
"""


# Fixtures for creating config files


@pytest.fixture
def tox_ini(tmp_path):
    """Create a tox.ini file."""
    path = tmp_path / "tox.ini"
    path.write_text(TOX_INI_CONTENT)
    return path


@pytest.fixture
def setup_cfg(tmp_path):
    """Create a setup.cfg file with tox configuration."""
    path = tmp_path / "setup.cfg"
    path.write_text(SETUP_CFG_CONTENT)
    return path


@pytest.fixture
def setup_cfg_no_tox(tmp_path):
    """Create a setup.cfg file without tox configuration."""
    path = tmp_path / "setup.cfg"
    path.write_text(SETUP_CFG_NO_TOX_CONTENT)
    return path


@pytest.fixture
def tox_toml(tmp_path):
    """Create a tox.toml file."""
    path = tmp_path / "tox.toml"
    path.write_text(TOX_TOML_CONTENT)
    return path


@pytest.fixture
def pyproject_native(tmp_path):
    """Create a pyproject.toml with native tox configuration."""
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT_NATIVE_CONTENT)
    return path


@pytest.fixture
def pyproject_legacy(tmp_path):
    """Create a pyproject.toml with legacy_tox_ini."""
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT_LEGACY_CONTENT)
    return path


@pytest.fixture
def pyproject_no_tox(tmp_path):
    """Create a pyproject.toml without tox configuration."""
    path = tmp_path / "pyproject.toml"
    path.write_text(PYPROJECT_NO_TOX_CONTENT)
    return path


class TestToxINIConfigReader:
    def test_can_read_existing_file(self, tox_ini):
        assert ToxINIConfigReader.can_read(tox_ini) is True

    def test_can_read_nonexistent_file(self, tmp_path):
        assert ToxINIConfigReader.can_read(tmp_path / "tox.ini") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.ini"
        path.write_text(TOX_INI_CONTENT)
        assert ToxINIConfigReader.can_read(path) is False

    def test_read(self, tox_ini):
        reader = ToxINIConfigReader(tox_ini)
        config = reader.read()

        assert "tox" in config
        assert config["tox"]["env_list"] == "py39, py310, py311"
        assert "testenv" in config
        assert config["testenv"]["deps"] == "pytest"
        assert config["testenv"]["commands"] == "pytest tests"


class TestSetupCfgConfigReader:
    def test_can_read_with_tox_config(self, setup_cfg):
        assert SetupCfgConfigReader.can_read(setup_cfg) is True

    def test_can_read_without_tox_config(self, setup_cfg_no_tox):
        assert SetupCfgConfigReader.can_read(setup_cfg_no_tox) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert SetupCfgConfigReader.can_read(tmp_path / "setup.cfg") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.cfg"
        path.write_text(SETUP_CFG_CONTENT)
        assert SetupCfgConfigReader.can_read(path) is False

    def test_read(self, setup_cfg):
        reader = SetupCfgConfigReader(setup_cfg)
        config = reader.read()

        assert "tox:tox" in config
        assert config["tox:tox"]["env_list"] == "py39, py310"
        assert "testenv" in config
        assert config["testenv"]["deps"] == "pytest"


class TestToxTOMLConfigReader:
    def test_can_read_existing_file(self, tox_toml):
        assert ToxTOMLConfigReader.can_read(tox_toml) is True

    def test_can_read_nonexistent_file(self, tmp_path):
        assert ToxTOMLConfigReader.can_read(tmp_path / "tox.toml") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.toml"
        path.write_text(TOX_TOML_CONTENT)
        assert ToxTOMLConfigReader.can_read(path) is False

    def test_read(self, tox_toml):
        reader = ToxTOMLConfigReader(tox_toml)
        config = reader.read()

        assert config["requires"] == ["tox>=4.0"]
        assert config["env_list"] == ["py39", "py310", "py311"]
        assert "env_run_base" in config
        assert config["env_run_base"]["commands"] == [["pytest"]]
        assert "env" in config
        assert config["env"]["lint"]["deps"] == ["ruff"]


class TestPyprojectTOMLConfigReader:
    def test_can_read_native_config(self, pyproject_native):
        assert PyprojectTOMLConfigReader.can_read(pyproject_native) is True

    def test_can_read_legacy_config(self, pyproject_legacy):
        # Should return False for legacy (that's handled by PyprojectLegacyINIConfigReader)
        assert PyprojectTOMLConfigReader.can_read(pyproject_legacy) is False

    def test_can_read_no_tox_config(self, pyproject_no_tox):
        assert PyprojectTOMLConfigReader.can_read(pyproject_no_tox) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert PyprojectTOMLConfigReader.can_read(tmp_path / "pyproject.toml") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.toml"
        path.write_text(PYPROJECT_NATIVE_CONTENT)
        assert PyprojectTOMLConfigReader.can_read(path) is False

    def test_read(self, pyproject_native):
        reader = PyprojectTOMLConfigReader(pyproject_native)
        config = reader.read()

        assert config["requires"] == ["tox>=4.0"]
        assert config["env_list"] == ["py39", "py310"]
        assert "env_run_base" in config
        assert config["env_run_base"]["deps"] == ["pytest"]


class TestPyprojectLegacyINIConfigReader:
    def test_can_read_legacy_config(self, pyproject_legacy):
        assert PyprojectLegacyINIConfigReader.can_read(pyproject_legacy) is True

    def test_can_read_native_config(self, pyproject_native):
        # Should return False for native (that's handled by PyprojectTOMLConfigReader)
        assert PyprojectLegacyINIConfigReader.can_read(pyproject_native) is False

    def test_can_read_no_tox_config(self, pyproject_no_tox):
        assert PyprojectLegacyINIConfigReader.can_read(pyproject_no_tox) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert PyprojectLegacyINIConfigReader.can_read(tmp_path / "pyproject.toml") is False

    def test_read(self, pyproject_legacy):
        reader = PyprojectLegacyINIConfigReader(pyproject_legacy)
        config = reader.read()

        assert "tox" in config
        assert config["tox"]["env_list"] == "py39, py310"
        assert "testenv" in config
        assert config["testenv"]["deps"] == "pytest"


class TestFindConfigFile:
    def test_finds_tox_ini(self, tox_ini):
        path, reader_class = find_config_file(tox_ini.parent)
        assert path == tox_ini
        assert reader_class is ToxINIConfigReader

    def test_finds_setup_cfg(self, setup_cfg):
        path, reader_class = find_config_file(setup_cfg.parent)
        assert path == setup_cfg
        assert reader_class is SetupCfgConfigReader

    def test_finds_tox_toml(self, tox_toml):
        path, reader_class = find_config_file(tox_toml.parent)
        assert path == tox_toml
        assert reader_class is ToxTOMLConfigReader

    def test_finds_pyproject_native(self, pyproject_native):
        path, reader_class = find_config_file(pyproject_native.parent)
        assert path == pyproject_native
        assert reader_class is PyprojectTOMLConfigReader

    def test_finds_pyproject_legacy(self, pyproject_legacy):
        path, reader_class = find_config_file(pyproject_legacy.parent)
        assert path == pyproject_legacy
        assert reader_class is PyprojectLegacyINIConfigReader

    def test_raises_when_no_config(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc_info:
            find_config_file(tmp_path)
        assert "No tox configuration file found" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value)

    def test_raises_when_no_config_with_unrelated_pyproject(self, pyproject_no_tox):
        with pytest.raises(FileNotFoundError):
            find_config_file(pyproject_no_tox.parent)

    def test_raises_when_no_config_with_unrelated_setup_cfg(self, setup_cfg_no_tox):
        with pytest.raises(FileNotFoundError):
            find_config_file(setup_cfg_no_tox.parent)


class TestConfigPriority:
    def test_tox_ini_over_setup_cfg(self, tmp_path):
        """tox.ini takes priority over setup.cfg."""
        (tmp_path / "tox.ini").write_text(TOX_INI_CONTENT)
        (tmp_path / "setup.cfg").write_text(SETUP_CFG_CONTENT)

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "tox.ini"
        assert reader_class is ToxINIConfigReader

    def test_setup_cfg_over_pyproject(self, tmp_path):
        """setup.cfg takes priority over pyproject.toml."""
        (tmp_path / "setup.cfg").write_text(SETUP_CFG_CONTENT)
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_NATIVE_CONTENT)

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "setup.cfg"
        assert reader_class is SetupCfgConfigReader

    def test_pyproject_over_tox_toml(self, tmp_path):
        """pyproject.toml takes priority over tox.toml."""
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_NATIVE_CONTENT)
        (tmp_path / "tox.toml").write_text(TOX_TOML_CONTENT)

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "pyproject.toml"

    def test_pyproject_legacy_over_native(self, tmp_path):
        """legacy_tox_ini takes priority over native pyproject.toml format."""
        # This tests the order within pyproject.toml readers
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_LEGACY_CONTENT)

        path, reader_class = find_config_file(tmp_path)
        assert reader_class is PyprojectLegacyINIConfigReader


class TestReadConfig:
    def test_read_tox_ini(self, tox_ini):
        config = read_config(tox_ini.parent)
        assert "tox" in config
        assert "testenv" in config

    def test_read_setup_cfg(self, setup_cfg):
        config = read_config(setup_cfg.parent)
        assert "tox:tox" in config
        assert "testenv" in config

    def test_read_tox_toml(self, tox_toml):
        config = read_config(tox_toml.parent)
        assert "env_list" in config
        assert "env_run_base" in config

    def test_read_pyproject_native(self, pyproject_native):
        config = read_config(pyproject_native.parent)
        assert "env_list" in config
        assert "env_run_base" in config

    def test_read_pyproject_legacy(self, pyproject_legacy):
        config = read_config(pyproject_legacy.parent)
        assert "tox" in config
        assert "testenv" in config

    def test_raises_when_no_config(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_config(tmp_path)

