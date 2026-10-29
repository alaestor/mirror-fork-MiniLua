"""Executable regressions for local-name binding and allocation."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest

from lua_minifier.core import Minifier, MinifyOptions


@pytest.fixture(params=["lua", "luau"])
def runtime(request):
    name = request.param
    executable = os.environ.get(f"MINILUA_TEST_{name.upper()}") or shutil.which(name)
    if executable is None:
        pytest.skip(f"{name} interpreter unavailable")
    return executable


def assert_execution(runtime, tmp_path, source, expected, *, preserve_names=None):
    output = Minifier(MinifyOptions(
        rename_locals=True, minify_strings=False, minify_numbers=False,
        preserve_names=preserve_names,
    )).minify(source).output
    for name, program in (("original", source), ("minified", output)):
        path = tmp_path / f"{name}.lua"
        path.write_text(program)
        result = subprocess.run(
            [runtime, str(path)], capture_output=True, timeout=3,
        )
        assert result.returncode == 0, (name, program, result.stderr)
        assert result.stdout == expected, (name, program, result.stdout)
    return output


@pytest.mark.parametrize(("source", "expected"), [
    ("a=10; local value=2; print(a+value)", b"12\n"),
    ("a=10; local value=2; a=a+value; print(a,value)", b"12\t2\n"),
    ("a=10; local value=2; local functionValue=function() return a+value end; print(functionValue())", b"12\n"),
    ("local value=2; print(value+3)", b"5\n"),
])
def test_generated_names_do_not_capture_globals(runtime, tmp_path, source, expected):
    assert_execution(runtime, tmp_path, source, expected)


def test_preserved_short_local_cannot_be_captured(runtime, tmp_path):
    assert_execution(runtime, tmp_path,
                     "local a=10; local value=2; print(a+value)", b"12\n",
                     preserve_names={"a"})


@pytest.mark.parametrize(("source", "expected"), [
    ('local x=1; local t={x=2}; print(t["x"],t.x,x)', b"2\t2\t1\n"),
    ('local x=3; local t={x=2,[x]=4}; print(t["x"],t[x])', b"2\t4\n"),
    ('local x=3; local t={nested={x=2},x=x}; print(t.nested["x"],t["x"])', b"2\t3\n"),
    ('local x=3; local t={x=0}; t.x=x; print(t["x"])', b"3\n"),
    ('local x=3; local t={x=function(self) return 9 end}; print(t["x"](t),t:x(),x)', b"9\t9\t3\n"),
    ('local x=3; local t={x=2; y=x}; print(t["x"],t.y)', b"2\t3\n"),
])
def test_table_keys_and_members_are_not_variables(runtime, tmp_path, source, expected):
    assert_execution(runtime, tmp_path, source, expected)
