"""Literal transformations must preserve runtime bytes and numeric behavior."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from lua_minifier.core import Minifier
from lua_minifier.core.lexer import Lexer, TokenType
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
    if r"\u{" in literal and execute(runtime, "print(_VERSION)", tmp_path).strip() == b"Lua 5.2":
        pytest.skip("Lua 5.2 does not support Unicode escapes")
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
    if (literal.startswith("0x") and "p" in literal
            and execute(runtime, "print(_VERSION)", tmp_path).strip() == b"Lua 5.1"):
        pytest.skip("Lua 5.1 does not support hexadecimal floats")
    source = (f"local n={literal};print(n,tostring(n),1/n);"
              "if math.type then print(math.type(n)) end")
    expected = execute(runtime, source, tmp_path)
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


def test_numeric_compaction_still_removes_redundant_characters():
    assert minify_number("0.5000") == ".5"
    assert minify_number("1.000e+003") == "1e3"
    assert minify_number("000123") == "123"


@pytest.mark.parametrize("literal", [
    r'"\x41"', r'"\u{41}"', r'"a\z  b"',
    '"a\\z \t\v\f\r\n b"',
])
def test_dialect_sensitive_escapes_preserve_original(runtime, tmp_path, literal):
    version = execute(runtime, "print(_VERSION)", tmp_path)
    if b"Lua 5.2" in version and r"\u{" in literal:
        pytest.skip("Lua 5.2 does not support Unicode escapes")
    if b"Lua 5.1" in version and "\n" in literal:
        pytest.skip("Lua 5.1 does not support multiline whitespace-skipping escapes")
    source = f"local s={literal};print(#s);for i=1,#s do print(string.byte(s,i)) end"
    expected = execute(runtime, source, tmp_path)
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected
    assert minify_string(literal) == literal


def test_hex_escape_has_runtime_specific_bytes(runtime, tmp_path):
    version = execute(runtime, "print(_VERSION)", tmp_path)
    expected = b"3\n120\n52\n49\n" if b"Lua 5.1" in version else b"1\n65\n"
    source = r'local s="\x41";print(#s);for i=1,#s do print(string.byte(s,i)) end'
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


def test_escaped_backslash_does_not_disable_portable_compression():
    literal = r'"\\x\065\066\067"'
    assert len(minify_string(literal)) < len(literal)


@pytest.mark.parametrize("literal", [
    "[[\r\nhello]]", "[[a\r\nb]]", "[=[\r\na\r\nb]=]",
    "[[\n\nhello]]", "[[a\nb]]", "[[\rhello]]", "[[a\rb]]",
    "[[\n\rhello]]", "[[a\n\rb]]", "[=[é\r\nb]=]",
])
def test_long_string_newlines_preserve_bytes(runtime, tmp_path, literal):
    source = f"local s={literal};print(#s);for i=1,#s do print(string.byte(s,i)) end"
    expected = execute(runtime, source, tmp_path)
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


@pytest.mark.parametrize("literal", ["[[\rhello]]", "[[a\rb]]", "[[a\n\rb]]"])
def test_dialect_sensitive_long_newlines_remain_unchanged(literal):
    assert minify_string(literal) == literal


def test_known_long_string_newline_bytes(runtime, tmp_path):
    source = "local s=[=[\r\na\r\nb]=];print(#s);for i=1,#s do print(string.byte(s,i)) end"
    expected = b"3\n97\n10\n98\n"
    assert execute(runtime, source, tmp_path) == expected
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


def test_known_bare_cr_long_string_bytes(runtime, tmp_path):
    source = "local s=[=[\ra\rb]=];print(#s);for i=1,#s do print(string.byte(s,i)) end"
    version = execute(runtime, "print(_VERSION)", tmp_path)
    expected = b"4\n13\n97\n13\n98\n" if b"Luau" in version else b"3\n97\n10\n98\n"
    assert execute(runtime, source, tmp_path) == expected
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


@pytest.mark.parametrize(("literal", "expected"), [
    ("1e1_0", b"10000000000\n"),
    ("1E+1_0", b"10000000000\n"),
    ("1e-0_1", b"0.1\n"),
    ("1_0e0_1", b"100\n"),
    ("1_000", b"1000\n"),
    ("0xF_F", b"255\n"),
    ("0b1_010", b"10\n"),
])
def test_luau_numeric_separators_execute(runtime, tmp_path, literal, expected):
    if "luau" not in Path(runtime).name:
        pytest.skip("Numeric separators are Luau syntax")
    source = f"print({literal})"
    assert execute(runtime, source, tmp_path) == expected
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected


@pytest.mark.parametrize("literal", ["1e1_0", "1e-0_1", "0x1p+0_1"])
def test_exponent_separator_is_part_of_numeric_token(literal):
    tokens = [token for token in Lexer(literal).tokenize() if token.type != TokenType.EOF]
    assert [(token.type, token.value) for token in tokens] == [(TokenType.NUMBER, literal)]


def test_identifier_after_exponent_stays_separate(runtime, tmp_path):
    source = "local _0=7;print(1e1,_0)"
    expected = execute(runtime, source, tmp_path)
    assert execute(runtime, Minifier().minify(source).output, tmp_path) == expected
