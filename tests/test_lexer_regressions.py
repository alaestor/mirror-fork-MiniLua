"""Regression coverage for lexer errors and source-preserving literals."""

import pytest

from lua_minifier.core import Minifier, MinifyError
from lua_minifier.core.lexer import Lexer, LexerError, TokenType


@pytest.mark.parametrize("source", ['"', "'", 'return "hello', "return 'hello", '"hello\\', '"hello\\"'])
def test_unterminated_short_string_is_rejected(source):
    with pytest.raises(LexerError, match="Unfinished string"):
        Lexer(source).tokenize()
    with pytest.raises(MinifyError, match="Unfinished string"):
        Minifier().minify(source)


@pytest.mark.parametrize("source", ['""', "''", r'"hello\""', r"'hello\\'"])
def test_closed_short_string_is_preserved(source):
    tokens = Lexer(source).tokenize()
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source
    assert tokens[1].type == TokenType.EOF


LINE_ENDINGS = ['\n', '\r', '\r\n', '\n\r']


@pytest.mark.parametrize('ending', LINE_ENDINGS)
def test_line_comment_stops_before_all_lua_line_endings(ending):
    source = '-- comment' + ending + 'print(1)'
    tokens = Lexer(source).tokenize()
    assert tokens[0].value == '-- comment'
    assert tokens[1].type == TokenType.NEWLINE
    assert tokens[1].value == ending
    assert (tokens[2].value, tokens[2].line, tokens[2].col) == ('print', 2, 1)
    assert Minifier().minify(source).output.strip() == 'print(1)'


@pytest.mark.parametrize('ending', LINE_ENDINGS)
def test_unescaped_line_ending_in_short_string_is_rejected(ending):
    with pytest.raises(LexerError, match='Unfinished string'):
        Lexer('"hello' + ending + 'world"').tokenize()


@pytest.mark.parametrize('ending', LINE_ENDINGS)
def test_escaped_line_ending_in_short_string_is_preserved(ending):
    source = '"hello\\' + ending + 'world" next'
    tokens = Lexer(source).tokenize()
    assert tokens[0].value == source[:-5]
    assert (tokens[2].value, tokens[2].line, tokens[2].col) == ('next', 2, 8)


def test_consecutive_line_pairs_and_long_comments_track_locations():
    tokens = Lexer('--[=[a\r\nb\n\rc]=]\r\n\r\nnext').tokenize()
    assert (tokens[-2].value, tokens[-2].line, tokens[-2].col) == ('next', 5, 1)


@pytest.mark.parametrize('ending', LINE_ENDINGS)
def test_line_comment_minification_preserves_lua_execution(ending):
    import shutil
    import subprocess

    lua = shutil.which('lua')
    if lua is None:
        pytest.skip('Lua runtime is not installed')
    source = '-- comment' + ending + 'print(1)'
    output = Minifier().minify(source).output
    for program in (source, output):
        result = subprocess.run([lua, '-'], input=program.encode(), capture_output=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert result.stdout == b'1\n'


@pytest.mark.parametrize('ending', LINE_ENDINGS)
def test_z_escape_consumes_multiline_whitespace_without_ending_string(ending):
    source = '"left\\z \t\v\f' + ending + '\t right" next'
    tokens = Lexer(source).tokenize()
    assert tokens[0].type == TokenType.STRING
    assert tokens[0].value == source[:-5]
    assert (tokens[2].value, tokens[2].line) == ('next', 2)


def test_escaped_backslash_does_not_enable_z_whitespace_skipping():
    with pytest.raises(LexerError, match='Unfinished string'):
        Lexer('"left\\\\z\nright"').tokenize()


def test_z_escape_stops_at_first_non_whitespace_character():
    with pytest.raises(LexerError, match='Unfinished string'):
        Lexer('"left\\z  right\n"').tokenize()


@pytest.mark.parametrize('literal', ['0b1010', '0B1010', '0b10_10', '0b0', '0b1_000_000'])
def test_luau_binary_literal_is_one_number(literal):
    tokens = Lexer(literal).tokenize()
    assert [(t.type, t.value) for t in tokens] == [
        (TokenType.NUMBER, literal), (TokenType.EOF, '')
    ]


INTERPOLATIONS = [
    '`hello  world {x}`',
    '`hello -- world`',
    r'`escaped \` and \{ and \\ {x}`',
    '`table {({a={b=4}}).a.b} done`',
    '`quote {"}" .. \'{\'} done`',
    '`long {[=[} ` {]=]} done`',
    '`nested {`inner {x} -- text`} done`',
    '`comment {x -- } ` is ignored\n + 1} done`',
    '`comment {x --[=[ } ` { ]=]\n + 1} done`',
]


@pytest.mark.parametrize('literal', INTERPOLATIONS)
def test_interpolated_literal_preserves_raw_text_as_one_token(literal):
    tokens = Lexer(literal + ' next').tokenize()
    assert tokens[0].type.name == 'INTERPOLATED_STRING'
    assert tokens[0].value == literal
    assert tokens[2].value == 'next'


@pytest.mark.parametrize('literal', ['`hello', '`hello {x', '`hello {"}"}', '`hello {`nested`'])
def test_unterminated_interpolated_literal_is_rejected(literal):
    with pytest.raises(LexerError, match='Unfinished interpolated string'):
        Lexer(literal).tokenize()


@pytest.mark.parametrize(('literal', 'expected'), list(zip(INTERPOLATIONS, [
    b'hello  world 3\n',
    b'hello -- world\n',
    b'escaped ` and { and \\ 3\n',
    b'table 4 done\n',
    b'quote }{ done\n',
    b'long } ` { done\n',
    b'nested inner 3 -- text done\n',
    b'comment 4 done\n',
    b'comment 4 done\n',
])))
def test_luau_interpolation_preserves_execution(literal, expected, tmp_path):
    _assert_luau_minification('local x=3; print(' + literal + ')', expected, tmp_path)


def test_luau_binary_literals_preserve_execution(tmp_path):
    _assert_luau_minification('print(0b1010, 0B1010, 0b10_10, 0b0, 0b1_000_000)',
                              b'10\t10\t10\t0\t64\n', tmp_path)


def _assert_luau_minification(source, expected, tmp_path):
    import shutil
    import subprocess
    from lua_minifier.core import MinifyOptions

    luau = shutil.which('luau')
    if luau is None:
        pytest.skip('Luau runtime is not installed')
    outputs = [source]
    for rename in (False, True):
        outputs.append(Minifier(MinifyOptions(rename_locals=rename)).minify(source).output)
    for index, program in enumerate(outputs):
        path = tmp_path / f'case{index}.luau'
        path.write_text(program)
        result = subprocess.run([luau, str(path)], capture_output=True, timeout=3)
        assert result.returncode == 0, result.stderr
        assert result.stdout == expected


def test_interpolation_refuses_renaming_atomically(tmp_path):
    import os
    import shutil
    import subprocess
    from lua_minifier.core import MinifyOptions

    runtime = os.environ.get("MINILUA_TEST_LUAU") or shutil.which("luau")
    if runtime is None:
        pytest.skip("Luau runtime is unavailable")
    from lua_minifier.core.lexer import Lexer
    from lua_minifier.core.renamer import RenamerError, VariableRenamer

    source = 'local longVariable=3; print(`value {longVariable}`)'
    tokens = Lexer(source).tokenize()
    with pytest.raises(RenamerError, match="interpolated"):
        VariableRenamer(tokens).rename()
    result = Minifier(MinifyOptions(rename_locals=True)).minify(source)
    assert result.errors and result.errors[0].startswith("Renamer warning:")
    for name, program in (("original", source), ("minified", result.output)):
        path = tmp_path / f"{name}.luau"
        path.write_text(program)
        process = subprocess.run([runtime, str(path)], capture_output=True, timeout=3)
        assert process.returncode == 0, process.stderr
        assert process.stdout == b"value 3\n"



@pytest.mark.parametrize('operator', ['//=', '..='])
def test_luau_three_character_compound_operator_is_one_token(operator):
    tokens = Lexer(operator).tokenize()
    assert [(t.type, t.value) for t in tokens] == [
        (TokenType.OP, operator), (TokenType.EOF, '')
    ]


@pytest.mark.parametrize(('source', 'expected'), [
    ('local x=9; x //= 2; print(x)', b'4\n'),
    ('local x="a"; x ..= "b"; print(x)', b'ab\n'),
    ('print(9 // 2)', b'4\n'),
    ('print("a" .. "b")', b'ab\n'),
])
def test_luau_compound_and_normal_operators_preserve_execution(source, expected, tmp_path):
    _assert_luau_minification(source, expected, tmp_path)
