"""A file interpreter directive must not absorb executable source."""

import shutil
import subprocess
import os

import pytest

from lua_minifier import Minifier, MinifyOptions
from lua_minifier.core.lexer import Lexer, TokenType


@pytest.mark.parametrize("runtime_name", ["lua", "luau"])
@pytest.mark.parametrize("remove_comments", [True, False])
def test_shebang_preserves_following_code(runtime_name, remove_comments, tmp_path):
    runtime = shutil.which(runtime_name)
    if runtime is None:
        pytest.skip(f"{runtime_name} runtime unavailable")
    source = '#!/usr/bin/lua\nprint(42, "#!/literal")\n'
    output = Minifier(MinifyOptions(remove_comments=remove_comments)).minify(source).output
    for name, program in (("original", source), ("minified", output)):
        path = tmp_path / f"{name}.lua"
        path.write_text(program)
        result = subprocess.run([runtime, str(path)], capture_output=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"42\t#!/literal\n"
    assert output.startswith("#!/usr/bin/lua\n")


@pytest.mark.skipif(os.name != "posix", reason="direct interpreter directives require POSIX")
def test_default_minification_retains_directly_executable_script(tmp_path):
    runtime = shutil.which("lua")
    if runtime is None:
        pytest.skip("lua runtime unavailable")
    source = f"#!{runtime}\nprint(42)\n"
    output = Minifier().minify(source).output
    for name, program in (("original", source), ("minified", output)):
        path = tmp_path / f"{name}.lua"
        path.write_text(program)
        path.chmod(0o700)
        result = subprocess.run([str(path)], capture_output=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"42\n"


def test_shebang_keeps_original_layout_when_requested():
    source = "#!/usr/bin/lua\r\nprint( 42 )\r\n"
    options = MinifyOptions(remove_comments=False, remove_whitespace=False)
    assert Minifier(options).minify(source).output == source


def test_hash_bang_is_not_a_comment_after_the_first_byte():
    tokens = Lexer(" #!not-a-directive\n").tokenize()
    assert not any(t.type in (TokenType.COMMENT, TokenType.LONG_COMMENT) for t in tokens)
