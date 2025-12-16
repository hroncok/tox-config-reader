"""Tests for tox_config_reader.raw module."""

import json
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
)


# Path to the configs test fixtures directory
CONFIGS_DIR = Path(__file__).parent / "configs"


def discover_config_fixtures():
    """Discover all config fixture directories."""
    fixtures = []
    for config_dir in sorted(CONFIGS_DIR.iterdir()):
        if config_dir.is_dir():
            expected_json = config_dir / "expected.json"
            if expected_json.exists():
                fixtures.append(config_dir)
    return fixtures


def get_fixture_ids():
    """Get test IDs for parametrized fixtures."""
    return [d.name for d in discover_config_fixtures()]


# Parametrized test for all config fixtures
@pytest.mark.parametrize(
    "config_dir", discover_config_fixtures(), ids=get_fixture_ids()
)
class TestConfigFixtures:
    def test_read_config_matches_expected(self, config_dir):
        """Test that read_config returns the expected normalized structure."""
        expected_json = config_dir / "expected.json"
        expected = json.loads(expected_json.read_text())

        config = read_config(config_dir)

        assert config == expected

    def test_find_config_file_succeeds(self, config_dir):
        """Test that find_config_file finds the config in this directory."""
        path, reader_class = find_config_file(config_dir)
        assert path.parent == config_dir


# Inline content for can_read tests (these test specific behaviors, not config parsing)
SETUP_CFG_NO_TOX_CONTENT = """\
[metadata]
name = mypackage
version = 1.0.0
"""

PYPROJECT_NO_TOX_CONTENT = """\
[build-system]
requires = ["flit_core>=3.4"]
build-backend = "flit_core.buildapi"

[project]
name = "mypackage"
"""


class TestToxINIConfigReader:
    def test_can_read_existing_file(self, tmp_path):
        path = tmp_path / "tox.ini"
        path.write_text("[tox]\n")
        assert ToxINIConfigReader.can_read(path) is True

    def test_can_read_nonexistent_file(self, tmp_path):
        assert ToxINIConfigReader.can_read(tmp_path / "tox.ini") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.ini"
        path.write_text("[tox]\n")
        assert ToxINIConfigReader.can_read(path) is False


class TestSetupCfgConfigReader:
    def test_can_read_with_tox_config(self, tmp_path):
        path = tmp_path / "setup.cfg"
        path.write_text("[tox:tox]\n")
        assert SetupCfgConfigReader.can_read(path) is True

    def test_can_read_with_testenv_only(self, tmp_path):
        path = tmp_path / "setup.cfg"
        path.write_text("[testenv]\n")
        assert SetupCfgConfigReader.can_read(path) is True

    def test_can_read_without_tox_config(self, tmp_path):
        path = tmp_path / "setup.cfg"
        path.write_text(SETUP_CFG_NO_TOX_CONTENT)
        assert SetupCfgConfigReader.can_read(path) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert SetupCfgConfigReader.can_read(tmp_path / "setup.cfg") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.cfg"
        path.write_text("[tox:tox]\n")
        assert SetupCfgConfigReader.can_read(path) is False


class TestToxTOMLConfigReader:
    def test_can_read_existing_file(self, tmp_path):
        path = tmp_path / "tox.toml"
        path.write_text('env_list = ["py39"]\n')
        assert ToxTOMLConfigReader.can_read(path) is True

    def test_can_read_nonexistent_file(self, tmp_path):
        assert ToxTOMLConfigReader.can_read(tmp_path / "tox.toml") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.toml"
        path.write_text('env_list = ["py39"]\n')
        assert ToxTOMLConfigReader.can_read(path) is False


class TestPyprojectTOMLConfigReader:
    def test_can_read_native_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text('[tool.tox]\nenv_list = ["py39"]\n')
        assert PyprojectTOMLConfigReader.can_read(path) is True

    def test_can_read_legacy_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text('[tool.tox]\nlegacy_tox_ini = "[tox]"\n')
        assert PyprojectTOMLConfigReader.can_read(path) is False

    def test_can_read_no_tox_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text(PYPROJECT_NO_TOX_CONTENT)
        assert PyprojectTOMLConfigReader.can_read(path) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert PyprojectTOMLConfigReader.can_read(tmp_path / "pyproject.toml") is False

    def test_can_read_wrong_filename(self, tmp_path):
        path = tmp_path / "other.toml"
        path.write_text('[tool.tox]\nenv_list = ["py39"]\n')
        assert PyprojectTOMLConfigReader.can_read(path) is False


class TestPyprojectLegacyINIConfigReader:
    def test_can_read_legacy_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text('[tool.tox]\nlegacy_tox_ini = "[tox]"\n')
        assert PyprojectLegacyINIConfigReader.can_read(path) is True

    def test_can_read_native_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text('[tool.tox]\nenv_list = ["py39"]\n')
        assert PyprojectLegacyINIConfigReader.can_read(path) is False

    def test_can_read_no_tox_config(self, tmp_path):
        path = tmp_path / "pyproject.toml"
        path.write_text(PYPROJECT_NO_TOX_CONTENT)
        assert PyprojectLegacyINIConfigReader.can_read(path) is False

    def test_can_read_nonexistent_file(self, tmp_path):
        assert (
            PyprojectLegacyINIConfigReader.can_read(tmp_path / "pyproject.toml")
            is False
        )


class TestFindConfigFile:
    def test_raises_when_no_config(self, tmp_path):
        with pytest.raises(FileNotFoundError) as exc_info:
            find_config_file(tmp_path)
        assert "No tox configuration file found" in str(exc_info.value)
        assert str(tmp_path) in str(exc_info.value)

    def test_raises_when_no_config_with_unrelated_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text(PYPROJECT_NO_TOX_CONTENT)
        with pytest.raises(FileNotFoundError):
            find_config_file(tmp_path)

    def test_raises_when_no_config_with_unrelated_setup_cfg(self, tmp_path):
        (tmp_path / "setup.cfg").write_text(SETUP_CFG_NO_TOX_CONTENT)
        with pytest.raises(FileNotFoundError):
            find_config_file(tmp_path)


class TestConfigPriority:
    def test_tox_ini_over_setup_cfg(self, tmp_path):
        """tox.ini takes priority over setup.cfg."""
        (tmp_path / "tox.ini").write_text("[tox]\n")
        (tmp_path / "setup.cfg").write_text("[tox:tox]\n")

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "tox.ini"
        assert reader_class is ToxINIConfigReader

    def test_setup_cfg_over_pyproject(self, tmp_path):
        """setup.cfg takes priority over pyproject.toml."""
        (tmp_path / "setup.cfg").write_text("[tox:tox]\n")
        (tmp_path / "pyproject.toml").write_text('[tool.tox]\nenv_list = ["py39"]\n')

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "setup.cfg"
        assert reader_class is SetupCfgConfigReader

    def test_pyproject_over_tox_toml(self, tmp_path):
        """pyproject.toml takes priority over tox.toml."""
        (tmp_path / "pyproject.toml").write_text('[tool.tox]\nenv_list = ["py39"]\n')
        (tmp_path / "tox.toml").write_text('env_list = ["py39"]\n')

        path, reader_class = find_config_file(tmp_path)
        assert path.name == "pyproject.toml"

    def test_pyproject_legacy_over_native(self, tmp_path):
        """legacy_tox_ini takes priority over native pyproject.toml format."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.tox]\nlegacy_tox_ini = "[tox]"\n'
        )

        path, reader_class = find_config_file(tmp_path)
        assert reader_class is PyprojectLegacyINIConfigReader


class TestReadConfig:
    def test_raises_when_no_config(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            read_config(tmp_path)
