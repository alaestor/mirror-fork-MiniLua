"""Source files are byte streams, including literal bytes outside UTF-8."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from lua_minifier.core import Minifier
from lua_minifier.utils.file_utils import read_source, write_output


@pytest.fixture(params=["lua", "luau"])
def runtime(request):
    executable = os.environ.get(request.param.upper()) or shutil.which(request.param)
    if not executable:
        pytest.skip(f"{request.param} runtime unavailable")
    return executable


def execute(runtime, path):
    result = subprocess.run([runtime, str(path)], capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.mark.parametrize(("literal", "expected"), [
    (b'"\xff"', b"1\n255\n"),
    (b"[[\xff]]", b"1\n255\n"),
    ('"é"'.encode("utf-8"), b"2\n195\n169\n"),
    (b"[[a\rb]]", None),
])
def test_file_minification_preserves_literal_bytes(runtime, tmp_path, literal, expected):
    source = b"local s=" + literal + b";print(#s);for i=1,#s do print(string.byte(s,i)) end"
    original = tmp_path / "input.lua"
    output = tmp_path / "output.lua"
    original.write_bytes(source)
    if expected is None:
        expected = b"3\n97\n13\n98\n" if "luau" in Path(runtime).name else b"3\n97\n10\n98\n"
    assert execute(runtime, original) == expected

    result = Minifier().minify(read_source(original))
    write_output(output, result.output)

    assert execute(runtime, output) == expected
    assert result.original_size == len(source)
    assert result.minified_size == len(output.read_bytes())


def test_read_write_preserves_exact_source_bytes(tmp_path):
    original = tmp_path / "input.lua"
    output = tmp_path / "output.lua"
    source = b'-- comment\r\nlocal s="\xff\xc3\xa9"\rprint(s)\n'
    original.write_bytes(source)
    write_output(output, read_source(original))
    assert output.read_bytes() == source


@pytest.mark.parametrize("output_mode", ["file", "stdout"])
def test_cli_file_output_preserves_non_utf8_bytes(runtime, tmp_path, output_mode):
    original = tmp_path / "input.lua"
    output = tmp_path / "output.lua"
    original.write_bytes(b'local s="\xff";print(#s,string.byte(s))')
    args = ["-o", str(output)] if output_mode == "file" else ["--stdout"]
    result = subprocess.run(
        [sys.executable, "-m", "lua_minifier.cli", str(original), *args, "--quiet"],
        capture_output=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    if output_mode == "stdout":
        output.write_bytes(result.stdout)
    assert execute(runtime, output) == b"1\t255\n"
