"""Kept comments must not merge with a preceding minus operator."""

import os
import shutil
import subprocess

import pytest

from lua_minifier import Minifier, MinifyOptions


CASES = [
    ('print(1 - --[[comment]] 2)', 'print(1- --[[comment]]2)\n', b'-1\n'),
    ('print(1 - -- comment\n 2)', 'print(1- -- comment\n2)\n', b'-1\n'),
    ('print(1 - --[=[comment]=] -2)', 'print(1- --[=[comment]=]-2)\n', b'3\n'),
    ('print(1 + --[[comment]] 2)', 'print(1+--[[comment]]2)\n', b'3\n'),
]


@pytest.mark.parametrize(('source', 'expected_output', 'expected_stdout'), CASES)
def test_kept_comment_output_has_only_necessary_separator(source, expected_output, expected_stdout):
    output = Minifier(MinifyOptions(remove_comments=False)).minify(source).output
    assert output == expected_output


@pytest.mark.parametrize('runtime_name', ['lua', 'luau'])
@pytest.mark.parametrize(('source', 'expected_output', 'expected_stdout'), CASES)
def test_kept_comments_preserve_execution(runtime_name, source, expected_output, expected_stdout, tmp_path):
    runtime = os.environ.get(runtime_name.upper()) or shutil.which(runtime_name)
    if runtime is None:
        pytest.skip(f'{runtime_name} runtime unavailable')
    output = Minifier(MinifyOptions(remove_comments=False)).minify(source).output
    for index, program in enumerate((source, output)):
        path = tmp_path / f'case{index}.lua'
        path.write_text(program)
        result = subprocess.run([runtime, str(path)], capture_output=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected_stdout


@pytest.mark.parametrize('source', [
    'print(1 - --[[comment]] 2)\n',
    'print(1 - -- comment\n 2)\n',
    'print(1\t-\t--[=[comment]=]\t2)\n',
])
def test_kept_comments_do_not_duplicate_preserved_whitespace(source):
    options = MinifyOptions(remove_comments=False, remove_whitespace=False)
    assert Minifier(options).minify(source).output == source
