"""Directory and glob discovery honor both supported source extensions."""

import pytest
from click.testing import CliRunner

from lua_minifier.cli import cli
from lua_minifier.utils.file_utils import discover_files


@pytest.mark.parametrize("recursive", [False, True])
def test_directory_includes_lua_and_luau_but_not_other_files(tmp_path, recursive):
    for name in ("one.lua", "two.luau", "notes.txt"):
        (tmp_path / name).write_text("print(1)")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "three.luau").write_text("print(3)")
    expected = {tmp_path / "one.lua", tmp_path / "two.luau"}
    if recursive:
        expected.add(nested / "three.luau")
    assert set(discover_files([str(tmp_path)], recursive=recursive)) == expected


@pytest.mark.parametrize("recursive", [False, True])
def test_cli_accepts_luau_only_directory(tmp_path, recursive):
    (tmp_path / "only.luau").write_text("print(42)")
    args = [str(tmp_path), "--stdout", "-q"]
    if recursive:
        args.append("--recursive")
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"


def test_overlapping_patterns_process_each_source_once(tmp_path):
    source = tmp_path / "one.luau"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source), str(tmp_path / "*.luau"), "--stdout", "-q"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"


def test_empty_directory_reports_no_sources_not_a_fake_glob(tmp_path):
    result = CliRunner().invoke(cli, [str(tmp_path), "--recursive", "-q"])
    assert result.exit_code == 1
    assert "No Lua/Luau files" in result.stderr
    assert "Cannot read" not in result.stderr


def test_explicit_nonstandard_extension_remains_supported(tmp_path):
    source = tmp_path / "script.txt"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source), "--stdout", "-q"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"
