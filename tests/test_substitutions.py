"""Tests for tox_config_reader.substitutions module."""

import os

from tox_config_reader.substitutions import (
    substitute_string,
    substitute_value,
    substitute_config,
)


class TestSubstituteString:
    def test_no_substitution(self):
        assert substitute_string("hello world") == "hello world"

    def test_empty_string(self):
        assert substitute_string("") == ""

    def test_pathsep(self):
        result = substitute_string("path1{:}path2")
        assert result == f"path1{os.pathsep}path2"

    def test_sep(self):
        result = substitute_string("src{/}main")
        assert result == f"src{os.sep}main"

    def test_escaped_brace(self):
        result = substitute_string(r"literal \{brace\}")
        assert result == "literal {brace}"

    def test_escaped_colon(self):
        result = substitute_string(r"no\:substitution")
        assert result == "no:substitution"


class TestEnvSubstitution:
    def test_env_existing(self):
        result = substitute_string("{env:TEST_VAR}", environ={"TEST_VAR": "test_value"})
        assert result == "test_value"

    def test_env_nonexistent(self):
        result = substitute_string("{env:NONEXISTENT_VAR}", environ={})
        assert result == ""

    def test_env_with_default(self):
        result = substitute_string("{env:NONEXISTENT_VAR:default_value}", environ={})
        assert result == "default_value"

    def test_env_existing_ignores_default(self):
        result = substitute_string(
            "{env:TEST_VAR:default_value}", environ={"TEST_VAR": "actual_value"}
        )
        assert result == "actual_value"

    def test_env_empty_default(self):
        result = substitute_string("{env:NONEXISTENT_VAR:}", environ={})
        assert result == ""

    def test_env_nested_default(self):
        result = substitute_string(
            "{env:PRIMARY_VAR:{env:FALLBACK_VAR}}",
            environ={"FALLBACK_VAR": "fallback_value"},
        )
        assert result == "fallback_value"

    def test_env_uses_os_environ_by_default(self, monkeypatch):
        """Sanity check that os.environ is used when environ is not specified."""
        monkeypatch.setenv("SANITY_CHECK_VAR", "sanity_value")
        result = substitute_string("{env:SANITY_CHECK_VAR}")
        assert result == "sanity_value"


class TestPosargsSubstitution:
    def test_posargs_provided(self):
        result = substitute_string("{posargs}", posargs=["--verbose", "-x"])
        assert result == "--verbose -x"

    def test_posargs_empty(self):
        result = substitute_string("{posargs}", posargs=[])
        assert result == ""

    def test_posargs_none(self):
        result = substitute_string("{posargs}")
        assert result == ""

    def test_posargs_with_default(self):
        result = substitute_string("{posargs:--default}", posargs=[])
        assert result == "--default"

    def test_posargs_provided_ignores_default(self):
        result = substitute_string("{posargs:--default}", posargs=["--actual"])
        assert result == "--actual"

    def test_posargs_in_command(self):
        result = substitute_string("pytest {posargs}", posargs=["tests/", "-v"])
        assert result == "pytest tests/ -v"


class TestPosargsIndexed:
    """Test TOML-style indexed posargs like {posargs[0]}, {posargs[1:]}."""

    def test_posargs_single_index(self):
        result = substitute_string("{posargs[0]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg1"

    def test_posargs_second_index(self):
        result = substitute_string("{posargs[1]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg2"

    def test_posargs_last_index(self):
        result = substitute_string("{posargs[2]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg3"

    def test_posargs_negative_index(self):
        result = substitute_string("{posargs[-1]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg3"

    def test_posargs_negative_index_second_last(self):
        result = substitute_string("{posargs[-2]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg2"

    def test_posargs_index_out_of_range(self):
        result = substitute_string("{posargs[10]}", posargs=["arg1", "arg2"])
        assert result == ""

    def test_posargs_slice_from(self):
        result = substitute_string("{posargs[1:]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg2 arg3"

    def test_posargs_slice_to(self):
        result = substitute_string("{posargs[:2]}", posargs=["arg1", "arg2", "arg3"])
        assert result == "arg1 arg2"

    def test_posargs_slice_range(self):
        result = substitute_string(
            "{posargs[1:3]}", posargs=["arg1", "arg2", "arg3", "arg4"]
        )
        assert result == "arg2 arg3"

    def test_posargs_slice_empty(self):
        result = substitute_string("{posargs[5:]}", posargs=["arg1", "arg2"])
        assert result == ""

    def test_posargs_index_empty_list(self):
        result = substitute_string("{posargs[0]}", posargs=[])
        assert result == ""

    def test_posargs_index_in_command(self):
        result = substitute_string(
            "python {posargs[0]} --config {posargs[1]}",
            posargs=["script.py", "config.ini", "extra"],
        )
        assert result == "python script.py --config config.ini"

    def test_posargs_invalid_index(self):
        result = substitute_string("{posargs[abc]}", posargs=["arg1"])
        assert result == "{posargs[abc]}"


class TestTtySubstitution:
    def test_tty_on_value(self, monkeypatch):
        # Mock stdin.isatty() to return True
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        result = substitute_string("{tty:--color:--no-color}")
        assert result == "--color"

    def test_tty_off_value(self, monkeypatch):
        # Mock stdin.isatty() to return False
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        result = substitute_string("{tty:--color:--no-color}")
        assert result == "--no-color"

    def test_tty_no_off_value(self, monkeypatch):
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        result = substitute_string("{tty:--pdb}")
        assert result == ""


class TestMultipleSubstitutions:
    def test_multiple_in_one_string(self):
        result = substitute_string(
            "Hello {env:USER}, path is src{/}main", environ={"USER": "testuser"}
        )
        assert result == f"Hello testuser, path is src{os.sep}main"

    def test_adjacent_substitutions(self):
        result = substitute_string("{/}{/}")
        assert result == f"{os.sep}{os.sep}"


class TestSubstituteValue:
    def test_string(self):
        result = substitute_value("src{/}main")
        assert result == f"src{os.sep}main"

    def test_list_of_strings(self):
        result = substitute_value(["src{/}main", "tests{/}unit"])
        assert result == [f"src{os.sep}main", f"tests{os.sep}unit"]

    def test_nested_list(self):
        result = substitute_value([["pytest", "{posargs}"]], posargs=["-v"])
        assert result == [["pytest", "-v"]]

    def test_dict(self):
        result = substitute_value(
            {"key": "{env:MY_VAR}"}, environ={"MY_VAR": "my_value"}
        )
        assert result == {"key": "my_value"}

    def test_nested_dict(self):
        result = substitute_value(
            {"env_run_base": {"commands": [["pytest", "{posargs}"]]}},
            posargs=["--verbose"],
        )
        assert result == {"env_run_base": {"commands": [["pytest", "--verbose"]]}}

    def test_non_string_passthrough(self):
        assert substitute_value(42) == 42
        assert substitute_value(3.14) == 3.14
        assert substitute_value(True) is True
        assert substitute_value(None) is None


class TestSubstituteConfig:
    def test_full_config(self):
        config = {
            "env_list": ["py{env:PYTHON_VERSION}"],
            "env_run_base": {"deps": ["pytest"], "commands": [["pytest", "{posargs}"]]},
        }
        result = substitute_config(
            config, posargs=["tests/", "-v"], environ={"PYTHON_VERSION": "3.11"}
        )
        assert result == {
            "env_list": ["py3.11"],
            "env_run_base": {"deps": ["pytest"], "commands": [["pytest", "tests/ -v"]]},
        }

    def test_pathsep_in_config(self):
        config = {"set_env": {"PATH": "bin{:}usr/bin"}}
        result = substitute_config(config)
        assert result["set_env"]["PATH"] == f"bin{os.pathsep}usr/bin"


class TestINISectionReference:
    """Test INI-style section references like {[section]key}."""

    def test_testenv_reference(self):
        config = {
            "env_run_base": {
                "deps": "pytest",
                "commands": "pytest tests",
            }
        }
        result = substitute_string("{[testenv]deps}", config=config)
        assert result == "pytest"

    def test_tox_section_reference(self):
        config = {
            "env_list": "py39, py310",
            "requires": "tox>=4.0",
        }
        result = substitute_string("{[tox]env_list}", config=config)
        assert result == "py39, py310"

    def test_testenv_named_reference(self):
        config = {
            "env_run_base": {
                "deps": "pytest",
            },
            "env": {
                "lint": {
                    "deps": "ruff",
                    "commands": "ruff check src",
                }
            },
        }
        result = substitute_string("{[testenv:lint]deps}", config=config)
        assert result == "ruff"

    def test_testenv_named_fallback_to_base(self):
        config = {
            "env_run_base": {
                "deps": "pytest",
                "base_option": "base_value",
            },
            "env": {
                "lint": {
                    "deps": "ruff",
                }
            },
        }
        # lint doesn't have base_option, should fall back to env_run_base
        result = substitute_string("{[testenv:lint]base_option}", config=config)
        assert result == "base_value"

    def test_pkgenv_reference(self):
        config = {
            "env_pkg_base": {
                "pass_env": "HOME",
            }
        }
        result = substitute_string("{[pkgenv]pass_env}", config=config)
        assert result == "HOME"

    def test_invalid_section_reference(self):
        config = {"env_run_base": {"deps": "pytest"}}
        result = substitute_string("{[nonexistent]key}", config=config)
        assert result == "{[nonexistent]key}"

    def test_missing_key_in_section(self):
        config = {"env_run_base": {"deps": "pytest"}}
        result = substitute_string("{[testenv]nonexistent}", config=config)
        assert result == "{[testenv]nonexistent}"


class TestTOMLDottedReference:
    """Test TOML-style dotted references like {env_run_base.deps}."""

    def test_simple_dotted_reference(self):
        config = {
            "env_run_base": {
                "deps": "pytest",
            }
        }
        result = substitute_string("{env_run_base.deps}", config=config)
        assert result == "pytest"

    def test_nested_dotted_reference(self):
        config = {
            "env": {
                "lint": {
                    "deps": "ruff",
                }
            }
        }
        result = substitute_string("{env.lint.deps}", config=config)
        assert result == "ruff"

    def test_deep_dotted_reference(self):
        config = {"level1": {"level2": {"level3": {"value": "deep_value"}}}}
        result = substitute_string("{level1.level2.level3.value}", config=config)
        assert result == "deep_value"

    def test_missing_dotted_reference(self):
        config = {"env_run_base": {"deps": "pytest"}}
        result = substitute_string("{env_run_base.nonexistent}", config=config)
        assert result == "{env_run_base.nonexistent}"

    def test_dotted_reference_non_string_value(self):
        config = {
            "env_run_base": {
                "deps": ["pytest", "coverage"],  # List, not string
            }
        }
        # Non-string values should not be substituted
        result = substitute_string("{env_run_base.deps}", config=config)
        assert result == "{env_run_base.deps}"


class TestConfigReferenceInConfig:
    """Test using config references within substitute_config."""

    def test_reference_between_sections(self):
        config = {
            "base_deps": "pytest",
            "env_run_base": {
                "deps": "{base_deps}",
            },
        }
        result = substitute_config(config)
        assert result["env_run_base"]["deps"] == "pytest"

    def test_dotted_reference_in_config(self):
        config = {
            "env_run_base": {
                "deps": "pytest",
            },
            "env": {
                "lint": {
                    "also_deps": "Deps are: {env_run_base.deps}",
                }
            },
        }
        result = substitute_config(config)
        assert result["env"]["lint"]["also_deps"] == "Deps are: pytest"


class TestTOMLInlineSubstitution:
    """Test TOML inline table substitutions like { replace = "posargs", ... }."""

    def test_posargs_inline_basic(self):
        config = {"commands": [["python", {"replace": "posargs"}]]}
        result = substitute_config(config, posargs=["script.py", "--verbose"])
        assert result["commands"] == [["python", "script.py --verbose"]]

    def test_posargs_inline_with_default(self):
        config = {
            "commands": [["python", {"replace": "posargs", "default": "default.py"}]]
        }
        result = substitute_config(config, posargs=[])
        assert result["commands"] == [["python", "default.py"]]

    def test_posargs_inline_with_default_list(self):
        config = {
            "commands": [["python", {"replace": "posargs", "default": ["a", "b"]}]]
        }
        result = substitute_config(config, posargs=[])
        assert result["commands"] == [["python", ["a", "b"]]]

    def test_posargs_inline_extend(self):
        config = {
            "commands": [
                [
                    "python",
                    {"replace": "posargs", "default": ["a", "b"], "extend": True},
                ]
            ]
        }
        result = substitute_config(config, posargs=[])
        assert result["commands"] == [["python", "a", "b"]]

    def test_posargs_inline_extend_with_posargs(self):
        config = {"commands": [["pytest", {"replace": "posargs", "extend": True}]]}
        result = substitute_config(config, posargs=["tests/", "-v"])
        assert result["commands"] == [["pytest", "tests/", "-v"]]

    def test_posargs_inline_extend_empty(self):
        config = {"commands": [["pytest", {"replace": "posargs", "extend": True}]]}
        result = substitute_config(config, posargs=[])
        assert result["commands"] == [["pytest"]]

    def test_env_inline_basic(self):
        config = {"commands": [["echo", {"replace": "env", "name": "MY_VAR"}]]}
        result = substitute_config(config, environ={"MY_VAR": "my_value"})
        assert result["commands"] == [["echo", "my_value"]]

    def test_env_inline_with_default(self):
        config = {
            "commands": [
                [
                    "echo",
                    {"replace": "env", "name": "NONEXISTENT", "default": "fallback"},
                ]
            ]
        }
        result = substitute_config(config, environ={})
        assert result["commands"] == [["echo", "fallback"]]

    def test_inline_substitution_in_nested_list(self):
        config = {
            "env_run_base": {
                "commands": [
                    [
                        "pytest",
                        {"replace": "posargs", "default": ["tests"], "extend": True},
                    ]
                ]
            }
        }
        result = substitute_config(config, posargs=[])
        assert result["env_run_base"]["commands"] == [["pytest", "tests"]]

    def test_multiple_inline_substitutions(self):
        config = {
            "commands": [
                ["cmd1", {"replace": "posargs", "extend": True}],
                ["cmd2", {"replace": "posargs", "extend": True}],
            ]
        }
        result = substitute_config(config, posargs=["arg1", "arg2"])
        assert result["commands"] == [
            ["cmd1", "arg1", "arg2"],
            ["cmd2", "arg1", "arg2"],
        ]

    def test_ref_inline_basic(self):
        config = {
            "env_run_base": {"deps": ["pytest", "coverage"]},
            "env": {
                "lint": {"deps": [{"replace": "ref", "of": ["env_run_base", "deps"]}]}
            },
        }
        result = substitute_config(config)
        assert result["env"]["lint"]["deps"] == ["pytest", "coverage"]

    def test_ref_inline_extend(self):
        config = {
            "env_run_base": {"deps": ["pytest", "coverage"]},
            "env": {
                "lint": {
                    "deps": [
                        {
                            "replace": "ref",
                            "of": ["env_run_base", "deps"],
                            "extend": True,
                        },
                        "ruff",
                    ]
                }
            },
        }
        result = substitute_config(config)
        assert result["env"]["lint"]["deps"] == ["pytest", "coverage", "ruff"]

    def test_ref_inline_with_default(self):
        config = {
            "env": {
                "lint": {
                    "deps": [
                        {
                            "replace": "ref",
                            "of": ["nonexistent", "key"],
                            "default": "fallback-dep",
                        }
                    ]
                }
            }
        }
        result = substitute_config(config)
        assert result["env"]["lint"]["deps"] == ["fallback-dep"]

    def test_ref_inline_with_default_list(self):
        config = {
            "env": {
                "lint": {
                    "deps": [
                        {
                            "replace": "ref",
                            "of": ["nonexistent"],
                            "default": ["a", "b"],
                            "extend": True,
                        }
                    ]
                }
            }
        }
        result = substitute_config(config)
        assert result["env"]["lint"]["deps"] == ["a", "b"]

    def test_ref_inline_nested_path(self):
        config = {
            "env": {
                "base": {"commands": [["pytest"]]},
                "extended": {
                    "commands": [{"replace": "ref", "of": ["env", "base", "commands"]}]
                },
            }
        }
        result = substitute_config(config)
        assert result["env"]["extended"]["commands"] == [["pytest"]]

    def test_ref_inline_nested_path_extend(self):
        config = {
            "env": {
                "base": {"commands": [["pytest"]]},
                "extended": {
                    "commands": [
                        {
                            "replace": "ref",
                            "of": ["env", "base", "commands"],
                            "extend": True,
                        }
                    ]
                },
            }
        }
        result = substitute_config(config)
        assert result["env"]["extended"]["commands"] == [["pytest"]]

    def test_ref_inline_string_value(self):
        config = {
            "base_python": "python3.11",
            "env_run_base": {"base_python": {"replace": "ref", "of": ["base_python"]}},
        }
        result = substitute_config(config)
        assert result["env_run_base"]["base_python"] == "python3.11"


class TestEdgeCases:
    def test_unknown_substitution_preserved(self):
        result = substitute_string("{unknown_sub}")
        assert result == "{unknown_sub}"

    def test_empty_braces(self):
        result = substitute_string("{}")
        assert result == "{}"

    def test_malformed_env_no_key(self):
        result = substitute_string("{env:}")
        assert result == ""

    def test_deeply_nested_structure(self):
        config = {"level1": {"level2": {"level3": [{"level4": "value{/}here"}]}}}
        result = substitute_config(config)
        assert result["level1"]["level2"]["level3"][0]["level4"] == f"value{os.sep}here"

    def test_malformed_section_reference(self):
        result = substitute_string("{[incomplete}", config={})
        assert result == "{[incomplete}"

    def test_empty_section_reference(self):
        result = substitute_string("{[]key}", config={})
        assert result == "{[]key}"
