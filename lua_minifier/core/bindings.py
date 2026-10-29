"""Parse Lua syntax and resolve local references without rewriting tokens.

This is a binding parser, not a validator or a typechecker. Unsupported syntax
raises RenamerError; callers must retain the original token stream in that case.
"""

from dataclasses import dataclass, field
from typing import List

from .lexer import Token, TokenType


class RenamerError(Exception):
    """The renamer cannot safely analyze this token stream."""


@dataclass
class Binding:
    name: str
    occurrences: List[int] = field(default_factory=list)
    implicit: bool = False


_TRIVIA = {TokenType.SPACE, TokenType.NEWLINE,
           TokenType.COMMENT, TokenType.LONG_COMMENT}
# Left and right binding powers. Exponentiation and concatenation associate right.
_BINARY = {
    "or": (1, 2), "and": (2, 3),
    "<": (3, 4), ">": (3, 4), "<=": (3, 4), ">=": (3, 4),
    "~=": (3, 4), "==": (3, 4),
    "|": (4, 5), "~": (5, 6), "&": (6, 7),
    "<<": (7, 8), ">>": (7, 8), "..": (8, 8),
    "+": (9, 10), "-": (9, 10),
    "*": (10, 11), "/": (10, 11), "//": (10, 11), "%": (10, 11),
    "^": (12, 12),
}
_END_BLOCK = {"end", "else", "elseif", "until", ""}
_COMPOUND = {"+=", "-=", "*=", "/=", "//=", "%=", "^=", "..="}


class BindingParser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.indices = [i for i, token in enumerate(tokens)
                        if token.type not in _TRIVIA]
        self.position = 0
        self.scopes = [{}]
        self.bindings = []

    def parse(self) -> List[Binding]:
        if any(t.type.name == "INTERPOLATED_STRING" for t in self.tokens):
            raise RenamerError("renaming interpolated strings is not supported")
        self.block()
        if self.token().type != TokenType.EOF:
            self.fail("unexpected token")
        return self.bindings

    def token(self, offset=0):
        position = self.position + offset
        if position >= len(self.indices):
            return Token(TokenType.EOF, "", 0, 0)
        return self.tokens[self.indices[position]]

    def value(self, offset=0):
        return self.token(offset).value

    def take(self):
        index = self.indices[self.position]
        self.position += 1
        return index

    def accept(self, value):
        if self.value() == value:
            self.take()
            return True
        return False

    def expect(self, value):
        if not self.accept(value):
            self.fail(f"expected {value!r}")

    def fail(self, message):
        token = self.token()
        raise RenamerError(f"{message} at {token.line}:{token.col}: {token.value!r}")

    def is_name(self):
        # Luau treats these as contextual keywords; Lua permits them as names.
        return (self.token().type == TokenType.NAME or
                self.value() in {"type", "export", "continue", "goto"})

    def name(self):
        if not self.is_name():
            self.fail("expected identifier")
        return self.take()

    def define(self, index, *, implicit=False):
        name = "self" if implicit else self.tokens[index].value
        binding = Binding(name, [] if implicit else [index], implicit)
        self.bindings.append(binding)
        self.scopes[-1][name] = binding
        return binding

    def reference(self, index):
        name = self.tokens[index].value
        for scope in reversed(self.scopes):
            if name in scope:
                scope[name].occurrences.append(index)
                break

    def block(self):
        while self.value() not in _END_BLOCK:
            self.statement()

    def scoped_block(self):
        self.scopes.append({})
        self.block()
        self.scopes.pop()

    def statement(self):
        value = self.value()
        if self.accept(";"):
            return
        if self.accept("local"):
            self.local()
        elif self.accept("function"):
            self.reference(self.name())
            while self.accept("."):
                self.name()
            method = self.accept(":")
            if method:
                self.name()
            self.function_body(method)
        elif self.accept("do"):
            self.scoped_block()
            self.expect("end")
        elif self.accept("while"):
            self.expression()
            self.expect("do")
            self.scoped_block()
            self.expect("end")
        elif self.accept("repeat"):
            self.scopes.append({})
            self.block()
            self.expect("until")
            self.expression()
            self.scopes.pop()
        elif self.accept("if"):
            self.expression()
            self.expect("then")
            self.scoped_block()
            while self.accept("elseif"):
                self.expression()
                self.expect("then")
                self.scoped_block()
            if self.accept("else"):
                self.scoped_block()
            self.expect("end")
        elif self.accept("for"):
            self.for_statement()
        elif self.accept("return"):
            if self.value() not in _END_BLOCK | {";"}:
                self.expressions()
            self.accept(";")
        elif value in {"break", "continue"} and self.value(1) not in {"=", "("}:
            self.take()
        elif value == "goto" and self.token(1).type == TokenType.NAME:
            self.take()
            self.name()  # Labels belong to a separate namespace.
        elif self.accept("::"):
            self.name()
            self.expect("::")
        elif value == "export" and self.value(1) == "type":
            self.fail("Luau type declarations are not supported for renaming")
        elif value == "type" and self.token(1).type == TokenType.NAME:
            self.fail("Luau type declarations are not supported for renaming")
        else:
            kind = self.prefix()
            multiple = False
            while self.accept(","):
                multiple = True
                self.prefix()
            if self.accept("="):
                self.expressions()
            elif self.value() in _COMPOUND:
                self.take()
                self.expression()
            elif multiple or kind != "call":
                self.fail("expected assignment or function call")

    def local(self):
        if self.accept("function"):
            self.define(self.name())  # Recursive local functions see themselves.
            self.function_body(False)
            return
        names = []
        while True:
            names.append(self.name())
            if self.accept("<"):
                attribute = self.name()
                if self.tokens[attribute].value not in {"const", "close"}:
                    self.fail("unsupported local attribute")
                self.expect(">")
            if self.value() == ":":
                self.fail("Luau type annotations are not supported for renaming")
            if not self.accept(","):
                break
        # Ordinary declarations begin after the entire initializer list.
        if self.accept("="):
            self.expressions()
        for index in names:
            self.define(index)

    def for_statement(self):
        names = [self.name()]
        if self.accept("="):
            self.expression()
            self.expect(",")
            self.expression()
            if self.accept(","):
                self.expression()
        else:
            while self.accept(","):
                names.append(self.name())
            self.expect("in")
            self.expressions()
        self.expect("do")
        self.scopes.append({})
        for index in names:
            self.define(index)
        self.block()
        self.scopes.pop()
        self.expect("end")

    def function_body(self, method):
        self.expect("(")
        self.scopes.append({})
        if method:
            self.define(None, implicit=True)
        if not self.accept(")"):
            while True:
                if self.accept("..."):
                    self.expect(")")
                    break
                self.define(self.name())
                if self.value() == ":":
                    self.fail("Luau typed parameters are not supported for renaming")
                if self.accept(")"):
                    break
                self.expect(",")
        if self.value() == ":":
            self.fail("Luau return annotations are not supported for renaming")
        self.block()
        self.expect("end")
        self.scopes.pop()

    def expressions(self):
        self.expression()
        while self.accept(","):
            self.expression()

    def expression(self, minimum=0):
        if self.value() in {"-", "not", "#", "~"}:
            self.take()
            self.expression(11)
        elif self.token().type in {TokenType.NUMBER, TokenType.STRING,
                                   TokenType.LONG_STRING} or self.value() in {
                                       "nil", "true", "false", "..."}:
            self.take()
        elif self.accept("function"):
            self.function_body(False)
        elif self.value() == "{":
            self.table()
        else:
            self.prefix()
        if self.value() == "::" and self.value(2) != "::":
            self.fail("Luau type assertions are not supported for renaming")
        while self.value() in _BINARY:
            left, right = _BINARY[self.value()]
            if left < minimum:
                break
            self.take()
            self.expression(right)

    def prefix(self):
        if self.accept("("):
            self.expression()
            self.expect(")")
            kind = "value"
        else:
            self.reference(self.name())
            kind = "variable"
        while True:
            if self.accept("."):
                self.name()  # Static member, not a local reference.
                kind = "variable"
            elif self.accept("["):
                self.expression()
                self.expect("]")
                kind = "variable"
            elif self.accept(":"):
                self.name()
                self.arguments()
                kind = "call"
            elif self.value() in {"(", "{"} or self.token().type in {
                TokenType.STRING, TokenType.LONG_STRING,
            }:
                self.arguments()
                kind = "call"
            else:
                break
        return kind

    def arguments(self):
        if self.accept("("):
            if not self.accept(")"):
                self.expressions()
                self.expect(")")
        elif self.value() == "{":
            self.table()
        elif self.token().type in {TokenType.STRING, TokenType.LONG_STRING}:
            self.take()
        else:
            self.fail("expected call arguments")

    def table(self):
        self.expect("{")
        while not self.accept("}"):
            if self.accept("["):
                self.expression()
                self.expect("]")
                self.expect("=")
                self.expression()
            elif self.is_name() and self.value(1) == "=":
                self.name()  # Record key, not a local declaration/reference.
                self.expect("=")
                self.expression()
            else:
                self.expression()
            if not (self.accept(",") or self.accept(";")):
                self.expect("}")
                break
