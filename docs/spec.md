# ArbPlus Language Specification
## "A Really Bad Programming Language" — v1.0

---

## Step 1 — File Format & Basic Syntax

### File Structure
An `.arb` file follows this order:
```
#meta { ... }          ← metadata block (optional but recommended)
#use batch;            ← declarations (optional)
--OV print myprint;    ← overrides (optional)
--Function Role.Name() ← function definitions (optional)
<executable body>      ← main code (required)
```

### Inline C
C code is embedded via `c{ ... }` blocks. The interpreter hands the block to the system's C compiler (gcc/cc/clang) and runs the compiled output. If no compiler is found, a clear error is reported at runtime.

### Line Endings
**Primary terminator: `;`** — chosen because it's the universal statement separator across C-family languages, which ArbPlus embeds. The alternative `>` is also accepted for aesthetic variety. Mixing `;` and `>` in one file is legal; each statement simply ends at whichever terminator appears first.

### Comments
- Single-line: `//` runs until the next statement terminator (`;`, `>`) or newline
- Multi-line: `/* ... */` — can span multiple lines, can be nested

### Whitespace & Encoding
- Whitespace between tokens is ignored (spaces, tabs, newlines)
- Newlines are soft terminators — a statement continues across lines until `;` or `>`
- File encoding: UTF-8

---

## Step 2 — Program Metadata Block

### Syntax
```
#meta {
    name: "MyScript";
    version: "1.0";
    author: "Jane Doe";
    description: "A script that does things";
    image: file:./icon.png;
    dependencies: "libfoo 1.2, utils.arb 0.9";
    languages: "ArbPlus, C, batch";
}
```

### Fields

| Field | Required | Description |
|-------|----------|-------------|
| name | Yes | Program name |
| version | No | Semantic version string |
| author | No | Author name |
| description | No | Free-form summary |
| image | No | Icon — `file:path` for file reference, `base64:data` for inline |
| dependencies | No | Comma-separated list of required libraries/extensions/files with versions |
| languages | No | Comma-separated list: ArbPlus, batch, PowerShell, C, C++, Python |

### Image Tag Syntax
- File: `image: file:./assets/icon.png;`
- Base64: `image: base64:iVBORw0KGgoAAAANSUhEUg...;`

---

## Step 3 — Runtime Architecture

**Decision: The runtime is implemented in Python.**

ArbPlus ships as a single interpreter (lexer, parser, evaluator, built-in functions, OS-globals layer) written in Python 3. The interpreter interprets ArbPlus code directly and shells out to whatever toolchains are already on the user's machine for embedded pieces.

### Startup Checks
The interpreter checks for required toolchains **lazily** — only when a script actually uses a feature:
- `c{ }` blocks → checks for gcc/cc/clang via `shutil.which()`
- `cmd{ }` blocks → uses `cmd.exe /c` on Windows, `sh -c` on Linux/macOS
- `ps{ }` blocks → checks for powershell/pwsh

If a required toolchain is missing, the interpreter raises an `ArbPlusError` with a message like:
```
ArbPlus Error: C block requires a C compiler (gcc/cc/clang) but none was found on PATH.
Install a C compiler to use c{ } blocks.
```

### Packaging
- Bundled via PyInstaller into a single executable per platform
- End users don't need Python installed
- C/C++ extensions still require a compiler at runtime

### Performance Trade-off
| Workload | Performance | Impact |
|----------|-------------|--------|
| File I/O, shell calls, string ops | I/O-bound | Python overhead negligible |
| Tight numeric loops | CPU-bound | ~100x slower than compiled |
| count.time sampling | CPU-bound | Sub-ms precision not achievable |
| c{ } blocks | Native | Full speed (compiled) |

---

## Step 4 — Execution Model

### Declarations
```
#use batch;       // declares the script uses batch shell escapes
#use powershell;  // declares PowerShell usage
#import utils;    // imports an ArbPlus module
```

### Shell Escape Syntax
```
let result = cmd{ echo "hello" };      // batch/cmd escape
let psResult = ps{ Get-Date };          // PowerShell escape
```

### Variable Interpolation
ArbPlus variables are interpolated into shell blocks using `${var}` syntax:
```
let name = "world";
cmd{ echo "Hello, ${name}" };
```

### Output Marshaling
Shell stdout is captured and returned as an `ArbString`. The script can then coerce it to other types using `toInt()`, `toFloat()`, etc.

---

## Step 5 — Type System

### Core Types

| Type | Description | Literal Example |
|------|-------------|-----------------|
| `int` | 64-bit integer | `42`, `0x1A` |
| `float` | Double-precision float | `3.14` |
| `string` | UTF-8 text | `"hello"` |
| `boolean` | True/false | `true`, `false` |
| `array` | Fixed-size, homogeneous | (constructed via builtins) |
| `list` | Dynamic, heterogeneous | `[1, "two", 3.0]` |
| `arb` | Tagged hex container | `arb{ 0x01("hi"), 0x02(42) }` |

### arb Type

#### Sub-Type Tag Map
| Tag Name | Hex Prefix | Description |
|----------|-----------|-------------|
| str | 0x01 | String |
| int | 0x02 | Integer |
| float | 0x03 | Float |
| bool | 0x04 | Boolean |
| image | 0x10 | Base64-encoded image |
| raw | 0xFF | Raw bytes |

#### Literal Syntax
```
let data = arb{ 0x01("hello"), 0x02(42), 0x03(3.14), 0x04(true) };
```

#### Encode/Decode
- Encoding: each value is serialized to hex bytes using `struct.pack` for int/float, `.encode().hex()` for strings
- Decoding: values are stored decoded in memory; `get_decoded(index)` returns the Python value

#### Operations
- Indexing: `data[0]` → returns the decoded value as an ArbValue
- Iteration: `for (item in data) { ... }`
- Type checking: `typeof(data[0])` → returns the sub-type tag name
- Length: `len(data)` → number of elements

### Coercion Rules
| From | To | Method |
|------|-----|--------|
| int → float | `toFloat(42)` | Returns 42.0 |
| float → int | `toInt(3.14)` | Truncates to 3 |
| int → string | `toString(42)` | "42" |
| bool → string | `toString(true)` | "true" |
| string → int | `toInt("42")` | 42 (raises error if non-numeric) |
| arb[n] → any | `data[0]` | Returns decoded value with its original type |

---

## Step 6 — Variables, String Concatenation & Swap

### Declaration & Assignment
```
let x = 10;        // mutable declaration
const PI = 3.14;   // immutable declaration
x = 20;            // reassignment (let only)
```
- **Scoping**: Function-local by default. Variables declared in the body are global to functions called from the body (via parent environment chain).
- **Mutability**: `let` = mutable, `const` = immutable (reassignment raises error)

### String Concatenation
- **Operator**: `..` — does NOT auto-coerce (use `toString()` for non-strings)
- **Builtin**: `concat(a, b, c)` — auto-coerces all arguments to strings
- **Precedence**: `..` is below comparison operators, above `+`/`-`
- **Auto-coercion with `+`**: If either operand of `+` is a string, both are coerced to strings and concatenated

### Single-Line Swap
```
a <> b;
```
- Swaps the values of `a` and `b` without a temp variable
- Different types: values are swapped as-is, types follow the values
- Both operands must be existing variable names (not expressions)

---

## Step 7 — Functions

### Definition Syntax
```
--Function Role.Name (Args) {
    <body>
}
```

### Role
The `Role` field serves as a namespace/visibility prefix:
- `pub` — public (callable from anywhere)
- `util` — utility (callable, conventional namespace)
- Any identifier works as a custom namespace

### Arguments
- Typed: `--Function pub.add(x: int, y: int) { ... }`
- Untyped: `--Function util.greet(name) { ... }`
- Type hints trigger coercion on call: passing `42` to a `: int` param is safe

### Return
- `return value;` — returns from function
- `return;` — returns empty string
- Implicit return: if no return, returns empty string

### Nested/Recursive Calls
Functions can call themselves recursively and call other functions. Functions are stored in the interpreter's function table and resolved by name.

### Built-in Functions
Arithmetic: `add`, `sub`, `mul`, `div`, `mod`, `pow`
String: `concat`, `len`, `upper`, `lower`, `trim`, `split`, `join`, `substr`, `replace`, `contains`
I/O: `print`, `input`
Type: `toInt`, `toFloat`, `toString`, `toBool`, `typeof`
File: `readFile`, `fileExists`, `writeFile`, `buildFile`, `encodeImage`, `decodeImage`, `openMedia`, `openBrowser`
Addressing: `addr.hex`, `addr.binary`, `addr.meta`, `txtRC`
Directory: `dir.list`, `dir.name`, `dir.make`, `dir.del`
OS: `snap.time`, `count.time`, `wait`, `cs`, `locale.prf`, `locale.check`, `locale.alt`, `locale.cur`, `battery`, `network`, `screen`, `os.name`, `os.version`
Extensions: `loadExt`

### Overrides
```
--OV print myprint;
```
- Creates an alias: calling `myprint` invokes the original `print` builtin
- The original name (`print`) remains callable
- Collision: if a user function with the same name as the override target exists, the override takes precedence for the alias name

---

## Step 8 — File Reading, Addressed Data Access & Image Encoding

### Basic File Reading
```
if (fileExists("./data.txt")) {
    let content = readFile("./data.txt");
    print(content);
}
```
- `fileExists(path)` → boolean
- `readFile(path)` → string (full contents)
- Errors (not found, not readable, is directory) raise catchable `ArbPlusError`

### File Reading Modes
- **Media**: `openMedia(path)` — opens in OS's registered app
- **Binary/Hex**: `addr.hex(offset)` returns hex representation
- **Metadata**: `addr.meta("EXIF:DateTaken")` returns metadata marker
- **Browser**: `openBrowser(url)` — uses OS's default browser mechanism

### Addressing Syntax
```
addr.hex(0x1A)         // → "0x1A"
addr.binary(1024)      // → "0b10000000000"
addr.meta("EXIF:DateTaken")  // → metadata lookup
```

### txtRC — Row/Column Access
```
let data = readFile("./data.csv");
let cell = txtRC(2, 3, data);  // row 2, col 3 (1-based indexing)
```
- **Indexing**: 1-based (row 1 = first row, col 1 = first column)
- **Out of bounds**: raises `ArbPlusError` with bounds info
- **Delimiter detection**: auto-detects tab, comma, semicolon, or whitespace
- **Third argument**: optional data string; if omitted, uses last `readFile` result

### Image Encoding
```
let img = encodeImage("./photo.png");  // → arb with image tag (0x10)
decodeImage(img, "./restored.png");     // writes back to file
```
- `encodeImage(path)` reads bytes, base64-encodes, stores in arb with `image` tag
- `decodeImage(arb, path)` extracts base64 data, decodes, writes to file
- Interacts with `image` metadata tag: the metadata tag references a display icon; encodeImage/decodeImage handle data images

---

## Step 9 — File Building, Path Resolution & Directory Operations

### File Building
```
writeFile("./output.txt", "content", mode: overwrite);  // default: overwrite
writeFile("./output.txt", "content", mode: error);       // error if exists
buildFile("./output.txt", "content");                    // auto-rename if exists
```

### Path Resolution
- **Relative**: `./` (current folder), `../` (parent), `../../` (multi-level)
- **Base**: resolved relative to the **running script's location** (not working directory)
- Absolute paths pass through unchanged

### Write Conflicts
| Mode | Behavior |
|------|----------|
| overwrite (default) | Overwrites existing file |
| error | Raises error if file exists |
| buildFile | Auto-renames to `output_1.txt`, `output_2.txt`, etc. |

### Missing Directories
`writeFile` and `buildFile` auto-create intermediate directories.

### Directory Operations
```
dir.make("./newdir", "a.txt;b.txt;c.arb");  // creates dir with empty files
dir.list("./newdir");                       // returns list of all entries
dir.list("./newdir", "files");               // files only
dir.list("./newdir", "folders");             // folders only
dir.name("./newdir", "renamed");             // renames/moves
dir.del("./newdir");                         // recursive delete
```

### Error Convention
All directory operations raise catchable `ArbPlusError` on failure (not found, target exists, etc.). Success returns `true` (boolean).

---

## Step 10 — Conditionals & Control Flow

### if / elif / else
```
if (cond) { ... }
elif (cond2) { ... }
else { ... }
```

### not Operator
```
if (not cond) { ... }
```
- Precedence: above comparison operators, below `&&` and `||`
- Negates truthiness of the following expression

### Loops
```
for (i = 1 to 10) { ... }
for (i = 0 to 100 step 2) { ... }
for (item in list) { ... }
while (cond) { ... }
```

### break
```
for (i = 1 to 100) {
    if (i > 10) { break; }
}
```
- Exits the **innermost** loop only
- Labeled/nested break is not supported in v1.0

### exit / quit / end
- `exit` — terminates program with optional exit code: `exit 1;`
- `quit` — synonym for `exit 0;`
- `end` — no-op in the parser (blocks are `{ }` delimited); kept for compatibility

### Inline Expressions
- Ternary: `let x = (cond ? valA : valB);`
- Inline input: `let name = input("Enter name: ", fg: cyan);`

---

## Step 11 — Input/Output with Color

### Color Model
- Named colors: black, red, green, yellow, blue, magenta, cyan, white
- Bright variants: bright_black, bright_red, etc.
- Hex RGB: `#FF6600`
- Default when only fg given: bg stays terminal default (no bg code emitted)
- Default when only bg given: fg stays terminal default

### Syntax
```
print("text", fg: red, bg: black);
print("just fg", fg: cyan);
input("prompt: ", fg: yellow, bg: blue);
```

### Default Behavior
- `print(text)` → no color (plain output)
- `print(text, fg: red)` → red text, default background
- `print(text, bg: black)` → default text, black background
- Color values are bare identifiers (not strings) in kwarg position: `fg: red` not `fg: "red"`

---

## Step 12 — OS-Level Global Variables

### Time

#### snap.time — One-Shot Snapshot
```
let ts = snap.time();                              // "2026-07-23 12:39:00"
let detailed = snap.time(Year: 0, Month: 0, Day: 0);  // "Year=2026, Month=7, Day=23"
```
Returns the current time once. Each named kwarg slot is bound to the corresponding component.

#### count.time — Live/Dynamic
```
let now = count.time();                            // re-samples on each call
let ms = count.time(MS: 0, interval: 1);           // custom 1ms interval
```
Re-samples the clock on each access. The `interval` kwarg sets a custom sampling interval in milliseconds (default: 1ms).

#### wait — Pause Execution
```
wait(0, 2, 500);  // 0 minutes, 2 seconds, 500 ms → pauses 2.5s
```
Full script halt (synchronous interpreter). If a function name is passed after `;`, it would pause that function only — but in the current implementation, wait is a full script halt (synchronous model).

### Color Scheme — cs()
```
let scheme = cs();      // "light" or "dark"
let isDark = cs(dark);   // true/false
let isLight = cs(light); // true/false
```
- No argument: returns current scheme as string
- With argument: returns boolean (same global, queried two ways)

### Locale
```
locale.prf    // preferred locale (e.g., "en_US")
locale.cur    // current active locale
locale.alt    // alternative/fallback locales (e.g., "en-US, en-GB")
locale.check("en_GB")  // boolean: is this locale available?
```

### Other Globals
| Global | Returns |
|--------|---------|
| `battery()` | Battery status string (e.g., "85%") |
| `network()` | Boolean — network connectivity |
| `screen()` | Screen dimensions (e.g., "1920x1080") |
| `os.name` | OS name (e.g., "Linux", "Windows", "Darwin") |
| `os.version` | OS version string |

### Adding New Globals
The pattern is: add a new builtin to `_setup_builtins`, follow the two-shapes pattern (no-arg returns value, with-arg returns boolean check), use dot-notation for namespaced globals (e.g., `disk.space`, `cpu.usage`).

---

## Step 13 — Extensions (C / C++ / Python): Interface & ABI

### C/C++ ABI
- Entry point: `arbplus_register(ArbEngine* engine)`
- `ArbEngine` struct contains:
  - `register_func(name, func)` — register a new function
  - `register_hook(builtin_name, hook)` — hook an existing builtin
- Value marshaling: `ArbValue` struct with type tag + union (int_val, float_val, str_val, bool_val)
- Use `extern "C"` in C++ to prevent name mangling on the entry point

### Python ABI
- Entry point: `register(engine)` function
- `engine.register_extension(name, func)` — func receives `(args, kwargs)` as lists/dicts of ArbValue
- `engine.register_hook(builtin_name, hook_func)` — hook receives `(args, kwargs, original_func)`

### Loading Extensions
```
loadExt("./ext_example.py", "python");
loadExt("./ext_c.c", "c");
loadExt("./ext_cpp.cpp", "c++");
```
Declared in metadata `dependencies` and `languages` fields.

### Calling Extension Functions
- Bare names: `ext.double(42)` — the `ext.` prefix is conventional
- Functions registered without the `ext.` prefix are callable by their registered name directly

### Hook Mechanism
- Hooks are called **before** the original builtin
- If a hook returns non-None, it short-circuits (original not called)
- If a hook returns None, the original builtin runs normally
- Multiple hooks stack: called in registration order, first non-None wins

### Error Handling
- Failed load: `ArbPlusError` with file path and reason
- Failed call: exception from the extension function propagates as `ArbPlusError`

---

## Step 14 — Extension Examples & Maintenance Guide

See:
- `extensions/ext_c.c` — C extension example
- `extensions/ext_cpp.cpp` — C++ extension example
- `extensions/ext_example.py` — Python extension example
- `docs/maintenance.md` — Manual maintenance guide

---

## Steps 15-18

See:
- `docs/grammar.md` — Formal EBNF grammar (Step 15)
- `examples/` — Worked examples (Step 16)
- `docs/usage.md` — Usage documentation (Step 17)
- `docs/implementation_notes.md` — Implementation notes (Step 18)


---

# ArbPlus v2.0 — Language Additions

The following additions extend the base v1.0 specification. They are fully implemented and tested.

## Addition 1 — String Interpolation

`${expr}` inside string literals is replaced with the expression's value at runtime.

- Undefined variables inside `${}` produce an empty string (no error)
- Expressions are parsed by a sub-lexer/parser (any valid ArbPlus expression)
- Interpolation works in both regular and interpolated strings

## Addition 2 — open.url, open.app, bindKey

- `open.url(url_string)` — opens the URL in the OS default browser
- `open.app(app_name, args: arg_string)` — launches an OS application
- `bindKey(key_combo, function_name)` — registers a key binding for interactive mode
- In script mode (no event loop), these are no-ops that log the intended action

## Addition 3 — Random, CLI Args, Environment

### Random
- `random()` — returns a float in [0.0, 1.0)
- `randInt(min, max)` — returns an integer in [min, max] (inclusive)
- `random.seed(n)` — seeds the PRNG for reproducible sequences
- Seeded sequences are deterministic; re-seeding with the same value reproduces the same sequence

### CLI Arguments
- `args()` — returns a list of command-line arguments passed after the script name
- `args(index)` — returns the argument at the given 0-based index, or empty string
- Arguments are passed as: `python3 interpreter.py script.arb arg1 arg2 ...`

### Environment Variables
- `env("VAR_NAME")` — returns the environment variable value, or empty string if not set

## Addition 4 — Map Type

A key-value store with string keys and ArbValue values.

### Construction
```arb
let m = map{ "name": "ArbPlus", "version": 2, "debug": true };
```

### Operations
- Access: `m.keyName` or `m["keyName"]`
- Assignment: `m.keyName = value`
- `keys(m)` — returns list of all keys
- `values(m)` — returns list of all values
- `has(m, "key")` — returns boolean

## Addition 5 — /n Newline Token & Text Brightness

### /n Processing
- `/n` inside displayed text (print/input output) is converted to a newline
- `//n` is the escape sequence to show `/n` literally
- Processing order: `//n` → placeholder, `/n` → newline, placeholder → `/n`
- Only applied when text is output via print() or input()

### Text Brightness
- `b:` kwarg controls ANSI brightness: `dim` (code 2), `normal` (code 22), `bright` (code 1)
- Default brightness is `normal`
- Combined with fg color in the ANSI escape sequence

## Addition 6 — repeat...until

Post-test loop that always executes at least once:
```arb
repeat {
    // body (always runs at least once)
} until (condition);
```
- Condition is checked AFTER the body executes
- `break` works inside the body
- Equivalent to do-while in C

## Addition 7 — --OV defaults Override

Sets default colors applied to all print/input calls without explicit fg/bg/b kwargs:
```arb
--OV defaults(fg, bg, b) (fg: cyan, bg: black, b: bright);
```
- Per-script setting
- Individual call kwargs override the defaults
- If a call specifies `fg: red`, only fg is overridden; bg and b still use defaults

## Addition 8 — Cross-Type Comparison

### == and != with mixed types
- String vs int: `"42" == 42` → `true` (string is coerced to int for comparison)
- String vs float: `"3.14" == 3.14` → `true`
- Non-numeric strings: `"hello" == 42` → `false` (no coercion)

### <, <=, >, >= with mixed types
- If both operands look numeric, they are compared numerically
- If either is non-numeric, string comparison is used
- `"5" < "10"` → `false` (string comparison: '5' > '1')

## Addition 9 — switch/case and try/catch/finally

### switch/case
```arb
switch (expression) {
    case value1: { statements }
    case value2: { statements }
    default: { statements }
}
```
- Optional colon after case value
- `default` is the catch-all (optional)
- First matching case executes, then breaks (no fall-through)

### try/catch/finally
```arb
try {
    // risky code
} catch (err) {
    // err contains the error message string
} finally {
    // always runs, even if no catch
}
```
- `catch` stores the ArbPlusError message in the named variable
- `finally` is optional but always runs (cleanup)
- `try` with `finally` only (no `catch`) — cleanup runs after any error
- Only catchable errors are caught (ArbPlusError), not Python system errors

## Addition 10 — and / or Keywords

`and` and `or` are keyword alternatives to `&&` and `||`:
```arb
if (a and b) { }      // same as if (a && b)
if (a or b) { }       // same as if (a || b)
if (a and b or c) { } // and has higher precedence than or
```
- Keywords and operators can be mixed
- `and` has the same precedence as `&&` (higher than `or`/`||`)

## Addition 11 — Module Imports

```arb
#import modulename;
```
- Loads `modulename.arb` from the same directory as the importing script
- Module functions become available as `modulename.functionName()`
- Module function definitions are extracted and registered in the interpreter
- Non-.arb imports (e.g., Python extensions) are silently skipped (use `loadExt` instead)
- Circular imports are prevented via import tracking

## Addition 12 — CLI Argument Passing

Command-line arguments after the script name are available via `args()`:
```bash
python3 interpreter.py script.arb hello world 42
```
```arb
print(args());    // → ["hello", "world", "42"]
print(args(0));   // → "hello"
print(len(args())); // → 3
```
Arguments are passed as strings; use `toInt()` / `toFloat()` for numeric conversion.

---

## Additions 24-27 (v2.0 final)

### Addition 24: run.arb() — Execute Another Arb Script
`run.arb(path, key: value, ...)` loads and executes another `.arb` file in a fresh scope, passes variables as CLI args, and returns the child script's return value. The child receives arguments via `args()` and `args(i)`.

```
let result = run.arb("child.arb", greeting: "Hello", count: 42);
```

### Addition 25: dl.url() — Download URL to Disk
`dl.url(url, filename: "name.ext")` downloads a URL to the local filesystem. If no filename is given, it derives one from the URL path. Returns the full path to the saved file. Network errors are caught and reported.

```
let saved = dl.url("https://example.com/file.txt", filename: "data.txt");
```

### Addition 26: --clean — Manual GC Trigger
`--clean;` manually triggers garbage collection. Modes:
- `--clean;` — collect (default)
- `--clean stop;` — disable auto collection
- `--clean restart;` — re-enable and collect
- `--clean count;` — collect and store count silently

Works at both top-level and inside function bodies.

### Addition 27: return() Any Type + --F Delegation
`return()` now accepts any value type: int, float, string, bool, array, list, arb, map, colored string. Bare `return()` with no argument returns `null` (ArbNull).

`--F role.funcName(args)` delegates the return value to another function — sugar for `return(funcName(args))`. Supports dotted function names, positional and keyword arguments, and propagates errors through try/catch.

```
--Function util.dispatcher(choice) {
    if (choice == "A") { --F util.handlerA(); }
    if (choice == "B") { --F util.handlerB(10, 20); }
    return("default");
}
```

### null Keyword
`null` is now a first-class keyword producing `ArbNull()`. Comparisons: `null == null` → true, `null == "anything"` → false.

## Part 4 Additions (26-27)

### Addition 26: Inline Python py{ } Block

The `py{ ... }` block is an inline escape into raw Python code within an ArbPlus script. Since the interpreter itself runs in Python, `py{ }` executes directly in the same process — no separate compiler or toolchain needed.

**Variable passing**: All ArbPlus variables in scope are available inside the block. Variables assigned inside the block are synced back to ArbPlus scope after execution. Type translation is automatic:
- ArbPlus `int`/`float`/`string`/`bool` → Python `int`/`float`/`str`/`bool`
- ArbPlus `list` → Python `list`
- ArbPlus `map` → Python `dict`
- ArbPlus `arb` → Python `list` (of [name, byte, hex, decoded] tuples)
- Python values assigned back are translated to the closest ArbPlus type

**Standard-library-only restriction**: `py{ }` blocks may only `import` Python standard-library modules (e.g. `math`, `json`, `re`, `datetime`, `os`, `sys`). Third-party imports are rejected at runtime with an `ArbPlusError` that can be caught via `try/catch`. The interpreter checks each `import` statement against Python's `sys.stdlib_module_names` allowlist.

**One-way boundary**: Inside a `py{ }` block, you cannot call ArbPlus built-in functions. ArbPlus data goes in, Python code runs, Python values come back. This is by design — third-party logic belongs in proper ArbPlus extensions (Step 13), not smuggled through an inline block.

```
let data = "hello world foo bar";
let word_count = 0;
py{
    import re
    words = re.findall(r'\w+', data)
    word_count = len(words)
    print(f"Found {word_count} words: {words}")
}
print("Back in ArbPlus:", word_count);
```

### Addition 27: $! File-Path Loading for Escape Blocks

`$!pathVariable` inside a `c{ }`, `py{ }`, `cmd{ }`, or `ps{ }` block tells the interpreter to load the block's code from an external file at runtime, rather than writing it inline.

```
c{$!cSourcePathVar}
py{$!pySourcePathVar}
cmd{$!scriptPathVar}
ps{$!scriptPathVar}
```

**Rules**:
- `$!` must be the sole content of the block — no mixing inline code with file loading
- Path resolution uses the same `./`/`../` relative rules as file building (Step 9)
- If the path doesn't point to a readable file, an `ArbPlusError` is raised (catchable via try/catch)
- For `py{$!...}`: the loaded file is still subject to the stdlib-only restriction
- No extension requirement — the block type declares the language, not the file extension
- For `cmd{$!...}`/`ps{$!...}`: this runs an existing `.bat`/`.sh`/`.ps1` script file from within ArbPlus

### Additional Part 4 Features

**Shorthand arithmetic**: `i++` (increment) and `k--` (decrement) work as standalone statements. Usable in while loops and for loops.

**Forward declaration**: `let [name];` declares a variable without assigning a value. The variable starts as `null` and can be assigned later, or never.

**var() built-in**: `var("variable_name")` returns the value of a variable by name, allowing unquoted variable references where strings are expected (e.g. in `--OV` overrides).

**count.time vs snap.time**: 
- `snap.time()` returns a full timestamp snapshot (date + time) at the moment of the call — for logging when something happened
- `count.time()` returns current time with optional live mode — `count.time(live: true, MS: 1000)` prints a live updating clock
- Setting a variable to `count.time()` captures the moment, not a live feed — the variable holds the value from when it was called

## Part 5 Additions (30–36)

### Addition 30: --ErrOV Warning/Error Color Gate

`--ErrOV true;` is a top-level flag (before `--Function` and body) that gates whether `--OV` color overrides apply to warning and error messages. When enabled, `--OV defaults(warn_fg, err_fg) (warn_fg: yellow, err_fg: red);` sets the color scheme for interpreter warnings and errors.

```
--ErrOV true;
--OV defaults(warn_fg, err_fg) (warn_fg: yellow, err_fg: red);
```

When `--ErrOV` is not set, `--OV` overrides for `warn_fg`/`warn_bg`/`err_fg`/`err_bg` are silently ignored (with a warning printed).

### Addition 31: Hex/RGB/OKLCH Color Support

The `color()` function and `--OV defaults` now accept color specifications beyond the basic named colors:

- **Hex**: `#ff6600`, `#330099`
- **RGB**: `rgb(255,102,0)`, `rgb(100,200,50)`
- **OKLCH**: `oklch(0.7,0.15,240)` — perceptually uniform color space

All color parameters (`fg`, `bg`) in `color()`, `print()` overrides, and `--OV defaults` accept any of these formats alongside the original named colors (`red`, `bright_blue`, etc.).

### Addition 32: Colored Output Extension

`ext_colors.py` provides ArbPlus-consistent colored output for inline language blocks. Load it via `loadExt` and call from Arb:

```
loadExt("extensions/ext_colors.py", "python");
let colored = ext_colors.color_text("Hello", "blue", "", "bright");
print(colored);
ext_colors.color_print("Red text", "red", "", "normal");
```

Also importable directly from `py{ }` blocks:
```
py{
    import sys
    sys.path.insert(0, "extensions")
    from ext_colors import color_text, color_print
    color_print("Hello from Python", "green", "", "bright")
}
```

The extension uses the same ANSI color logic as the interpreter's `colorize()` function, supporting named, hex, RGB, and OKLCH colors.

### Addition 33: Parser Fix — Commas and > in Color Arguments

Fixed a parser issue where commas and `>` inside `color()` arguments were misinterpreted as statement terminators. The parser now correctly handles:
- Multiple comma-separated kwargs: `color("text", fg: red, bg: white, b: bright)`
- `>` inside expressions: `print("5 > 3 is " + (5 > 3));`

### Addition 34: meta.* Variables

`meta(key)` returns individual metadata fields. `meta()` (no args) returns all metadata as a map. Internal keys (prefixed with `_`) are filtered from the output.

```
meta.name         // "My Script"
meta.version      // 2.0
meta.description  // "A description"
meta()            // {name: "My Script", version: 2.0, ...}
```

### Addition 35: Arb Naming Convention

- **Product name**: ArbPlus (the interpreter/toolchain)
- **Language name**: Arb (the programming language)
- **File extension**: `.arb` (stays as-is, not `.arbplus`)

### Addition 36: file() Type

`file("path/to/file.txt")` creates an `ArbFile` reference that carries the resolved absolute path. The reference can be passed to `readFile()`, `fileExists()`, `addr.hex()`, and other file-related built-ins.

```
let f = file("test_ref.txt");
print("File ref: " + f);
print("File exists: " + fileExists(f));
print("Contents: " + readFile(f));
print("Hex: " + addr.hex(f));
```
