"""Source belongs on stdout; diagnostics belong on stderr."""

import pytest
from click.testing import CliRunner

from lua_minifier.cli import cli


@pytest.mark.parametrize("mode", ["file", "stdin", "implicit-stdin"])
def test_stdout_contains_only_minified_source(tmp_path, mode):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    args = [str(source), "--stdout"] if mode == "file" else (["-", "--stdout"] if mode == "stdin" else [])
    result = CliRunner().invoke(cli, args, input="print(42)" if mode != "file" else None)
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"
    assert "MiniLua" in result.stderr


def test_file_mode_keeps_stats_but_not_on_stdout(tmp_path):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source), "--stdout", "--no-banner"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"
    assert "Original" in result.stderr
    assert "MiniLua" not in result.stderr


def test_batch_failure_does_not_contaminate_successful_stdout(tmp_path):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source), str(tmp_path / "missing.lua"), "--stdout", "-q"])
    assert result.exit_code == 1
    assert result.stdout == "print(42)\n"
    assert "Cannot read" in result.stderr


def test_quiet_suppresses_status_but_not_source(tmp_path):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source), "--stdout", "-q"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(42)\n"
    assert result.stderr == ""


def test_file_output_emits_no_source_on_stdout(tmp_path):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    result = CliRunner().invoke(cli, [str(source)])
    assert result.exit_code == 0, result.output
    assert result.stdout == ""
    assert "Original" in result.stderr
    assert source.with_name("input.min.lua").read_text() == "print(42)\n"
