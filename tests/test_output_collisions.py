"""Plan output destinations before any batch file can be replaced."""

import pytest
from click.testing import CliRunner

from lua_minifier.cli import cli


def source_file(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"print({value})")
    return path


@pytest.mark.parametrize("overwrite", [False, True])
def test_colliding_batch_names_are_rejected_before_any_write(tmp_path, overwrite):
    first = source_file(tmp_path / "a" / "same.lua", 1)
    second = source_file(tmp_path / "b" / "same.luau", 2)
    destination = tmp_path / "dist"
    args = [str(first), str(second), "-d", str(destination), "-q"]
    if overwrite:
        args.append("--overwrite")
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 1
    assert "collision" in result.stderr.lower()
    assert not destination.exists()
    assert first.read_text() == "print(1)"
    assert second.read_text() == "print(2)"


def test_destination_cannot_replace_another_input_before_it_is_read(tmp_path):
    first = source_file(tmp_path / "same.lua", 1)
    second = source_file(tmp_path / "same.min.lua", 2)
    result = CliRunner().invoke(cli, [str(first), str(second), "-f", "-q"])
    assert result.exit_code == 1
    assert first.read_text() == "print(1)"
    assert second.read_text() == "print(2)"


def test_distinct_batch_outputs_are_written(tmp_path):
    first = source_file(tmp_path / "a.lua", 1)
    second = source_file(tmp_path / "b.luau", 2)
    destination = tmp_path / "dist"
    result = CliRunner().invoke(cli, [str(first), str(second), "-d", str(destination), "-q"])
    assert result.exit_code == 0, result.output
    assert {p.name: p.read_text() for p in destination.iterdir()} == {
        "a.min.lua": "print(1)\n", "b.min.lua": "print(2)\n",
    }


def test_in_place_allows_each_input_to_replace_itself(tmp_path):
    first = source_file(tmp_path / "same.lua", 1)
    second = source_file(tmp_path / "same.luau", 2)
    result = CliRunner().invoke(cli, [str(first), str(second), "--in-place", "-q"])
    assert result.exit_code == 0, result.output
    assert first.read_text() == "print(1)\n"
    assert second.read_text() == "print(2)\n"


def test_stdout_does_not_require_distinct_file_destinations(tmp_path):
    first = source_file(tmp_path / "a" / "same.lua", 1)
    second = source_file(tmp_path / "b" / "same.lua", 2)
    result = CliRunner().invoke(cli, [str(first), str(second), "--stdout", "-q"])
    assert result.exit_code == 0, result.output
    assert result.stdout == "print(1)\nprint(2)\n"


def test_single_output_option_rejects_multiple_inputs(tmp_path):
    first = source_file(tmp_path / "a.lua", 1)
    second = source_file(tmp_path / "b.lua", 2)
    result = CliRunner().invoke(cli, [str(first), str(second), "-o", str(tmp_path / "out.lua"), "-q"])
    assert result.exit_code == 1
    assert not (tmp_path / "a.min.lua").exists()
    assert not (tmp_path / "b.min.lua").exists()
