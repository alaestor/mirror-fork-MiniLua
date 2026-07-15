"""
Variable Renamer
Renames local variables and function parameters to short generated names.

Architecture:
  - Pass 1 (collect): builds a full scope TREE with all local→short mappings
  - Pass 2 (substitute): navigates the same tree to replace NAME tokens

The scope tree is built once and shared — this avoids the "fresh child scope"
bug where substitute-pass scopes had no knowledge of collect-pass mappings.
"""

from typing import List, Dict, Set, Optional
from .lexer import Token, TokenType, LUA_KEYWORDS


# ------------------------------------------------------------------ #
#  Protected name registry                                           #
# ------------------------------------------------------------------ #

_PROTECTED_GLOBALS: Set[str] = {
    # Lua standard library
    "print", "pairs", "ipairs", "next", "select", "type", "tostring",
    "tonumber", "error", "assert", "pcall", "xpcall", "rawget", "rawset",
    "rawequal", "rawlen", "setmetatable", "getmetatable", "unpack",
    "table", "string", "math", "io", "os", "coroutine", "package",
    "require", "load", "loadfile", "dofile", "collectgarbage",
    "module", "arg", "_G", "_VERSION", "_ENV",
    
    # Lua 5.4
    "utf8", "warn",
    
    # Luau built-ins
    "bit32", "buffer", "task", "game", "script", "workspace",
    "Instance", "Vector3", "Vector2", "Vector2int16", "Vector3int16",
    "CFrame", "Color3", "BrickColor", "UDim", "UDim2",
    "Enum", "Ray", "Region3", "Region3int16",
    "TweenInfo", "NumberSequence", "NumberSequenceKeypoint",
    "ColorSequence", "ColorSequenceKeypoint",
    "NumberRange", "PhysicalProperties", "Rect", "Random",
    "Axes", "Faces", "Font", "DateTime", "RBXScriptSignal",
    "tick", "time", "elapsedTime", "wait", "delay", "spawn",
    "typeof", "shared", "plugin", "settings", "UserSettings",
    
    # Roblox services / classes
    "Humanoid", "BasePart", "Model", "Part", "MeshPart",
    "RemoteEvent", "RemoteFunction", "BindableEvent", "BindableFunction",
    "Players", "ReplicatedStorage", "ServerStorage", "ServerScriptService",
    "StarterGui", "StarterPack", "StarterPlayer", "Lighting",
    "RunService", "TweenService", "UserInputService", "PathfindingService",
    "HttpService", "DataStoreService", "MarketplaceService",
    "SoundService", "ChatService", "Teams", "BadgeService",
    
    # Executor functions
    "getrawmetatable", "setrawmetatable", "hookmetamethod",
    "hookfunction", "newcclosure", "newlclosure",
    "checkcaller", "islclosure", "iscclosure", "isexecutorclosure",
    "clonefunction", "cloneref",
    "getgenv", "getsenv", "getrenv", "getfenv", "setfenv",
    "gethui", "getcallingscript",
    "getscripts", "getloadedmodules", "getinstances", "getnilinstances",
    "getconnections", "getboundingbox",
    "firesignal", "fireclickdetector", "firetouchinterest",
    "fireproximityprompt", "fireremote",
    "getproto", "getprotos", "getupvalue", "getupvalues",
    "setupvalue", "getinfo", "debug",
    "readfile", "writefile", "appendfile", "listfiles",
    "makefolder", "delfolder", "delfile", "isfile", "isfolder",
    "request", "http_request", "http", "syn",
    "Drawing", "cleardrawcache", "getrenderproperty",
    "setrenderproperty", "isrenderobj", "createdrawing",
    "crypt", "base64encode", "base64decode", "base64",
    "messagebox", "setclipboard", "getclipboard", "toclipboard",
    "identifyexecutor", "whatexecutor", "getexecutorname",
    "getscriptname", "getscriptbytecode", "getscripthash", "getscriptclosure",
    "decompile", "loadbytecode",
    "protectgui", "unprotectgui",
    "getgc", "getmemoryusage",
    "mouse1click", "mouse1press", "mouse1release",
    "mouse2click", "mouse2press", "mouse2release",
    "mousemoveabs", "mousemoverel", "mousescroll",
    "keypress", "keyrelease", "keyclick",
    "setfflag", "getfflag", "setfastflag",
    "getobjects", "getsimpleid", "getnamecallmethod", "setnamecallmethod",
    "isnetworkowner", "sethiddenproperty", "gethiddenproperty",
    "getspecialinfo", "compareinstances",
    "rconsoleprint", "rconsolewarn", "rconsoleerr",
    "rconsolename", "rconsoleclear", "rconsolecreate", "rconsoledestroy",
    "consolecreate", "consoledestroy", "consoleprint", "consoleclear",
    "setthreadidentity", "getthreadidentity", "setsimulationradius",
    "getscriptthread", "getthreadcontext",
    "isluau", "getluauflags",
    
    # Metamethods
    "__index", "__newindex", "__call", "__tostring", "__len",
    "__eq", "__lt", "__le", "__add", "__sub", "__mul", "__div",
    "__mod", "__pow", "__unm", "__concat", "__idiv", "__band",
    "__bor", "__bxor", "__bnot", "__shl", "__shr",
    "__gc", "__close", "__mode", "__name",
}

_TRIVIA = frozenset({
    TokenType.SPACE, TokenType.NEWLINE,
    TokenType.COMMENT, TokenType.LONG_COMMENT,
})


# ------------------------------------------------------------------ #
#  Scope node                                                        #
# ------------------------------------------------------------------ #

class Scope:
    """
    A single lexical scope.  Children are appended in source order
    and consumed in the same order by the substitute pass.
    """
    __slots__ = ("parent", "locals", "children", "_child_idx")

    def __init__(self, parent: Optional["Scope"] = None):
        self.parent:    Optional["Scope"]  = parent
        self.locals:    Dict[str, str]     = {}   # original → short
        self.children:  List["Scope"]      = []
        self._child_idx: int               = 0    # used by substitute pass

    # Mutation
    def add_child(self) -> "Scope":
        child = Scope(self)
        self.children.append(child)
        return child

    def define(self, original: str, short: str) -> None:
        self.locals[original] = short

    # Lookup
    def lookup(self, name: str) -> Optional[str]:
        scope: Optional[Scope] = self
        while scope is not None:
            if name in scope.locals:
                return scope.locals[name]
            scope = scope.parent
        return None

    # Child navigation (substitute pass)
    def next_child(self) -> "Scope":
        child = self.children[self._child_idx]
        self._child_idx += 1
        return child

    def reset_child_cursor(self) -> None:
        self._child_idx = 0


# ------------------------------------------------------------------ #
#  Name generator                                                    #
# ------------------------------------------------------------------ #

def _name_generator():
    """
    Yields: a, b, …, z, aa, ab, …
    """
    import string
    alpha = string.ascii_lowercase
    n = 1
    while True:
        indices = [0] * n
        while True:
            yield "".join(alpha[i] for i in indices)
            pos = n - 1
            while pos >= 0:
                indices[pos] += 1
                if indices[pos] < len(alpha):
                    break
                indices[pos] = 0
                pos -= 1
            else:
                break
        n += 1


# ------------------------------------------------------------------ #
#  VariableRenamer                                                   #
# ------------------------------------------------------------------ #

def _skip_trivia(toks: List[Token], j: int, n: int) -> int:
    while j < n and toks[j].type in _TRIVIA:
        j += 1
    return j


class VariableRenamer:
    """
    Scope-aware two-pass local variable renamer.

    Pass 1 (collect)   — builds a complete Scope tree with all local→short mappings.
    Pass 2 (substitute)— navigates the SAME tree and replaces NAME token values.

    Sharing the tree between passes is the key correctness guarantee:
    no name substitution can use a scope-level that wasn't populated by collect.
    """

    def __init__(self, tokens: List[Token], preserve_names: Optional[Set[str]] = None):
        self.tokens  = tokens
        self.n       = len(tokens)
        self.preserve: Set[str] = (
            (preserve_names or set()) | LUA_KEYWORDS | _PROTECTED_GLOBALS
        )
        self._gen  = _name_generator()
        self._used: Set[str] = set()

    # Public
    def rename(self) -> List[Token]:
        root = self._collect()
        root.reset_child_cursor()
        for child in self._all_scopes(root):
            child.reset_child_cursor()
        return self._substitute(root)

    # Helpers

    def _alloc(self) -> str:
        """
        Allocate the next unique short name.
        """
        while True:
            name = next(self._gen)
            if name not in self.preserve and name not in self._used:
                self._used.add(name)
                return name

    def _define(self, scope: Scope, original: str) -> None:
        """
        Assign a fresh short name to *original* in *scope*.
        Always creates a new mapping even if *original* is shadowed
        from an outer scope (correct shadowing behaviour).
        """
        if original in self.preserve:
            return
        scope.define(original, self._alloc())

    def _all_scopes(self, root: Scope):
        """
        BFS / DFS iterator over every scope in the tree.
        """
        stack = list(root.children)
        while stack:
            s = stack.pop()
            yield s
            stack.extend(s.children)

    # Pass 1: Collect

    def _collect(self) -> Scope:
        """
        Walk tokens, maintain a scope stack, and populate the scope tree
        with original→short mappings for every local declaration.
        """
        toks = self.tokens
        n    = self.n
        root = Scope()
        stack: List[Scope] = [root]

        def cur() -> Scope:
            return stack[-1]

        def push_child() -> Scope:
            child = cur().add_child()
            stack.append(child)
            return child

        def pop() -> None:
            if len(stack) > 1:
                stack.pop()

        i = 0
        while i < n:
            tok = toks[i]

            if tok.type != TokenType.KEYWORD:
                i += 1
                continue

            kw = tok.value

            # Plain scope openers
            if kw in ("do", "then", "repeat"):
                push_child()

            # function
            elif kw == "function":
                fn_scope = push_child()

                j = _skip_trivia(toks, i + 1, n)

                # Skip optional function name chain (A.B:C)
                while j < n and toks[j].type == TokenType.NAME:
                    j += 1
                    j = _skip_trivia(toks, j, n)
                    if j < n and toks[j].value in (".", ":"):
                        j += 1
                        j = _skip_trivia(toks, j, n)
                    else:
                        break

                # Parse parameter list  '(' param {',' param} [, '...'] ')'
                j = _skip_trivia(toks, j, n)
                if j < n and toks[j].value == "(":
                    j += 1
                    while j < n and toks[j].value != ")":
                        t = toks[j]
                        if t.type == TokenType.NAME:
                            self._define(fn_scope, t.value)
                        j += 1

            # for
            elif kw == "for":
                for_scope = push_child()
                j = _skip_trivia(toks, i + 1, n)
                while j < n and toks[j].value not in ("=", "in", "do"):
                    t = toks[j]
                    if t.type == TokenType.NAME:
                        self._define(for_scope, t.value)
                    j += 1

            # end / until
            elif kw in ("end", "until"):
                pop()

            # local
            elif kw == "local":
                j = _skip_trivia(toks, i + 1, n)

                if j < n and toks[j].type == TokenType.KEYWORD \
                        and toks[j].value == "function":
                    # "local function Name" — Name goes into CURRENT scope.
                    # The 'function' keyword will push its own child scope
                    # (for the body/params) on the next loop iteration.
                    j2 = _skip_trivia(toks, j + 1, n)
                    if j2 < n and toks[j2].type == TokenType.NAME:
                        self._define(cur(), toks[j2].value)
                else:
                    # "local a, b, c = ..."
                    while j < n:
                        t = toks[j]
                        if t.type in _TRIVIA or t.value == ",":
                            j += 1
                            continue
                        if t.type == TokenType.NAME:
                            self._define(cur(), t.value)
                            j += 1
                        elif t.value == "...":
                            j += 1
                        else:
                            break   # hit '=' or expression start

            i += 1

        return root

    # Pass 2: Substitute

    def _substitute(self, root: Scope) -> List[Token]:
        """
        Walk tokens again, navigating the pre-built scope tree.
        Replace NAME token values with their mapped short names.
        """
        toks   = self.tokens
        n      = self.n
        stack: List[Scope] = [root]
        result: List[Token] = []

        def cur() -> Scope:
            return stack[-1]

        def push_next_child() -> None:
            # Consume the next child scope from current scope's list.
            child = cur().next_child()
            stack.append(child)

        def pop() -> None:
            if len(stack) > 1:
                stack.pop()

        i = 0
        while i < n:
            tok = toks[i]

            if tok.type == TokenType.KEYWORD:
                kw = tok.value
                if kw in ("do", "then", "repeat", "function", "for"):
                    push_next_child()
                elif kw in ("end", "until"):
                    pop()

            if tok.type == TokenType.NAME:
                renamed = cur().lookup(tok.value)
                if renamed is not None and tok.value not in self.preserve:
                    tok = Token(tok.type, renamed, tok.line, tok.col)

            result.append(tok)
            i += 1

        return result
