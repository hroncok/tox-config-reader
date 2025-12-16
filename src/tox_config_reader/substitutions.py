"""
Tox configuration substitution handling.

Performs substitutions on tox configuration values according to
https://tox.wiki/en/stable/config.html#substitutions

Supported substitutions:
- {env:KEY} - environment variable
- {env:KEY:DEFAULT} - environment variable with default
- {posargs} - positional arguments
- {posargs:DEFAULT} - positional arguments with default
- {posargs[N]} - specific positional argument by index (TOML only)
- {posargs[N:M]} - slice of positional arguments (TOML only)
- {tty:ON_VALUE:OFF_VALUE} - interactive shell substitution
- {:} - os.pathsep
- {/} - os.sep
- \\{ - escaped brace (literal {)
- {[section]key} - INI-style reference to value from another section
- {[env_name]key} - TOML-style configuration reference
- {key.subkey} - TOML-style dotted reference to nested config value

See also:
- https://tox.wiki/en/stable/config.html#substitution-for-values-from-other-sections
- https://tox.wiki/en/stable/config.html#string-substitution-references
- https://tox.wiki/en/stable/config.html#configuration-reference
- https://tox.wiki/en/stable/config.html#positional-argument-reference

TOML inline table substitutions are also supported:
- { replace = "posargs", default = ["a", "b"], extend = true }
- { replace = "env", name = "VAR", default = "fallback" }
- { replace = "ref", of = ["env_run_base", "deps"] }
"""

from __future__ import annotations

import os
import re  # Used for ESCAPED_BRACE_PATTERN
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any


# Pattern for escaped braces
ESCAPED_BRACE_PATTERN = re.compile(r"\\([{}\[\]:])")


def _find_matching_brace(text: str, start: int) -> int | None:
    """
    Find the matching closing brace for an opening brace.

    Args:
        text: The full text.
        start: Index of the opening brace.

    Returns:
        Index of the matching closing brace, or None if not found.
    """
    if start >= len(text) or text[start] != "{":
        return None

    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        if text[i] == "\\" and i + 1 < len(text):
            # Skip escaped character
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1

    if depth == 0:
        return i - 1  # Return index of the closing brace
    return None


def _find_substitutions(text: str) -> list[tuple[int, int, str]]:
    """
    Find all substitution expressions in text.

    Args:
        text: The text to search.

    Returns:
        List of (start, end, expression) tuples.
    """
    results = []
    i = 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text) and text[i + 1] == "{":
            # Skip escaped brace
            i += 2
            continue
        if text[i] == "{":
            end = _find_matching_brace(text, i)
            if end is not None:
                expr = text[i + 1:end]
                results.append((i, end + 1, expr))
                i = end + 1
                continue
        i += 1
    return results


def _substitute_env(
    key: str,
    default: str | None = None,
    environ: dict[str, str] | None = None,
) -> str:
    """
    Substitute an environment variable.

    Args:
        key: Environment variable name.
        default: Default value if variable is not set.
        environ: Environment dictionary to use (defaults to os.environ).

    Returns:
        The environment variable value or default.
    """
    if environ is None:
        environ = os.environ
    value = environ.get(key)
    if value is not None:
        return value
    if default is not None:
        return default
    return ""


def _substitute_posargs(posargs: list[str], default: str | None = None) -> str:
    """
    Substitute positional arguments.

    Args:
        posargs: List of positional arguments provided by user.
        default: Default value if no posargs provided.

    Returns:
        Space-joined posargs or default.
    """
    if posargs:
        return " ".join(posargs)
    if default is not None:
        return default
    return ""


def _substitute_posargs_indexed(
    posargs: list[str],
    index_expr: str,
) -> str | None:
    """
    Substitute positional arguments with index or slice.

    Supports:
    - {posargs[0]} - single index
    - {posargs[-1]} - negative index
    - {posargs[1:]} - slice from index
    - {posargs[:2]} - slice to index
    - {posargs[1:3]} - slice range

    Args:
        posargs: List of positional arguments provided by user.
        index_expr: The index expression (e.g., "0", "1:", ":2", "1:3").

    Returns:
        The indexed/sliced posargs as string, or None if invalid.
    """
    try:
        if ":" in index_expr:
            # Slice expression
            parts = index_expr.split(":", 1)
            start = int(parts[0]) if parts[0] else None
            end = int(parts[1]) if parts[1] else None
            sliced = posargs[start:end]
            return " ".join(sliced)
        else:
            # Single index
            idx = int(index_expr)
            if -len(posargs) <= idx < len(posargs):
                return posargs[idx]
            return ""  # Index out of range returns empty
    except (ValueError, IndexError):
        return None  # Invalid expression


def _substitute_tty(on_value: str, off_value: str = "") -> str:
    """
    Substitute based on whether running in interactive terminal.

    Args:
        on_value: Value to use when TTY is available.
        off_value: Value to use when TTY is not available.

    Returns:
        on_value if stdin is a TTY, off_value otherwise.
    """
    if sys.stdin.isatty():
        return on_value
    return off_value


# Mapping from INI section names to normalized config keys
INI_SECTION_MAP = {
    "tox": "",  # Core settings are at root level
    "tox:tox": "",  # setup.cfg style
    "testenv": "env_run_base",
    "pkgenv": "env_pkg_base",
}


def _resolve_ini_section_reference(
    section: str,
    key: str,
    config: dict[str, Any],
) -> str | None:
    """
    Resolve an INI-style section reference like {[testenv]deps}.

    Args:
        section: The section name (e.g., "testenv", "testenv:lint").
        key: The key within the section.
        config: The full config dict.

    Returns:
        The resolved value as string, or None if not found.
    """
    # Handle testenv:envname references
    if section.startswith("testenv:"):
        env_name = section[len("testenv:"):]
        env_config = config.get("env", {}).get(env_name, {})
        if key in env_config:
            value = env_config[key]
            if isinstance(value, str):
                return value
        # Fall back to env_run_base
        base_config = config.get("env_run_base", {})
        if key in base_config:
            value = base_config[key]
            if isinstance(value, str):
                return value
        return None

    # Map section name to normalized config path
    if section in INI_SECTION_MAP:
        mapped = INI_SECTION_MAP[section]
        if mapped == "":
            # Root level
            if key in config:
                value = config[key]
                if isinstance(value, str):
                    return value
        else:
            # Nested section
            section_config = config.get(mapped, {})
            if key in section_config:
                value = section_config[key]
                if isinstance(value, str):
                    return value

    return None


def _get_value_by_path(
    parts: list[str],
    config: dict[str, Any],
) -> Any | None:
    """
    Get a value from config by a list of path parts.

    Args:
        parts: List of keys to traverse (e.g., ["env_run_base", "deps"]).
        config: The full config dict.

    Returns:
        The value at the path, or None if not found.
    """
    current: Any = config

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None

    return current


def _resolve_dotted_reference(
    path: str,
    config: dict[str, Any],
) -> str | None:
    """
    Resolve a TOML-style dotted reference like {env_run_base.deps}.

    Args:
        path: Dotted path (e.g., "env_run_base.deps", "env.lint.deps").
        config: The full config dict.

    Returns:
        The resolved value as string, or None if not found.
    """
    parts = path.split(".")
    result = _get_value_by_path(parts, config)

    if isinstance(result, str):
        return result

    return None


def _parse_substitution(expr: str) -> tuple[str, list[str]]:
    """
    Parse a substitution expression into type and arguments.

    Args:
        expr: The expression inside braces (e.g., "env:KEY:DEFAULT").

    Returns:
        Tuple of (substitution_type, arguments).
    """
    # Handle special single-character substitutions
    if expr == ":":
        return ("pathsep", [])
    if expr == "/":
        return ("sep", [])

    # Split on colons, but handle escaped colons, nested braces, and brackets
    parts = []
    current = []
    i = 0
    brace_depth = 0
    bracket_depth = 0

    while i < len(expr):
        char = expr[i]

        # Handle escape sequences
        if char == "\\" and i + 1 < len(expr):
            next_char = expr[i + 1]
            if next_char == ":":
                current.append(":")
                i += 2
                continue
            elif next_char in "{}[]":
                current.append(next_char)
                i += 2
                continue

        # Track brace and bracket depth
        if char == "{":
            brace_depth += 1
            current.append(char)
            i += 1
        elif char == "}":
            brace_depth -= 1
            current.append(char)
            i += 1
        elif char == "[":
            bracket_depth += 1
            current.append(char)
            i += 1
        elif char == "]":
            bracket_depth -= 1
            current.append(char)
            i += 1
        elif char == ":" and brace_depth == 0 and bracket_depth == 0:
            # Only split on colon if not inside nested braces or brackets
            parts.append("".join(current))
            current = []
            i += 1
        else:
            current.append(char)
            i += 1

    parts.append("".join(current))

    if not parts:
        return ("unknown", [])

    return (parts[0], parts[1:])


def _substitute_single(
    expr: str,
    config: dict[str, Any],
    posargs: list[str],
    environ: dict[str, str],
) -> str:
    """
    Perform a single substitution.

    Args:
        expr: The expression inside braces.
        config: The full config dict for reference substitutions.
        posargs: Positional arguments from user.
        environ: Environment dictionary to use.

    Returns:
        The substituted value.
    """
    # Check for INI-style section reference: {[section]key}
    if expr.startswith("["):
        bracket_end = expr.find("]")
        if bracket_end > 1:
            section = expr[1:bracket_end]
            key = expr[bracket_end + 1:]
            if key:
                result = _resolve_ini_section_reference(section, key, config)
                if result is not None:
                    return result
        # Invalid or not found, return as-is
        return f"{{{expr}}}"

    sub_type, args = _parse_substitution(expr)

    if sub_type == "pathsep":
        return os.pathsep

    if sub_type == "sep":
        return os.sep

    if sub_type == "env":
        if not args:
            return f"{{{expr}}}"  # Invalid, return as-is
        key = args[0]
        default = args[1] if len(args) > 1 else None
        # Recursively substitute the default value
        if default is not None:
            default = substitute_string(default, config=config, posargs=posargs, environ=environ)
        return _substitute_env(key, default, environ)

    # Handle posargs with optional index: {posargs}, {posargs[0]}, {posargs[1:]}
    if sub_type == "posargs" or sub_type.startswith("posargs["):
        # Check for indexed posargs: posargs[N] or posargs[N:M]
        if sub_type.startswith("posargs[") and sub_type.endswith("]"):
            index_expr = sub_type[8:-1]  # Extract content between [ and ]
            result = _substitute_posargs_indexed(posargs, index_expr)
            if result is not None:
                return result
            return f"{{{expr}}}"  # Invalid index, return as-is

        # Regular posargs with optional default
        default = args[0] if args else None
        # Recursively substitute the default value
        if default is not None:
            default = substitute_string(default, config=config, posargs=posargs, environ=environ)
        return _substitute_posargs(posargs, default)

    if sub_type == "tty":
        on_value = args[0] if args else ""
        off_value = args[1] if len(args) > 1 else ""
        return _substitute_tty(on_value, off_value)

    # Check for TOML-style dotted reference: {env_run_base.deps}
    if "." in expr:
        result = _resolve_dotted_reference(expr, config)
        if result is not None:
            return result

    # Check if it's a simple config key reference at root level
    if sub_type in config:
        value = config[sub_type]
        if isinstance(value, str):
            return value
        # For non-string values, return as-is in braces
        return f"{{{expr}}}"

    # Unknown substitution, return as-is
    return f"{{{expr}}}"


def substitute_string(
    value: str,
    *,
    config: dict[str, Any] | None = None,
    posargs: list[str] | None = None,
    environ: dict[str, str] | None = None,
) -> str:
    """
    Perform substitutions on a single string value.

    Args:
        value: The string to substitute.
        config: The full config dict for reference substitutions.
        posargs: Positional arguments from user.
        environ: Environment dictionary to use (defaults to os.environ).

    Returns:
        The string with substitutions applied.
    """
    if config is None:
        config = {}
    if posargs is None:
        posargs = []
    if environ is None:
        environ = dict(os.environ)

    # Process substitutions iteratively to handle nested ones
    max_iterations = 10  # Prevent infinite loops
    prev_value = None

    for _ in range(max_iterations):
        if value == prev_value:
            break
        prev_value = value

        # Find all substitutions and replace from right to left
        # (to preserve indices)
        substitutions = _find_substitutions(value)
        for start, end, expr in reversed(substitutions):
            replacement = _substitute_single(expr, config, posargs, environ)
            value = value[:start] + replacement + value[end:]

    # Handle escaped braces
    value = ESCAPED_BRACE_PATTERN.sub(r"\1", value)

    return value


def _is_toml_inline_substitution(value: Any) -> bool:
    """
    Check if a value is a TOML inline table substitution.

    TOML inline substitutions look like:
    { replace = "posargs", default = ["a", "b"], extend = true }

    Args:
        value: The value to check.

    Returns:
        True if this is an inline substitution table.
    """
    return isinstance(value, dict) and "replace" in value


def _resolve_toml_inline_substitution(
    spec: dict[str, Any],
    config: dict[str, Any],
    posargs: list[str],
    environ: dict[str, str],
) -> tuple[Any, bool]:
    """
    Resolve a TOML inline table substitution.

    Handles substitutions like:
    { replace = "posargs", default = ["a", "b"], extend = true }
    { replace = "env", name = "MY_VAR", default = "fallback" }

    Args:
        spec: The substitution specification dict.
        config: The full config dict.
        posargs: Positional arguments from user.
        environ: Environment dictionary to use.

    Returns:
        Tuple of (resolved_value, extend_flag).
        extend_flag indicates if the value should extend a list.
    """
    replace_type = spec.get("replace", "")
    default = spec.get("default")
    extend = spec.get("extend", False)

    if replace_type == "posargs":
        if posargs:
            # Return posargs as list if extend, else as space-joined string
            if extend or isinstance(default, list):
                return list(posargs), extend
            return " ".join(posargs), extend
        # Use default if no posargs
        if default is not None:
            return default, extend
        return [] if extend else "", extend

    if replace_type == "env":
        env_name = spec.get("name", "")
        env_value = environ.get(env_name)
        if env_value is not None:
            return env_value, extend
        if default is not None:
            return default, extend
        return "", extend

    if replace_type == "ref":
        # Configuration reference: { replace = "ref", of = ["env_run_base", "deps"] }
        of = spec.get("of", [])
        if isinstance(of, list) and of:
            ref_value = _get_value_by_path(of, config)
            if ref_value is not None:
                # Auto-extend if the referenced value is a list
                should_extend = extend or isinstance(ref_value, list)
                return ref_value, should_extend
        if default is not None:
            # Auto-extend if the default value is a list
            should_extend = extend or isinstance(default, list)
            return default, should_extend
        return "", extend

    # Unknown replace type, return spec as-is
    return spec, False


def substitute_value(
    value: Any,
    *,
    config: dict[str, Any] | None = None,
    posargs: list[str] | None = None,
    environ: dict[str, str] | None = None,
) -> Any:
    """
    Perform substitutions on a value of any type.

    Recursively processes strings, lists, and dicts.
    Also handles TOML inline table substitutions like:
    { replace = "posargs", default = ["a", "b"], extend = true }

    Args:
        value: The value to substitute.
        config: The full config dict for reference substitutions.
        posargs: Positional arguments from user.
        environ: Environment dictionary to use (defaults to os.environ).

    Returns:
        The value with substitutions applied.
    """
    if config is None:
        config = {}
    if posargs is None:
        posargs = []
    if environ is None:
        environ = dict(os.environ)

    if isinstance(value, str):
        return substitute_string(value, config=config, posargs=posargs, environ=environ)

    if isinstance(value, list):
        result = []
        for item in value:
            if _is_toml_inline_substitution(item):
                resolved, extend = _resolve_toml_inline_substitution(item, config, posargs, environ)
                if extend and isinstance(resolved, list):
                    # Extend the result list with resolved items
                    result.extend(substitute_value(r, config=config, posargs=posargs, environ=environ) for r in resolved)
                else:
                    result.append(substitute_value(resolved, config=config, posargs=posargs, environ=environ))
            else:
                result.append(substitute_value(item, config=config, posargs=posargs, environ=environ))
        return result

    if isinstance(value, dict):
        # Check if this dict is an inline substitution at the top level
        if _is_toml_inline_substitution(value):
            resolved, _ = _resolve_toml_inline_substitution(value, config, posargs, environ)
            return substitute_value(resolved, config=config, posargs=posargs, environ=environ)
        return {k: substitute_value(v, config=config, posargs=posargs, environ=environ) for k, v in value.items()}

    # For other types (int, bool, None, etc.), return as-is
    return value


def substitute_config(
    config: dict[str, Any],
    *,
    posargs: list[str] | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Perform substitutions on an entire tox configuration dictionary.

    This is the main entry point for substitution processing. It takes
    a config dict as produced by read_config() and returns a new dict
    with all substitutions resolved.

    Args:
        config: The configuration dictionary from read_config().
        posargs: Positional arguments provided by the user (e.g., from CLI).
        environ: Environment dictionary to use (defaults to os.environ).

    Returns:
        A new dictionary with all substitutions resolved.

    Example:
        >>> from tox_config_reader import read_config
        >>> from tox_config_reader.substitutions import substitute_config
        >>> config = read_config()
        >>> resolved = substitute_config(config, posargs=["--verbose"])
    """
    if posargs is None:
        posargs = []
    if environ is None:
        environ = dict(os.environ)

    return substitute_value(config, config=config, posargs=posargs, environ=environ)

