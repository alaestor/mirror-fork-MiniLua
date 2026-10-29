"""
Minifier Engine
Applies all minification passes and assembles the final output string.

Pipeline:
  1. Lex source → token list
  2. (Optional) Rename locals
  3. Strip/compress tokens
  4. Reassemble with minimal separators
"""

from dataclasses import dataclass, field
from typing import List, Optional, Set

from .lexer import Lexer, Token, TokenType, LexerError
from .string_minifier import minify_string, minify_number
from .renamer import VariableRenamer


@dataclass
class MinifyOptions:
    remove_comments:   bool          = True
    remove_whitespace: bool          = True
    minify_strings:    bool          = True
    minify_numbers:    bool          = True
    rename_locals:     bool          = False
    preserve_names:    Optional[Set] = None
    keep_newlines:     bool          = False


@dataclass
class MinifyResult:
    output:            str
    original_size:     int
    minified_size:     int
    tokens_processed:  int
    errors:            List[str] = field(default_factory=list)

    @property
    def savings_bytes(self) -> int:
        return self.original_size - self.minified_size

    @property
    def savings_pct(self) -> float:
        if self.original_size == 0:
            return 0.0
        return (self.savings_bytes / self.original_size) * 100


class MinifyError(Exception):
    pass


# Tokens considered "real" content (not trivia)
_REAL_TYPES = frozenset({
    TokenType.NUMBER, TokenType.STRING, TokenType.LONG_STRING,
    TokenType.NAME, TokenType.KEYWORD, TokenType.OP, TokenType.INTERPOLATED_STRING,
})

_COMPOUND_OPERATORS = frozenset({
    "..", "//", "==", "~=", "<=", ">=", "<<", ">>", "->", "::",
    "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|=",
})


def _is_word_char(c: str) -> bool:
    return c.isalnum() or c == "_"


def _needs_separator(a: Token, b: Token) -> bool:
    """
    Return True if a space must be inserted between tokens a and b
    to preserve syntactic validity.

    Cases that REQUIRE a space:
      • word token  followed by  word token   (keyword/name/number-alpha)
      • keyword     followed by  unary minus or unary not (would merge)
      • minus op    followed by  minus op     (would form -- comment)
      • '['         followed by  '[' or '='   (would form long-string bracket)
      • number      followed by  '..'         (would mis-lex as float field)
      • keyword     followed by  '.'          (e.g. "return.field" – fine actually,
                                               but "end.field" needs space if end
                                               were a name – end is keyword so safe)
    """
    if a.type not in _REAL_TYPES or b.type not in _REAL_TYPES:
        return False

    av = a.value
    bv = b.value

    # Two word-char tokens always need a space
    if _is_word_char(av[-1]) and _is_word_char(bv[0]):
        return True

    # A numeral can absorb dots or the start of an identifier.
    if a.type == TokenType.NUMBER and (
        bv.startswith(".") or b.type in (TokenType.NAME, TokenType.KEYWORD)
    ):
        return True

    # '-' followed by '-' → would form a comment
    if av[-1] == "-" and bv[0] == "-":
        return True

    # '[' followed by '[' or '=' → would open a long string
    if av[-1] == "[" and bv[0] in ("[", "="):
        return True

    # keyword followed by '-' (unary minus)
    # e.g. "return-1" → valid Lua, but "not-1" ambiguous in some parsers
    # Safe: always add space between keyword and operator starting with '-'
    if a.type == TokenType.KEYWORD and bv[0] == "-":
        return True

    # keyword followed by '~' (bitwise not / unary)
    if a.type == TokenType.KEYWORD and bv[0] == "~":
        return True

    # '=' or comparison ops followed by '-'
    # "x =- 1" should stay "x=-1" — that's fine (unary minus after =)
    # but "if x then-1" → "then-1" - keyword+minus → handled above

    # '.' followed by '.' (single dot then another)
    # prevents accidentally forming ".." or "..."
    if av[-1] == "." and bv[0] == ".":
        return True

    # e.g. an attribute's closing '>' followed by assignment '='.
    if a.type == b.type == TokenType.OP and av[-1] + bv[0] in _COMPOUND_OPERATORS:
        return True

    return False


class Minifier:
    def __init__(self, options: Optional[MinifyOptions] = None):
        self.options = options or MinifyOptions()

    def minify(self, source: str) -> MinifyResult:
        if not source:
            return MinifyResult(
                output="\n",
                original_size=0,
                minified_size=1,
                tokens_processed=0,
            )

        original_size = len(source.encode("utf-8", errors="surrogateescape"))
        errors: List[str] = []

        # Lex
        try:
            tokens = Lexer(source).tokenize()
        except LexerError as e:
            raise MinifyError(str(e)) from e

        tokens_processed = len(tokens)

        # Rename locals (optional)
        if self.options.rename_locals:
            try:
                tokens = VariableRenamer(tokens, self.options.preserve_names).rename()
            except Exception as e:
                errors.append(f"Renamer warning: {e}")

        # Transform tokens
        tokens = self._transform(tokens, errors)

        # Assemble
        output = self._assemble(tokens)

        minified_size = len(output.encode("utf-8", errors="surrogateescape"))
        return MinifyResult(
            output=output,
            original_size=original_size,
            minified_size=minified_size,
            tokens_processed=tokens_processed,
            errors=errors,
        )

    # ------------------------------------------------------------------ #
    #  Transform pass                                                    #
    # ------------------------------------------------------------------ #

    def _transform(self, tokens: List[Token], errors: List[str]) -> List[Token]:
        result: List[Token] = []
        opts = self.options

        for tok in tokens:
            if tok.type == TokenType.EOF:
                result.append(tok)
                continue

            # Comments
            if tok.type in (TokenType.COMMENT, TokenType.LONG_COMMENT):
                if opts.remove_comments:
                    continue
                result.append(tok)
                continue

            # Whitespace
            if tok.type == TokenType.SPACE:
                if opts.remove_whitespace:
                    continue
                result.append(tok)
                continue

            # Newlines
            if tok.type == TokenType.NEWLINE:
                if opts.remove_whitespace and not opts.keep_newlines:
                    continue
                result.append(tok)
                continue

            # String literals
            if tok.type == TokenType.STRING and opts.minify_strings:
                try:
                    new_val = minify_string(tok.value)
                    tok = Token(tok.type, new_val, tok.line, tok.col)
                except Exception as e:
                    errors.append(f"String minify warning at {tok.line}:{tok.col}: {e}")

            # Long strings
            elif tok.type == TokenType.LONG_STRING and opts.minify_strings:
                try:
                    new_val = minify_string(tok.value)
                    new_type = (TokenType.STRING
                                if new_val and new_val[0] in ('"', "'")
                                else TokenType.LONG_STRING)
                    tok = Token(new_type, new_val, tok.line, tok.col)
                except Exception as e:
                    errors.append(f"Long string minify warning at {tok.line}:{tok.col}: {e}")

            # Number literals
            elif tok.type == TokenType.NUMBER and opts.minify_numbers:
                try:
                    new_val = minify_number(tok.value)
                    if new_val:
                        tok = Token(tok.type, new_val, tok.line, tok.col)
                except Exception as e:
                    errors.append(f"Number minify warning at {tok.line}:{tok.col}: {e}")

            result.append(tok)

        return result

    # ------------------------------------------------------------------ #
    #  Assemble pass                                                     #
    # ------------------------------------------------------------------ #

    def _assemble(self, tokens: List[Token]) -> str:
        parts: List[str] = []
        prev: Optional[Token] = None   # last REAL token emitted

        for index, tok in enumerate(tokens):
            if tok.type == TokenType.EOF:
                break

            # Only newlines retained by the transform pass reach this point.
            if tok.type == TokenType.NEWLINE:
                parts.append(tok.value)
                prev = None   # newline acts as implicit separator
                continue

            # A kept short comment needs a terminator if its newline was removed.
            # Long comments already delimit themselves and need no extra layout.
            if tok.type in (TokenType.COMMENT, TokenType.LONG_COMMENT):
                parts.append(tok.value)
                if (tok.type == TokenType.COMMENT and
                        (index + 1 == len(tokens) or tokens[index + 1].type != TokenType.NEWLINE)):
                    parts.append("\n")
                prev = None   # reset; comment + newline acts as separator
                continue

            # Spaces kept verbatim (remove_whitespace=False)
            if tok.type == TokenType.SPACE:
                parts.append(tok.value)
                prev = None  # Existing whitespace already separates real tokens.
                continue

            # Skip remaining trivia (NEWLINE when keep_newlines=False, etc.)
            if tok.type not in _REAL_TYPES:
                continue

            # Real token — insert minimal separator if needed
            if prev is not None and _needs_separator(prev, tok):
                parts.append(" ")
            parts.append(tok.value)
            prev = tok

        result = "".join(parts)
        if not self.options.remove_whitespace or self.options.keep_newlines:
            return result if result.endswith(("\n", "\r")) else result + "\n"
        return result.rstrip("\n") + "\n"
