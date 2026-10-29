"""Literal transformations must preserve runtime bytes and numeric behavior."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lua_minifier.core import Minifier
from lua_minifier.core.string_minifier import minify_number, minify_string


@pytest.fixture(params=["lua", "luau"])
def runtime(request):
    executable = os.environ.get(request.param.upper()) or shutil.which(request.param)
    if not executable:
        pytest.skip(f"{request.param} runtime unavailable")
    return executable


def execute(runtime, source, tmp_path):
    path = tmp_path / "literal.lua"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run([runtime, str(path)], capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.mark.parametrize("literal", [
    r'"\255"', r'"\128\255"', r'"\xFF\x80"',
    r'"\0012"', r'"\0009"', r'"\1274"',
    '"éÿ😀"', r'"\u{E9}\u{1F600}"',
    r'"\255é\0012"', r'"a\n\t\\\"b"',
])
def test_string_bytes_survive_minification(runtime, tmp_path, literal):
    source = f"local s={literal};print(#s);for i=1,#s do print(string.byte(s,i)) end"
    expected = execute(runtime, source, tmp_path)
    result = Minifier().minify(source).output
    assert execute(runtime, result, tmp_path) == expected


@pytest.mark.parametrize("literal", [
    r'"\256"', r'"\xGG"', r'"\u{}"', r'"\u{110000}"',
    r'"\q"', r'"\u{D800}"', '"trailing\\',
])
def test_unsupported_or_malformed_escapes_remain_unchanged(literal):
    assert minify_string(literal) == literal


def test_string_compression_remains_enabled():
    assert len(minify_string(r'"\065\066\067"')) < len(r'"\065\066\067"')


@pytest.mark.parametrize(("literal", "expected"), [
    (r'"\255"', b"1\n255\n"),
    (r'"\0012"', b"2\n1\n50\n"),
    ('"é"', b"2\n195\n169\n"),
])
def test_known_string_byte_values(runtime, tmp_path, literal, expected):
    source = f"local s={literal};print(#s);for i=1,#s do print(string.byte(s,i)) end"
    assert execute(runtime, source, tmp_path) == expected
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


@pytest.mark.parametrize("literal", [
    "1.0", "0.0", "-0.0", "1e309", "1e-999", "1e+03",
    "0.5000", "9007199254740993.0", "9223372036854775807",
    "9223372036854775808", "0009223372036854775807",
    "0xFFFFFFFFFFFFFFFF", "0x1.8p+1", "0x1p-1074",
])
def test_numeric_runtime_behavior_survives_minification(runtime, tmp_path, literal):
    if "luau" in Path(runtime).name and literal.startswith("0x") and "p" in literal:
        pytest.skip("Luau does not support hexadecimal floats")
    source = (f"local n={literal};print(n,tostring(n),1/n);"
              "if math.type then print(math.type(n)) end")
    expected = execute(runtime, source, tmp_path)
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


def test_numeric_compaction_still_removes_redundant_characters():
    assert minify_number("0.5000") == ".5"
    assert minify_number("1.000e+003") == "1e3"
    assert minify_number("000123") == "123"
