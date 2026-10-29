"""
Lua/Luau Lexer
Tokenizes source code into a stream of tokens for processing.
Supports Lua 5.1–5.4 and Luau (Roblox) syntax.
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    # Literals
    NUMBER      = auto()
    STRING      = auto()
    INTERPOLATED_STRING = auto()
    NAME        = auto()
    
    # Keywords
    KEYWORD     = auto()
    
    # Operators & punctuation
    OP          = auto()
    
    # Whitespace & structure
    NEWLINE     = auto()
    SPACE       = auto()
    
    # Comments
    COMMENT     = auto()
    LONG_COMMENT = auto()
    
    # Long strings
    LONG_STRING = auto()
    
    # Special
    EOF         = auto()


# All Lua 5.1–5.4 + Luau keywords
LUA_KEYWORDS = frozenset({
    "and", "break", "do", "else", "elseif", "end", "false", "for",
    "function", "goto", "if", "in", "local", "nil", "not", "or",
    "repeat", "return", "then", "true", "until", "while",
    # Luau extras
    "continue", "export", "type",
})


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, {self.line}:{self.col})"


class LexerError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(f"[Lexer] Line {line}, Col {col}: {msg}")
        self.line = line
        self.col = col


class Lexer:
    """
    Tokenizes Lua/Luau source into a list of Token objects.
    Preserves all tokens (including whitespace and comments)
    so the minifier can selectively remove what it wants.
    """

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self._newline_pending = ""
        self.tokens: List[Token] = []

    # ------------------------------------------------------------------ #
    #  Public API                                                        #
    # ------------------------------------------------------------------ #

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            tok = self._next_token()
            if tok:
                self.tokens.append(tok)
        self.tokens.append(Token(TokenType.EOF, "", self.line, self.col))
        return self.tokens

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                  #
    # ------------------------------------------------------------------ #

    def _peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        return self.source[idx] if idx < len(self.source) else ""

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch in "\r\n":
            if self._newline_pending and ch != self._newline_pending:
                self._newline_pending = ""
            else:
                self.line += 1
                self._newline_pending = ch
            self.col = 1
        else:
            self._newline_pending = ""
            self.col += 1
        return ch

    def _match(self, expected: str) -> bool:
        if self.source[self.pos:self.pos + len(expected)] == expected:
            for _ in expected:
                self._advance()
            return True
        return False

    # ------------------------------------------------------------------ #
    #  Token dispatch                                                    #
    # ------------------------------------------------------------------ #

    def _next_token(self) -> Optional[Token]:
        start_line, start_col = self.line, self.col
        ch = self._peek()

        # Whitespace
        if ch in " \t\v\f":
            return self._read_spaces(start_line, start_col)

        if ch in "\r\n":
            value = self._advance()
            if self._peek() in ("\r", "\n") and self._peek() != ch:
                value += self._advance()
            return Token(TokenType.NEWLINE, value, start_line, start_col)

        # Comments / long strings starting with '-' or '['
        if ch == "-" and self._peek(1) == "-":
            return self._read_comment(start_line, start_col)

        # Long strings
        if ch == "[" and self._peek(1) in ("[", "="):
            level = self._check_long_bracket()
            if level >= 0:
                return self._read_long_string(start_line, start_col, level)

        # Strings
        if ch in ('"', "'"):
            return self._read_short_string(start_line, start_col)

        if ch == "`":
            return self._read_interpolated_string(start_line, start_col)

        # Numbers
        if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
            return self._read_number(start_line, start_col)

        # Names / keywords
        if ch.isalpha() or ch == "_":
            return self._read_name(start_line, start_col)

        # Multi-char operators (check 3-char BEFORE 2-char to avoid prefix clash)
        three = self.source[self.pos:self.pos + 3]
        if three in {"...", "//=", "..="}:
            self._advance(); self._advance(); self._advance()
            return Token(TokenType.OP, three, start_line, start_col)

        two = self.source[self.pos:self.pos + 2]
        if two in {"..", "//", "==", "~=", "<=", ">=", "<<", ">>", "->", "::", "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|="}:
            self._advance(); self._advance()
            return Token(TokenType.OP, two, start_line, start_col)

        # Single-char operator / punctuation
        self._advance()
        return Token(TokenType.OP, ch, start_line, start_col)

    # ------------------------------------------------------------------ #
    #  Readers                                                           #
    # ------------------------------------------------------------------ #

    def _read_spaces(self, line: int, col: int) -> Token:
        buf = []
        while self.pos < len(self.source) and self._peek() in " \t\v\f":
            buf.append(self._advance())
        return Token(TokenType.SPACE, "".join(buf), line, col)

    def _read_comment(self, line: int, col: int) -> Token:
        # consume '--'
        self._advance(); self._advance()

        # long comment?
        if self._peek() == "[":
            level = self._check_long_bracket()
            if level >= 0:
                content = self._read_long_bracket_content(level)
                return Token(TokenType.LONG_COMMENT, "--" + content, line, col)

        # short comment: read until end of line
        buf = ["--"]
        while self.pos < len(self.source) and self._peek() not in "\r\n":
            buf.append(self._advance())
        return Token(TokenType.COMMENT, "".join(buf), line, col)

    def _check_long_bracket(self) -> int:
        """Return bracket level (0, 1, 2, …) or -1 if not a long bracket."""
        if self._peek() != "[":
            return -1
        i = 1
        while self.pos + i < len(self.source) and self.source[self.pos + i] == "=":
            i += 1
        if self.pos + i < len(self.source) and self.source[self.pos + i] == "[":
            return i - 1
        return -1

    def _read_long_bracket_content(self, level: int) -> str:
        """Consume [=*[ ... ]=*] and return the full raw text including brackets."""
        open_br = "[" + "=" * level + "["
        close_br = "]" + "=" * level + "]"
        buf = [open_br]
        for _ in open_br:
            self._advance()
        while self.pos < len(self.source):
            if self.source[self.pos:self.pos + len(close_br)] == close_br:
                buf.append(close_br)
                for _ in close_br:
                    self._advance()
                return "".join(buf)
            buf.append(self._advance())
        raise LexerError("Unfinished long bracket", self.line, self.col)

    def _read_long_string(self, line: int, col: int, level: int) -> Token:
        content = self._read_long_bracket_content(level)
        return Token(TokenType.LONG_STRING, content, line, col)

    def _read_short_string(self, line: int, col: int) -> Token:
        quote = self._advance()
        buf = [quote]
        while self.pos < len(self.source):
            ch = self._peek()
            if ch == "\\" :
                buf.append(self._advance())  # backslash
                if self.pos < len(self.source):
                    escaped = self._advance()
                    buf.append(escaped)
                    if escaped == "z":
                        while self.pos < len(self.source) and self._peek() in " \t\v\f\r\n":
                            buf.append(self._advance())
                    if escaped in "\r\n" and self._peek() in ("\r", "\n") and self._peek() != escaped:
                        buf.append(self._advance())
                continue
            if ch == quote:
                buf.append(self._advance())
                return Token(TokenType.STRING, "".join(buf), line, col)
            if ch in "\r\n":
                raise LexerError("Unfinished string", self.line, self.col)
            buf.append(self._advance())
        raise LexerError("Unfinished string", line, col)

    def _read_interpolated_string(self, line: int, col: int) -> Token:
        """Keep literal text and embedded expressions intact, including trivia.

        Expressions use normal token readers so braces inside quotes, nested
        interpolations, long brackets, and comments cannot close an expression.
        """
        start = self.pos
        self._advance()
        while self.pos < len(self.source):
            ch = self._advance()
            if ch == "\\":
                if self.pos < len(self.source):
                    self._advance()
            elif ch == "`":
                return Token(TokenType.INTERPOLATED_STRING, self.source[start:self.pos], line, col)
            elif ch == "{":
                depth = 1
                while depth and self.pos < len(self.source):
                    tok = self._next_token()
                    if tok.type == TokenType.OP:
                        if tok.value == "{":
                            depth += 1
                        elif tok.value == "}":
                            depth -= 1
                if depth:
                    raise LexerError("Unfinished interpolated string expression", line, col)
        raise LexerError("Unfinished interpolated string", line, col)

    def _read_number(self, line: int, col: int) -> Token:
        buf = []
        # Luau binary integers. Preserve spelling for the literal transformer.
        if self._peek() == "0" and self._peek(1) in ("b", "B"):
            buf.extend((self._advance(), self._advance()))
            while self.pos < len(self.source) and self._peek() in "01_":
                buf.append(self._advance())
            return Token(TokenType.NUMBER, "".join(buf), line, col)
        # Hex
        if self._peek() == "0" and self._peek(1) in ("x", "X"):
            buf.append(self._advance())
            buf.append(self._advance())
            while self.pos < len(self.source) and (self._peek() in "0123456789abcdefABCDEF_"):
                buf.append(self._advance())
            # hex float
            if self.pos < len(self.source) and self._peek() == ".":
                buf.append(self._advance())
                while self.pos < len(self.source) and (self._peek() in "0123456789abcdefABCDEF_"):
                    buf.append(self._advance())
            if self.pos < len(self.source) and self._peek() in ("p", "P"):
                buf.append(self._advance())
                if self.pos < len(self.source) and self._peek() in ("+", "-"):
                    buf.append(self._advance())
                while self.pos < len(self.source) and (self._peek().isdigit() or self._peek() == "_"):
                    buf.append(self._advance())
        else:
            while self.pos < len(self.source) and (self._peek().isdigit() or self._peek() == "_"):
                buf.append(self._advance())
            if self.pos < len(self.source) and self._peek() == ".":
                buf.append(self._advance())
                while self.pos < len(self.source) and (self._peek().isdigit() or self._peek() == "_"):
                    buf.append(self._advance())
            if self.pos < len(self.source) and self._peek() in ("e", "E"):
                buf.append(self._advance())
                if self.pos < len(self.source) and self._peek() in ("+", "-"):
                    buf.append(self._advance())
                while self.pos < len(self.source) and (self._peek().isdigit() or self._peek() == "_"):
                    buf.append(self._advance())
        return Token(TokenType.NUMBER, "".join(buf), line, col)

    def _read_name(self, line: int, col: int) -> Token:
        buf = []
        while self.pos < len(self.source) and (self._peek().isalnum() or self._peek() == "_"):
            buf.append(self._advance())
        word = "".join(buf)
        ttype = TokenType.KEYWORD if word in LUA_KEYWORDS else TokenType.NAME
        return Token(ttype, word, line, col)
