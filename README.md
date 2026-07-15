<div align="center">

```
   __    __     __     __   __     __     __         __  __     ______    
  /\ "-./  \   /\ \   /\ "-.\ \   /\ \   /\ \       /\ \/\ \   /\  __ \   
  \ \ \-./\ \  \ \ \  \ \ \-.  \  \ \ \  \ \ \____  \ \ \_\ \  \ \  __ \  
   \ \_\ \ \_\  \ \_\  \ \_\\"\_\  \ \_\  \ \_____\  \ \_____\  \ \_\ \_\ 
    \/_/  \/_/   \/_/   \/_/ \/_/   \/_/   \/_____/   \/_____/   \/_/\/_/ 
                                                                          
```

**A fast, accurate Lua / Luau source code minifier**

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-102%20passed-brightgreen)](#testing)

</div>

---

## Overview

**minilua** is a production-ready Lua / Luau minifier written in Python. It reduces the size of Lua source files by stripping comments, collapsing whitespace, compressing string and number literals, and optionally renaming local variables — all while preserving 100% semantic equivalence of the output.

Works with **Lua 5.1, 5.2, 5.3, 5.4** and **Luau** (Roblox), including executor/exploit environments.

**Typical savings: 40–60%** on real-world scripts.

---

## Features

| Feature | Description |
|---|---|
| **Comment removal** | Single-line (`--`) and multi-line (`--[[ ]]`) comments |
| **Whitespace stripping** | Spaces, tabs, redundant newlines |
| **String compression** | Optimal quote style, escape normalization, long→short string conversion |
| **Number compression** | `1.0→1`, `0.5→.5`, `1e+03→1e3`, `0x00FF→0xFF`, Luau `1_000→1000` |
| **Local variable renaming** | Renames locals to single-letter names (`a`, `b`, `c`, …) |
| **Executor globals protected** | `getrawmetatable`, `hookfunction`, `readfile`, `syn`, etc. are never renamed |
| **Luau support** | `type`, `continue`, `export`, `::labels::`, type annotations |
| **Safe separator logic** | Never produces `--` (comment), `[[` (long string), or merged keywords |
| **Batch processing** | Glob patterns, recursive directory scan |
| **stdin / stdout** | Pipe-friendly for build pipelines |

---

## Installation

```bash
pip install minilua
```

**Requirements:** Python 3.8+

---

## Quick Start

```bash
# Minify a single file  →  produces script.min.lua
minilua script.lua

# Minify and write to a specific path
minilua script.lua -o dist/script.lua

# Minify all files in a directory (recursive)
minilua src/ --recursive --output-dir dist/

# Print result to stdout (pipe-friendly)
minilua script.lua --stdout

# stdin → stdout
cat script.lua | minilua - --stdout
```

---

## CLI Reference

```
Usage: minilua [OPTIONS] [FILE|DIR|GLOB]...

  Lua / Luau Minifier — compress Lua source files.
  Supports Lua 5.1–5.4 and Luau (Roblox) syntax.

Input / Output:
  FILE|DIR|GLOB           One or more files, directories, or glob patterns
  -o, --output PATH       Output file path (single-file mode)
  -d, --output-dir PATH   Output directory for batch mode
  --suffix TEXT           Output filename suffix  [default: .min.lua]
  -i, --in-place          Overwrite input files in-place  ⚠ irreversible
  -r, --recursive         Recurse into subdirectories
  --stdout                Print result to stdout instead of writing files
  -f, --overwrite         Allow overwriting existing output files

Minification Options:
  --no-comments           Keep comments (default: strip)
  --no-whitespace         Keep whitespace (default: strip)
  --no-strings            Skip string literal compression
  --no-numbers            Skip number literal compression
  -R, --rename-locals     Rename local variables to short names
  --keep-newlines         Preserve one newline per statement

Display:
  -q, --quiet             Suppress all output except errors
  --no-banner             Hide the startup banner
  -v, --version           Show version and exit
  -h, --help              Show this message and exit
```

### Examples

```bash
# Rename local variables (more aggressive, ~55–70% savings)
minilua script.lua --rename-locals

# Keep comments (useful when debugging minified output)
minilua script.lua --no-comments

# Batch: minify all .lua and .luau files under src/
minilua src/ -r -d build/

# CI pipeline: fail on minification error, silent otherwise
minilua *.lua --stdout --quiet

# In-place for all files in current directory
minilua *.lua --in-place --overwrite
```

---

## Programmatic API

```python
from lua_minifier.core import Minifier, MinifyOptions

source = open("script.lua").read()

opts = MinifyOptions(
    remove_comments   = True,   # strip --comments
    remove_whitespace = True,   # strip spaces / newlines
    minify_strings    = True,   # compress string literals
    minify_numbers    = True,   # compress number literals
    rename_locals     = False,  # rename locals (opt-in)
    keep_newlines     = False,  # preserve newlines
)

result = Minifier(opts).minify(source)

print(result.output)
print(f"Original : {result.original_size:,} bytes")
print(f"Minified : {result.minified_size:,} bytes")
print(f"Saved    : {result.savings_pct:.1f}%")

if result.errors:
    for warning in result.errors:
        print("Warning:", warning)
```

### `MinifyOptions` fields

| Field | Type | Default | Description |
|---|---|---|---|
| `remove_comments` | `bool` | `True` | Strip `--` and `--[[ ]]` comments |
| `remove_whitespace` | `bool` | `True` | Strip spaces and newlines |
| `minify_strings` | `bool` | `True` | Compress string literals |
| `minify_numbers` | `bool` | `True` | Compress number literals |
| `rename_locals` | `bool` | `False` | Rename local variables |
| `preserve_names` | `set` | `None` | Extra names to never rename |
| `keep_newlines` | `bool` | `False` | Preserve one newline per line |

### `MinifyResult` fields

| Field | Type | Description |
|---|---|---|
| `output` | `str` | Minified source code |
| `original_size` | `int` | Original size in bytes |
| `minified_size` | `int` | Minified size in bytes |
| `savings_bytes` | `int` | Bytes saved |
| `savings_pct` | `float` | Percentage saved |
| `tokens_processed` | `int` | Number of tokens lexed |
| `errors` | `list[str]` | Non-fatal warnings |

---

## What Gets Compressed

### Comments
```lua
-- Before
-- This function adds two numbers
local function add(a, b)
    --[[ both arguments must be numbers ]]
    return a + b  -- return the sum
end

-- After
local function add(a,b)return a+b end
```

### String literals
```lua
-- Before
local msg = "Hello\tWorld"
local raw = [[
  multi-line content
]]
local hex = "\x68\x65\x6c\x6c\x6f"

-- After
local msg='Hello\tWorld'
local raw='  multi-line content\n'
local hex='hello'
```

### Number literals
```lua
-- Before
local a = 1.0
local b = 0.500
local c = 1e+03
local d = 0x00FF
local e = 1_000_000  -- Luau

-- After
local a=1
local b=.5
local c=1e3
local d=0xFF
local e=1000000
```

### Local variable renaming (`--rename-locals`)
```lua
-- Before
local function calculateDistance(pointA, pointB)
    local deltaX = pointA.x - pointB.x
    local deltaY = pointA.y - pointB.y
    return math.sqrt(deltaX * deltaX + deltaY * deltaY)
end

-- After
local function a(b,c)local d=b.x-c.x local e=b.y-c.y return math.sqrt(d*d+e*e)end
```

---

## Executor / Exploit Support

minilua fully recognizes executor globals and will **never rename** them when `--rename-locals` is active. The following (and more) are protected:

```
getrawmetatable    setrawmetatable    hookmetamethod
hookfunction       newcclosure        newlclosure
getgenv            getsenv            getrenv
getfenv            setfenv            gethui
readfile           writefile          appendfile
listfiles          makefolder         isfile
firesignal         fireclickdetector  fireproximityprompt
getupvalue         getupvalues        setupvalue
getproto           getprotos          getgc
syn                request            http_request
Drawing            setclipboard       getclipboard
identifyexecutor   getexecutorname    decompile
setthreadidentity  getthreadidentity  rconsoleprint
mouse1click        keypress           getconnections
... and 80+ more
```

---

## How It Works

```
Source code
     │
     ▼
┌─────────┐
│  Lexer  │  →  Full token stream (all trivia preserved)
└─────────┘
     │
     ▼
┌──────────────┐
│   Renamer    │  (optional) Two-pass scope-tree renamer
│  (Pass 1)    │  Builds lexical scope tree, assigns short names
│  (Pass 2)    │  Substitutes NAME tokens using the shared tree
└──────────────┘
     │
     ▼
┌───────────────────┐
│  Transform Pass   │
│  · Drop comments  │
│  · Drop spaces    │
│  · Compress STR   │  →  string_minifier
│  · Compress NUM   │  →  number_minifier
└───────────────────┘
     │
     ▼
┌────────────────┐
│  Assemble Pass │  Insert ' ' only where required by Lua grammar
└────────────────┘
     │
     ▼
Minified output
```

### Separator safety rules

The assembler inserts a space between two tokens **only when necessary**:

- Word token followed by word token → always needs space (`return 42`, `and b`)
- `-` followed by `-` → would form a `--` comment
- `[` followed by `[` or `=` → would open a long-bracket string
- Keyword followed by `-` or `~` → unary operator safety
- Number followed by `..` → float mis-lex prevention
- `.` followed by `.` → prevents accidental `..` formation

---

## Project Structure

```
lua_minifier/
├── __init__.py              Public API
├── cli.py                   CLI (Click-based)
├── setup.py                 Package configuration
├── README.md
│
├── core/
│   ├── __init__.py
│   ├── lexer.py             Lua/Luau tokenizer
│   ├── minifier.py          Pipeline engine & options
│   ├── string_minifier.py   String & number compression
│   └── renamer.py           Scope-tree local variable renamer
│
├── utils/
│   ├── __init__.py
│   ├── formatter.py         Terminal stats output (color-aware)
│   └── file_utils.py        File discovery, glob expansion, I/O
│
└── tests/
    ├── test_minifier.py     102-test suite
    └── sample.lua           Demo file
```

---

## Testing

```bash
python -m pytest tests/ -v
```

```
102 passed in 0.18s
```

Test coverage includes:

- Lexer tokenization (Lua 5.1–5.4, Luau syntax)
- String escape decoding/encoding (`\n`, `\xHH`, `\u{HH}`, `\ddd`, `\z`)
- Number compression (int, float, hex, hex-float, scientific, Luau separators)
- Separator correctness (no merged keywords, no accidental `--` comments)
- Comment and whitespace stripping / preservation
- Variable renamer (locals, params, for-vars, shadowing, no collisions)
- Executor global protection (80+ protected names)
- Luau-specific syntax (`continue`, `type`, `export`, `::`)
- Edge cases (empty input, deep nesting, large tables, null bytes in strings)

---

## License

MIT © Ardo
