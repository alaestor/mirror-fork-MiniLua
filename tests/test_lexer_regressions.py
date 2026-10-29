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
