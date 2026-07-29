# ArbPlus — "A Really Bad Programming Language"

A hybrid scripting language with inline C, shell escapes, Python escapes, tagged binary containers, OS-level globals, string interpolation, map types, module imports, file loading, and a Python-based tree-walking interpreter.

## Quick Start

```bash
# Run any .arb file
python3 interpreter.py examples/01_hello.arb

# Pass CLI arguments
python3 interpreter.py examples/13_datatypes2.arb arg1 arg2 arg3

# Run all examples
./run_examples.sh            # Linux/macOS
powershell -ExecutionPolicy Bypass -File run_examples.ps1  # Windows
```

## What's Here

```
arbplus/
├── interpreter.py          ← The full interpreter (lexer, parser, evaluator, builtins)
├── run_examples.sh         ← Test runner (Linux/macOS)
├── run_examples.ps1        ← Test runner (Windows PowerShell)
├── examples/               ← Example .arb scripts (30 files)
│   ├── 01-08               ← v1.0 core features
│   ├── 09-23               ← v2.0 additions 1-23
│   ├── 24-27               ← v2.0 additions 24-27 (run.arb, dl.url, --clean, return/null)
│   ├── 28_py_block.arb     ← Inline Python py{ } blocks
│   ├── 29_part4_features.arb ← $! file loading, i++/k--, let[], var(), count.time
│   ├── 30_part5_features.arb ← --ErrOV, hex/RGB/OKLCH, ext_colors, file() type
│   └── mymods.arb          ← Module file used by 15_imports.arb
├── extensions/             ← Extension examples
│   ├── ext_example.py      ← Python extension (HTTP fetch, greeting, time hook)
│   ├── ext_c.c             ← C extension (double int, reverse string)
│   └── ext_cpp.cpp         ← C++ extension (average, uppercase)
└── docs/                   ← Documentation
    ├── spec.md             ← Full language specification (Steps 1-14 + all additions)
    ├── grammar.md          ← Formal EBNF grammar
    ├── usage.md            ← Usage documentation
    ├── maintenance.md       ← Manual maintenance guide
    └── implementation_notes.md ← Implementation notes
```

## Language Features (v1.0)

- **File format**: `.arb` files with metadata, declarations, overrides, functions, body
- **Types**: int, float, string, boolean, array, list, and `arb` (tagged hex container)
- **Functions**: `--Function Role.Name(args) { body }` with typed/untyped params
- **Overrides**: `--OV print myprint` creates function aliases
- **Shell escapes**: `cmd{ ... }` and `ps{ ... }` with `${var}` interpolation
- **Inline C**: `c{ ... }` blocks compiled and executed natively
- **File I/O**: readFile, writeFile, buildFile, addr.hex/binary/meta, txtRC
- **Directory ops**: dir.make/list/name/del with relative path support
- **Control flow**: if/elif/else, for (range & iterable), while, break, ternary
- **Colored I/O**: `print(text, fg: red, bg: black)` with named/hex colors
- **OS globals**: snap.time, count.time, wait, cs, locale.*, battery, network, os.*
- **Extensions**: Python, C, and C++ extensions via loadExt() with hook support

## Language Features (v2.0 Additions)

### Part 1-3 (Additions 1-27)
- **String interpolation**: `"Hello ${name}!"` — undefined vars produce empty string
- **Map type**: `map{ "key": value }` with `keys()`, `values()`, `has()` operations
- **repeat...until**: Post-test loop that always executes at least once
- **switch/case/default**: Multi-branch with colon-delimited cases
- **try/catch/finally**: Error handling with catch variable and guaranteed cleanup
- **and/or keywords**: `if (a and b or c)` alongside `&&` / `||` operators
- **/n newline token**: `print("Line 1/nLine 2")` — `//n` escapes to literal `/n`
- **Text brightness**: `print("text", b: bright)` — dim, normal, bright ANSI levels
- **Default color override**: `--OV defaults(fg,bg,b) (fg: cyan, bg: black, b: bright)`
- **Cross-type comparison**: `"42" == 42` → `true`, numeric coercion for `<`, `>`, etc.
- **Module imports**: `#import mymods;` loads `.arb` files, functions via `modname.func()`
- **CLI arguments**: `args()` returns array, `args(0)` returns first arg
- **Environment variables**: `env("HOME")` returns value or empty string
- **Random numbers**: `random()`, `randInt(min,max)`, `random.seed(n)` with reproducibility
- **open.url / open.app**: Launch browser or OS application from scripts
- **Key bindings**: `bindKey("F1", "help")` for interactive mode registration
- **run.arb()**: Execute another `.arb` script in a fresh scope with variable passing and return value
- **dl.url()**: Download a URL to disk with optional filename, auto-naming from URL path
- **--clean**: Manual GC trigger — `--clean;`, `--clean stop;`, `--clean restart;`, `--clean count;`
- **return() any type**: Functions can return int, float, string, bool, array, list, arb, map, colored strings
- **--F delegation**: `--F role.funcName(args)` — delegate return to another function
- **null keyword**: First-class `null` literal for void/empty comparisons (`x == null`)

### Part 4 (Additions 26-27 + Extras)
- **Inline Python**: `py{ ... }` — execute raw Python in the same process, stdlib-only
- **$! file loading**: `c{$!path}` / `py{$!path}` / `cmd{$!path}` — load block code from file
- **Shorthand arithmetic**: `i++` / `k--` increment and decrement statements
- **Forward declaration**: `let [name];` declares a variable as `null` for later assignment
- **var()**: `var("name")` — unquoted variable references where strings are expected
- **count.time live**: `count.time(live: true, MS: 1000)` — live updating clock mode

### Example Files (30 total)
| # | File | Demonstrates |
|---|------|-------------|
| 1-10 | `01_hello` → `10_cblock` | v1.0 core features |
| 11-23 | `11_newfeatures` → `23_composability` | v2.0 additions 1-23 |
| 24 | `24_run_arb.arb` | run.arb() with variable passing and return values |
| 25 | `25_dl_url.arb` | dl.url() downloads, auto-naming, error handling |
| 26 | `26_clean.arb` | --clean manual GC, stop/restart/count modes |
| 27 | `27_return_delegate.arb` | return() any type, --F delegation, null keyword |
| 28 | `28_py_block.arb` | py{ } inline Python, stdlib enforcement, type translation |
| 29 | `29_part4_features.arb` | $! file loading, i++/k--, let[], var(), count.time |
| 30 | `30_part5_features.arb` | --ErrOV gate, hex/RGB/OKLCH colors, ext_colors, file() type |

## Architecture

The interpreter is a single Python file with no external dependencies (Python 3.8+ stdlib only). It uses a tree-walking approach: Lexer → Parser (AST) → Evaluator. Can be bundled with PyInstaller into a standalone executable.


## Part 5 Additions (30–36)

- **--ErrOV color gate** — `--ErrOV true;` enables `--OV` color overrides for warning/error messages
- **Hex/RGB/OKLCH colors** — `#ff6600`, `rgb(100,200,50)`, `oklch(0.7,0.15,240)` in all color parameters
- **ext_colors extension** — colored output for inline language blocks, loadable via `loadExt`
- **Parser fix** — commas and `>` in `color()` arguments handled correctly
- **meta.* variables** — `meta.name`, `meta.version`, `meta()` for metadata access
- **Arb naming** — Product: ArbPlus, Language: Arb, Extension: .arb
- **file() type** — `file("path")` creates ArbFile reference for file operations
