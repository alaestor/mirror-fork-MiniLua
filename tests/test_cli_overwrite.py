"""Output replacement must require the same permission for every input mode."""

import pytest
from click.testing import CliRunner

from lua_minifier.cli import cli


@pytest.mark.parametrize("stdin", [True, False], ids=["stdin", "file"])
@pytest.mark.parametrize("overwrite", [False, True], ids=["refuse", "replace"])
def test_existing_output_requires_explicit_overwrite(tmp_path, stdin, overwrite):
    source = tmp_path / "input.lua"
    source.write_text("print(42)")
    destination = tmp_path / "out.lua"
    destination.write_bytes(b"original contents\n")
    args = ["-" if stdin else str(source), "-o", str(destination), "-q"]
    if overwrite:
        args.append("--overwrite")

    result = CliRunner().invoke(cli, args, input="print(42)" if stdin else None)

    assert result.exit_code == (0 if overwrite else 1), result.output
    assert destination.read_bytes() == (b"print(42)\n" if overwrite else b"original contents\n")


def test_stdin_can_create_new_output_without_overwrite(tmp_path):
    destination = tmp_path / "new" / "out.lua"
    result = CliRunner().invoke(cli, ["-", "-o", str(destination), "-q"], input="print(42)")
    assert result.exit_code == 0, result.output
    assert destination.read_bytes() == b"print(42)\n"
