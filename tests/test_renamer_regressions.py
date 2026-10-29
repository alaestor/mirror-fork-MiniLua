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
    result = Minifier(MinifyOptions(
        rename_locals=True, minify_strings=False, minify_numbers=False,
        preserve_names=preserve_names,
    )).minify(source)
    assert not result.errors, result.errors
    output = result.output
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


@pytest.mark.parametrize(("source", "expected"), [
    ('local x=7; do local x=x+1; print(x) end; print(x)', b"8\n7\n"),
    ('local x=2; local y=3; local x,y=y,x; print(x,y)', b"3\t2\n"),
    ('local x=1; repeat local x=x+1; print(x) until x==2; print(x)', b"2\n1\n"),
    ('local i=100; for i=i-99,1 do print(i) end; print(i)', b"1\n100\n"),
    ('local x={8}; for x,y in ipairs(x) do print(x,y) end; print(x[1])', b"1\t8\n8\n"),
    ('local x=7; if false then local x=2 elseif x==7 then print(x) else local x=9 end; print(x)', b"7\n7\n"),
    ('local x=7; if false then local x=2 else print(x) end', b"7\n"),
    ('local function f(f) return f end; print(f(4))', b"4\n"),
    ('local x=1; local before=function() return x end; local x=2; local after=function() return x end; x=3; print(before(),after())', b"1\t3\n"),
    ('local x=7; local x=function() return x end; print(x())', b"7\n"),
    ('local function f(n) if n==0 then return 1 end return n*f(n-1) end; print(f(4))', b"24\n"),
    ('local self=99; local t={value=7}; function t:get() return self.value end; print(t:get(),self)', b"7\t99\n"),
    ('local self=99; local t={value=7}; function t:get() return function() return self.value end end; print(t:get()(),self)', b"7\t99\n"),
    ('local t={}; local method=5; function t.method(method) return method+1 end; print(t["method"](8),method)', b"9\t5\n"),
    ('local x=0; while x<2 do local y=x; x=x+1; print(y) end; do local x=9; print(x) end; print(x)', b"0\n1\n9\n2\n"),
])
def test_binding_scopes(runtime, tmp_path, source, expected):
    assert_execution(runtime, tmp_path, source, expected)


def test_lua_labels_and_attributes(runtime, tmp_path):
    if Path(runtime).name == "luau":
        pytest.skip("Lua 5.4 labels and attributes")
    version = subprocess.run([runtime, "-e", "print(_VERSION)"],
                             capture_output=True, timeout=3).stdout
    if version.strip() != b"Lua 5.4":
        pytest.skip("local attributes require Lua 5.4")
    assert_execution(runtime, tmp_path,
                     'local target <const> = 7; goto target; ::target:: print(target)', b"7\n")


@pytest.mark.parametrize(("source", "expected"), [
    ('local x=5; do local x; print(x) end; print(x)', b"nil\n5\n"),
    ('local x=1; local function before() return x end; local x=x+1; print(before(),x)', b"1\t2\n"),
    ('local i=2; for i=1,i do for i=1,i do print(i) end end; print(i)', b"1\n1\n2\n2\n"),
    ('local k=9; for k,v in function(_,last) if last==nil then return k,4 end end,nil,nil do print(k,v) end; print(k)', b"9\t4\n9\n"),
    ('local n=0; repeat local value=n; n=n+1 until (function() return value==1 end)(); print(n)', b"2\n"),
    ('local self=10; local t={}; function t:f(self) return self end; print(t:f(3),self)', b"3\t10\n"),
    ('local x=3; local t={f=function(y,z) return y+z end,x=x}; print(t.f(x,2),t["x"])', b"5\t3\n"),
    ('local type=type; local value=3; print(type(value))', b"number\n"),
    ('local x=1; local function f(...) local x=select(1,...); return x end; print(f(4),x)', b"4\t1\n"),
    ('local x=2; print(-x^2==-4,2^-x==0.25,x..x,x==2 and x or 9)', b"true\ttrue\t22\t2\n"),
])
def test_binding_adversarial_cases(runtime, tmp_path, source, expected):
    assert_execution(runtime, tmp_path, source, expected)


def test_luau_compound_assignment_and_continue(runtime, tmp_path):
    if Path(runtime).name != "luau":
        pytest.skip("Luau-only syntax")
    assert_execution(runtime, tmp_path,
                     'local total=0; for i=1,3 do if i==2 then continue end total+=i end; print(total)',
                     b"4\n")


@pytest.mark.parametrize("source", [
    'local value: number = 3; print(value)',
    'local function identity(value: number): number return value end; print(identity(3))',
    'type Value = number; local value: Value = 3; print(value)',
    'local value=3; print(value :: number)',
    'local value=3; print(if value==3 then value else 0)',
    'local function identity<T>(value: T): T return value end; print(identity(3))',
])
def test_unsupported_luau_renaming_warns_without_partial_changes(runtime, tmp_path, source):
    if Path(runtime).name != "luau":
        pytest.skip("Luau-only syntax")
    from lua_minifier.core.lexer import Lexer
    from lua_minifier.core.renamer import RenamerError, VariableRenamer

    tokens = Lexer(source).tokenize()
    original = [(token.type, token.value) for token in tokens]
    with pytest.raises(RenamerError):
        VariableRenamer(tokens).rename()
    assert [(token.type, token.value) for token in tokens] == original
    result = Minifier(MinifyOptions(rename_locals=True,
                                   minify_numbers=False, minify_strings=False)).minify(source)
    assert len(result.errors) == 1
    assert result.errors[0].startswith("Renamer warning:")
    for name, program in (("original", source), ("minified", result.output)):
        path = tmp_path / f"{name}.luau"
        path.write_text(program)
        process = subprocess.run([runtime, str(path)], capture_output=True, timeout=3)
        assert process.returncode == 0, (program, process.stderr)
        assert process.stdout == b"3\n", (program, process.stdout)


def test_lua_label_without_semicolon(runtime, tmp_path):
    if Path(runtime).name == "luau":
        pytest.skip("Luau does not support goto")
    version = subprocess.run([runtime, "-e", "print(_VERSION)"],
                             capture_output=True, timeout=3).stdout
    if version.strip() == b"Lua 5.1":
        pytest.skip("goto requires Lua 5.2 or later")
    assert_execution(runtime, tmp_path,
                     'local target=7 ::target:: print(target)', b"7\n")


def test_lua_close_attribute_captures_initializer_scope(runtime, tmp_path):
    if Path(runtime).name == "luau":
        pytest.skip("Lua 5.4-only syntax")
    version = subprocess.run([runtime, "-e", "print(_VERSION)"],
                             capture_output=True, timeout=3).stdout
    if version.strip() != b"Lua 5.4":
        pytest.skip("local attributes require Lua 5.4")
    assert_execution(runtime, tmp_path,
                     'local value=1; do local resource <close> = setmetatable({},'
                     '{__close=function() print(value) end}); local value=2; print(value) end; print(value)',
                     b"2\n1\n1\n")


def test_preserved_name_still_shadows_outer_binding(runtime, tmp_path):
    assert_execution(runtime, tmp_path,
                     'local value=1; local function identity(value) return value end; print(identity(3),value)',
                     b"3\t1\n", preserve_names={"value"})


def test_unsupported_late_annotation_does_not_rename_earlier_declarations():
    from lua_minifier.core.lexer import Lexer
    from lua_minifier.core.renamer import RenamerError, VariableRenamer

    source = 'local longVariable=3; local value: number=longVariable; print(value)'
    tokens = Lexer(source).tokenize()
    original = [(token.type, token.value) for token in tokens]
    with pytest.raises(RenamerError, match="type annotations"):
        VariableRenamer(tokens).rename()
    assert [(token.type, token.value) for token in tokens] == original
    with_renaming = Minifier(MinifyOptions(rename_locals=True)).minify(source)
    without_renaming = Minifier().minify(source)
    assert with_renaming.output == without_renaming.output
    assert len(with_renaming.errors) == 1
