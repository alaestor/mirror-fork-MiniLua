"""Binding-aware local variable and function parameter renaming."""

from typing import List, Set, Optional
from .lexer import Token, TokenType, LUA_KEYWORDS
from .bindings import BindingParser, RenamerError


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

class VariableRenamer:
    """Rename declarations and their resolved references after a complete parse.

    Unsupported grammar raises RenamerError without changing any input tokens.
    The minifier can then retain the original names and report a warning.
    """

    def __init__(self, tokens: List[Token], preserve_names: Optional[Set[str]] = None):
        self.tokens = tokens
        self.preserve = (preserve_names or set()) | LUA_KEYWORDS | _PROTECTED_GLOBALS
        self._gen = _name_generator()
        # Reserve every source identifier, including free and unchanged names.
        self._used = {token.value for token in tokens
                      if token.type in {TokenType.NAME, TokenType.KEYWORD}}

    def rename(self) -> List[Token]:
        bindings = BindingParser(self.tokens).parse()
        replacements = {}
        for binding in bindings:
            if binding.implicit or binding.name in self.preserve:
                continue
            short = self._alloc()
            for index in binding.occurrences:
                replacements[index] = short
        return [Token(token.type, replacements[i], token.line, token.col)
                if i in replacements else token
                for i, token in enumerate(self.tokens)]

    def _alloc(self) -> str:
        while True:
            name = next(self._gen)
            if name not in self.preserve and name not in self._used:
                self._used.add(name)
                return name
