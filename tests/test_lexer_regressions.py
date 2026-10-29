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
