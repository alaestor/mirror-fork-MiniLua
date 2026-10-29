"""Minimal separators must preserve the lexer boundaries of valid Lua."""

import shutil
import subprocess

import pytest

from lua_minifier import Minifier, MinifyOptions


@pytest.mark.parametrize(("source", "expected", "options"), [
    ('print("a" .. .5)', b'a0.5\n', {}),
    ('print("a" .. 0.5)', b'a0.5\n', {}),
    ('local t={x=7}; print(t[ [[x]] ])', b'7\n', {'minify_strings': False}),
    ('local t={["a\\nb\\nc\\nd\\ne\\nf"]=7}; print(t[ [[a\nb\nc\nd\ne\nf]] ])', b'7\n', {}),
    ('print(1. and true)', b'true\n', {'minify_numbers': False}),
    ('local x=3; print(x - -2)', b'5\n', {}),
    ('print(({x=7}).x)', b'7\n', {}),
])
def test_minified_token_boundaries_preserve_execution(tmp_path, source, expected, options):
    lua = shutil.which('lua')
    if lua is None:
        pytest.skip('Lua runtime unavailable')
    output = Minifier(MinifyOptions(**options)).minify(source).output
    for name, program in [('original', source), ('minified', output)]:
        path = tmp_path / (name + '.lua')
        path.write_text(program)
        result = subprocess.run([lua, str(path)], capture_output=True, timeout=3)
        assert result.returncode == 0, (program, result.stderr)
        assert result.stdout == expected, (program, result.stdout)


def test_attribute_close_does_not_merge_with_assignment():
    output = Minifier().minify('local value <const> = 7; print(value)').output
    assert '<const> =7' in output


def test_unambiguous_punctuation_still_compacts():
    assert Minifier().minify('print ( 1 , 2 )').output == 'print(1,2)\n'
