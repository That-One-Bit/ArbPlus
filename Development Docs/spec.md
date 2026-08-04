# ArbPlus Language Specification
## "A Really Bad Programming Language" — v1.0
## Terminology

In ArbPlus, the following terminology is used throughout:

- **Block** — A built-in function provided by the interpreter (e.g., `print`, `color`, `open.app`, `dir.make`, `snap.time`). Blocks are not user-defined; they are part of the language runtime.
- **Tag** — A keyword or positional argument passed to a block (e.g., `fg: red`, `bg: black`, `b: bright` are tags passed to the `print` and `color` blocks).
- **Function** — A user-defined function declared with `--Function Role.Name(args) { body }`. Functions have parameters and accept arguments.
- **Parameter** — A named input in a user-defined function declaration.
- **Argument** — A value passed to a user-defined function at call time.


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
**Primary terminator: `;`** — chosen because it's the universal statement separator across C-family languages, which ArbPlus embeds. Newlines also terminate statements. The `>` character is strictly a comparison operator (greater-than), not a terminator.

### Comments
- Single-line: `//` runs until the next statement terminator (`;`) or newline
- Multi-line: `/* ... */` — can span multiple lines, can be nested

### Whitespace & Encoding
- Whitespace between tokens is ignored (spaces, tabs, newlines)
- Newlines are soft terminators — a statement continues across lines until `;`
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

ArbPlus ships as a single interpreter (lexer, parser, evaluator, blocks, OS-globals layer) written in Python 3. The interpreter interprets ArbPlus code directly and shells out to whatever toolchains are already on the user's machine for embedded pieces.

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
OS: `snap.time`, `count.time`, `wait`, `cs`/`os.CS`, `locale.prf`, `locale.check`, `locale.alt`, `locale.cur`, `os.Battery`/`battery`, `os.Network`/`network`, `os.Screen`/`screen`, `os.Name`/`os.name`, `os.Version`/`os.version`
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

#### snap.time — One-Shot Snapshot (Presence-Based)
```
let ts = snap.time();                        // "2026-08-01 14:37:00" (full timestamp)
let m = snap.time("minute");                  // "37" (raw value, no Key=val)
let hm = snap.time("hour", "minute");         // "14 37" (multiple components)
```
Returns the current time once. Pass component names as positional string arguments to get specific values. Returns raw values (not `Key=val` format). Use `print()` with concatenation for formatted output.

#### count.time — Live/Dynamic (Presence-Based)
```
let now = count.time();                        // "14:37:00.123" (full time)
let m = count.time("minute");                   // "37"
count.time(live: true, MS: 1000);              // live updating clock (blocks)
```
Same presence-based model as `snap.time`. The `live: true` kwarg with `MS: <interval>` activates live clock mode (blocks execution until interrupted).

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
| `os.Battery()` / `battery()` | Battery level (e.g., `85`) |
| `os.Network()` / `network()` | Boolean — network connectivity |
| `os.Screen()` / `screen()` | Screen dimensions (e.g., `"1920x1080"`) |
| `os.Name()` / `os.name` | OS name (e.g., `"Linux"`, `"Windows"`, `"Darwin"`) |
| `os.Version()` / `os.version` | OS version string |
| `os.CS()` / `cs()` | Color scheme (`"dark"`/`"light"`) |

All OS functions support Android via `adb` when a device is connected. `os.CS()` / `cs()` properly detects Android night mode — even if night mode is enabled, `cs(light)` returns `true` and `cs(dark)` returns `false`, matching the system's reported state.

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

## Addition 5 — Newline Escape & Text Brightness

### Newline Escape
- `\n` inside string literals is converted to a newline (standard escape sequence)
- Applied at lexer time, so runtime values (file paths, error messages) are unaffected
- No `/n` special token — `/n` in a string is just the literal characters `/` and `n`

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

`--F role.funcName(args)` delegates the return value to another function — sugar for `return(funcName(args))`. Supports dotted function names, positional and tags, and propagates errors through try/catch.

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

**One-way boundary**: Inside a `py{ }` block, you cannot call ArbPlus blocks. ArbPlus data goes in, Python code runs, Python values come back. This is by design — third-party logic belongs in proper ArbPlus extensions (Step 13), not smuggled through an inline block.

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

The `color()` block and `--OV defaults` now accept color specifications beyond the basic named colors:

- **Hex**: `#ff6600`, `#330099`
- **RGB**: `rgb(255,102,0)`, `rgb(100,200,50)`
- **OKLCH**: `oklch(0.7,0.15,240)` — perceptually uniform color space

All color tags (`fg`, `bg`) in `color()`, `print()` overrides, and `--OV defaults` accept any of these formats alongside the original named colors (`red`, `bright_blue`, etc.).

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

### Addition 33: Parser Fix — Commas and > in Color Tags

Fixed a parser issue where commas inside `color()` tags were misinterpreted as statement terminators. The `>` character is now strictly a comparison operator, not a statement terminator. The parser correctly handles:
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


## Part 6 Additions (37–42)

### Addition 37: `--OV` Universal Override Rule

`--OV` works uniformly across **all** blocks — not just `print`. Any built-in in the function table can be overridden, including `input()`.

**The general rule**: `--OV builtinName newAlias;` creates an alias for *every* form of that built-in. If a built-in has both a statement form and an inline-assignment form, the override covers both automatically. There is no need to specify the inline form separately.

For `input()` specifically:
- **Statement form**: `input("prompt: ");` → overridden alias works
- **Inline-assignment form**: `let name = input("prompt: ");` → overridden alias also works

```arb
--OV input myinput;

// Both forms are covered by the single override:
myinput("Enter name: ");          // statement form works
let name = myinput("Enter: ");     // inline-assignment form also works
```

This applies to every built-in: `--OV snap.time mytime;` overrides both `snap.time()` and `let ts = snap.time();`. The override intercepts the function name in the builtins table, so any call site using the new alias invokes the original function regardless of context.

### Addition 38: New Worked Examples

See `examples/` directory for complete scripts covering:
- **GUI interaction** — opening a native dialog via Python extension (see `ext_example.py`)
- **Cross-language variables** — the same ArbPlus variable used in `cmd{ }`, `py{ }`, and `c{ }` blocks within one script
- **`addr.hex()`** — reading a specific byte offset from a binary file
- **`input()` with `--OV`** — overriding `input()` and calling the override

### Addition 39: VS Code Syntax Highlighting

A VS Code extension is included in `vscode-arbplus/` providing:
- **TextMate grammar** (`syntaxes/arbplus.tmLanguage.json`) — syntax highlighting for all ArbPlus constructs
- **Semantic tokens** — 3-way function coloring: built-in (function), user-defined (macro), extension (variable)
- **Go-to-definition** — resolves `Role.Name()` calls within and across files
- **Hover provider** — shows function signatures and descriptions
- **Color theme support** — `syntaxes/color-guide.json` lists TextMate scope names with recommended colors for each syntax type, allowing easy theme integration

Install by opening `vscode-arbplus/` in VS Code and pressing F5, or install the packaged `.vsix` file. The grammar covers: comments (`//`, `/* */`, `#`), metadata block, string literals (including `${...}` interpolation), `--Function`/`--OV`/`--clean`/`--F` directives, keywords (`if`/`elif`/`else`/`repeat`/`until`/`switch`/`case`/`try`/`catch`/`finally`), `fg:`/`bg:`/`b:` named arguments, and all 88 blocks.

The TextMate grammar is portable — editors that support TextMate grammars (Sublime Text, Atom, GitHub highlighting) can use the same `.tmLanguage.json` with minimal adaptation.

### Addition 40: Expanded Documentation

This document and `docs/usage.md` have been fully updated to reflect all additions from the entire addendum. The documentation is usable on its own by someone who has only this final version — no need to read the addendum messages in order.

### Addition 41: Worked Example Coverage

All features from Additions 30–40 have worked examples in the `examples/` and `AI_Examples/` directories. The quick-reference table and formal grammar cover every addition.

### Addition 42: Downloadable Package

The entire ArbPlus project is packaged as a downloadable archive containing:
- `README.md` — how to run locally (Python version, dependencies, run command)
- Full interpreter source
- All worked-example `.arb` scripts
- C, C++, and Python extension examples (optional add-ons)
- VS Code syntax-highlighting extension (in `vscode-arbplus/`)
- Full documentation (`docs/`)

---

## Post-Addendum Changes

### `open.app(..., adr:)` — Android App Launching

`open.app` now supports launching Android apps alongside its existing Windows/macOS/Linux behavior. The `adr` argument specifies the Android package name or full intent string.

**Transport**: Uses `adb` (Android Debug Bridge) — the runtime shells out to `adb` against a connected/paired device or emulator, the same way it shells out to `cmd`/PowerShell for desktop operations. This was chosen over a dedicated companion extension because `adb` is the standard Android debugging tool, already installed in most development environments, and keeps the feature in the core runtime without requiring a separate extension load.

**`adr` accepts**:
- **Bare package name**: `adr: "com.example.app"` — launches the app's default activity via `adb shell monkey -p com.example.app -c android.intent.category.LAUNCHER 1`
- **Full intent string**: `adr: "am start -n com.example.app/.MainActivity"` — for more specific launches, passed directly to `adb shell`

**`args` mapping**: When `adr` is present, `args` maps onto Android's intent-extras system (e.g., `--es key value` flags). On desktop, `args` retains its existing meaning (arguments passed to the executable).

**Error handling**: Uses `try/catch` convention. If no device is connected/authorized, or the named package isn't installed, an `ArbPlusError` is raised:

```arb
try {
    open.app("", adr: "com.example.myapp");
} catch (e) {
    print("Failed to launch: " + e);
}
```

**Capability declaration**: Using `adr` should be declared in the metadata `languages` field alongside other reaching-off-the-machine features (like `fetch` for network or `javascript:` for browser scripting):

```arb
#meta {
    languages: "Arb, adb";
}
```

```arb
// Launch default activity
open.app("", adr: "com.example.myapp");

// Launch specific activity via intent string
open.app("", adr: "am start -n com.example.myapp/.MainActivity");

// With intent extras
open.app("", args: "--es greeting hello", adr: "com.example.myapp");
```

### `snap.time()` Reworked — Presence-Based Arguments

`snap.time` now uses **presence-based** positional tags: `snap.time(Year, Month, Day, Hour, Minute, Second, Millisecond)`. An argument that is present (even as `0` or an empty string) requests that component. Absent arguments are not returned.

**No `Key=val` output**: Returns raw values only (e.g., `"37"` not `"Minute=37"`). Use `print()` with string concatenation for formatted output.

```arb
snap.time()                        // → "2026-08-01 14:37:00" (full timestamp)
snap.time("minute")                // → "37" (just the minute)
snap.time("hour", "minute")         // → "14 37" (hour and minute, space-separated)
snap.time(minute: true)             // → "37" (via kwarg)
snap.time("year", "month", "day")   // → "2026 8 1"
```

You can also pass positional tags where the position determines the component (following the `Year, Month, Day, Hour, Minute, Second, Millisecond` order):

```arb
snap.time(0, 0, 0)  // → "2026 8 1" (year, month, day — positional)
```

### `count.time()` Reworked — Presence-Based Arguments

Same presence-based model as `snap.time`, but focused on time components:

```arb
count.time()                    // → "14:37:00.123" (full time)
count.time("minute")             // → "37"
count.time("hour", "minute")     // → "14 37"
count.time(live: true, MS: 1000) // live updating clock (blocks execution)
```

### OS Functions Renamed with `os.` Prefix

All OS-level functions now use the `os.` prefix consistently. The old bare names (`battery()`, `network()`, `screen()`) still work as aliases, but the canonical form is:

| Canonical | Alias | Returns |
|-----------|-------|---------|
| `os.Battery()` | `battery()` | Battery level (e.g., `85`) |
| `os.Screen()` | `screen()` | Screen resolution (e.g., `"1920x1080"`) |
| `os.Network()` | `network()` | Network connectivity (`true`/`false`) |
| `os.Name()` | `os.name` | OS name (e.g., `"Linux"`, `"Windows"`, `"Darwin"`) |
| `os.Version()` | `os.version` | OS version string |
| `os.CS()` | `cs()` | Color scheme (dark/light) — see below |

### `cs()` / `os.CS()` — Android Night Mode Support

Color scheme detection now supports Android devices via `adb`. On Android, even if night mode is enabled, `cs(light)` returns `true` and `cs(dark)` returns `false` — matching the system's reported state.

Detection methods (in order):
1. `adb shell settings get secure ui_night_mode`
2. `adb shell settings get system ui_night_mode`
3. `adb shell cmd uimode night`
4. `adb shell dumpsys activity throttle` (theme check)

If no Android device is connected, falls back to desktop detection (terminal color queries, `COLORFGBG` env var, etc.).

### `os.Battery()` and `os.Screen()` — Android Support

Battery and screen functions also support Android via `adb`:
- `os.Battery()` — reads `adb shell dumpsys battery` for level, status, and charging state
- `os.Screen()` — reads `adb shell wm size` for resolution

### `bindKey()` Outside `repeat/until` Loops

`bindKey` can now be used as a standalone statement outside of `repeat/until` loops. When used standalone:
- For `CTRL+C` / `CTRL+Z`: installs a signal handler (`SIGINT`/`SIGTSTP`)
- For other keys: attempts to use the `keyboard` Python library if available (optional dependency)
- The binding is registered regardless and checked during `repeat/until` loops if one starts later

```arb
// Standalone — installs SIGINT handler
bindKey("CTRL+C", "quit");

// This now works without a repeat/until loop
print("Press CTRL+C to quit.");
while (true) {
    wait(0, 0, 500);
}
```

### TextMate Grammar with Color Codes

The `syntaxes/color-guide.json` file in the VS Code extension lists every TextMate scope used by the grammar with a recommended color for each syntax type. This allows theme authors to easily add ArbPlus support by mapping these scopes to their theme's color palette.

---

## Maps and Arbs — Extended Documentation

### Map Type (Addition 4) — Complete Reference

Maps are ordered key-value stores. Keys are strings; values can be any ArbPlus type.

#### Construction

```arb
let m = map{ "name": "ArbPlus", "version": 2, "debug": true };
```

- Keys must be string literals (quoted)
- Values can be any type: `int`, `float`, `string`, `bool`, `list`, `map`, `arb`, `null`
- Insertion order is preserved

#### Access

```arb
// Dot notation (key must be a valid identifier)
print(m.name);         // → "ArbPlus"

// Bracket notation (key can be any string, including with spaces)
print(m["version"]);   // → 2

// Missing key returns empty string (not an error)
print(m.nonexistent);  // → ""
```

#### Assignment

```arb
// Add or update a key
m.newKey = "added";
m["version"] = 3;

// Assign any type
m.numbers = [1, 2, 3];
m.nested = map{ "inner": "value" };
m.data = arb{ 0x01("hello"), 0x02(42) };
```

#### Built-in Operations

```arb
keys(m)          // → ["name", "version", "debug", "newKey"]
values(m)        // → ["ArbPlus", 3, true, "added"]
has(m, "name")   // → true
has(m, "xyz")     // → false
len(m)            // → 4 (number of entries)
```

#### Nested Maps

Maps can contain other maps as values. Access nested keys with chained dot notation:

```arb
let config = map{
    "database": map{
        "host": "localhost",
        "port": 5432,
        "credentials": map{
            "user": "admin",
            "password": "secret"
        }
    },
    "app": map{
        "name": "MyApp",
        "version": "1.0"
    }
};

print(config.database.host);                    // → "localhost"
print(config.database.credentials.user);         // → "admin"
print(config.app.version);                       // → "1.0"

// Update nested values
config.database.port = 3306;
config.app.version = "2.0";
```

#### Maps Containing Arbs

Maps can hold `arb` typed values alongside any other type:

```arb
let record = map{
    "name": "test.dat",
    "size": 1024,
    "raw_data": arb{ 0x01("header"), 0x02(42), 0x03(3.14), 0x04(true) }
};

// Access the arb value
print(record.raw_data);              // → arb{...}
print(record.raw_data[0]);           // → "header" (decoded)
print(record.raw_data[1]);           // → 42 (decoded)
print(typeof(record.raw_data));       // → "arb"

// Iterate over arb elements inside a map
for (item in record.raw_data) {
    print(item);
}
```

#### Maps Inside Arbs

Arb containers can hold map values by encoding them. However, `arb` tags are limited to the predefined sub-type set (str, int, float, bool, image, raw). A map stored in an `arb` is serialized as a `raw` tag (0xFF) with its string representation. For structured nesting, prefer maps-of-maps:

```arb
// Recommended: nest maps inside maps for structured data
let data = map{
    "person": map{
        "name": "Alice",
        "age": 30,
        "address": map{
            "city": "NYC",
            "zip": "10001"
        }
    }
};

// Arb containers are best for binary/tagged data, not nested structures
let binary = arb{ 0x01("metadata"), 0xFF(raw_bytes) };
```

#### Iteration

```arb
let m = map{ "a": 1, "b": 2, "c": 3 };

// Iterate over keys
for (k in keys(m)) {
    print(k, "=", m[k]);
}

// Iterate over values
for (v in values(m)) {
    print(v);
}
```

### Arb Type — Complete Reference

Arb is a tagged hex container — a sequence of values, each with a sub-type tag. Values are encoded as hex bytes for storage and decoded on access.

#### Sub-Type Tag Map

| Tag Name | Hex Prefix | Description |
|----------|-----------|-------------|
| str | 0x01 | String (UTF-8) |
| int | 0x02 | 64-bit integer (big-endian) |
| float | 0x03 | Double-precision float |
| bool | 0x04 | Boolean |
| image | 0x10 | Base64-encoded image data |
| raw | 0xFF | Raw bytes / untyped data |

#### Construction

```arb
let data = arb{ 0x01("hello"), 0x02(42), 0x03(3.14), 0x04(true) };
let empty = arb{};
let withRaw = arb{ 0x01("label"), 0xFF("raw bytes here") };
```

#### Access

```arb
data[0]      // → "hello" (decoded to string)
data[1]      // → 42 (decoded to int)
data[2]      // → 3.14 (decoded to float)
data[3]      // → true (decoded to bool)

// Out of bounds raises error
// data[10]  → ArbPlusError: index 10 out of bounds

len(data)    // → 4
```

#### Type Checking

```arb
typeof(data)       // → "arb"
typeof(data[0])    // → "string"
typeof(data[1])    // → "int"
typeof(data[2])    // → "float"
typeof(data[3])    // → "bool"
```

#### Iteration

```arb
for (item in data) {
    print(item);
}
// Output:
// hello
// 42
// 3.14
// true
```

#### Encoding & Decoding

Each value is serialized to hex bytes using `struct.pack` for int/float, `.encode().hex()` for strings. Decoded values are stored in memory; `data[index]` returns the decoded Python value wrapped as the appropriate ArbPlus type.

#### Image Handling

```arb
let img = encodeImage("./photo.png");    // → arb with image tag (0x10)
decodeImage(img, "./restored.png");       // → writes decoded image to file
```

#### Arbs Inside Maps

Arb values can be stored as map values and accessed normally:

```arb
let container = map{
    "name": "binary_data",
    "payload": arb{ 0x01("magic"), 0x02(256), 0x04(false) }
};

print(container.name);           // → "binary_data"
print(container.payload[0]);     // → "magic"
print(container.payload[1]);     // → 256
print(container.payload[2]);     // → false
```

#### Arbs Inside Arbs

Arb containers can nest by encoding one arb as a `raw` element in another:

```arb
let inner = arb{ 0x01("inside"), 0x02(99) };
let outer = arb{ 0x01("wrapper"), 0xFF(inner) };

// outer[0] → "wrapper" (decoded string)
// outer[1] → raw representation of inner arb
```

Note: nested arbs are stored as raw bytes, so the inner arb's individual elements aren't directly indexable through the outer arb. For structured nesting, use maps or lists to hold multiple arb containers.

## Set-7 Additions (43-47)

### Addition 43 — Argument-Aware `--OV` Overrides

The `--OV` mechanism (Step 7) now supports supplying fixed arguments as part of the override declaration itself, rather than only renaming the target function.

**Syntax:**
```arb
--OV base(fixedArgs) newName;
```

The argument list in parentheses is **optional**:
- **With args**: `--OV print("\n") newlinePrint;` — every call to `newlinePrint` invokes `print` with the literal `"\n"` baked in as the first argument.
- **Without args**: `--OV print myPrint;` — plain rename, exactly as before (Step 7 behavior).

**Fixed vs pass-through:**
Arguments supplied in the `--OV` declaration are **fixed/hardcoded at declaration time**. The new name does not accept additional caller-supplied arguments — it always calls the target with exactly the fixed arguments. To create a pass-through alias that still accepts caller arguments, use the plain rename form: `--OV print myPrint;`.

**User-defined functions:**
This works identically for user-defined functions (`--Function Role.Name (Args) { ... })`):
```arb
--Function util.greet(name) { return "Hello, " + name + "!"; }
--OV greet("World") defaultGreet;
// defaultGreet() → "Hello, World!"
```

**`<>` swap form:**
```arb
--OV funcA <> funcB;
```
Completely exchanges two functions — every call to `funcA` runs what `funcB` used to do, and vice versa. Swapping works across categories (builtin ↔ user function, etc.) and is **reversible** with a second `--OV ... <> ...` declaration. There is no arity restriction — if a swapped-in call is missing arguments the other function needs, a runtime error occurs when that function executes.

**Cross-category override flags:**
By default, `--OV` in one `.arb` file cannot reach into imported modules, loaded extensions, or child scripts. These can be explicitly unlocked:

| Flag | Unlocks |
|------|---------|
| `--ext.ov true;` | Overriding extension-provided functions |
| `--mod.ov true;` | Overriding imported-module functions |
| `--chd.ov true;` | Overriding child-script functions |

Each flag gates only its own category. Flags must appear at the top of the file, before any `--OV` declaration (same placement rule as `--ErrOV`). Attempting a cross-category override without the relevant flag raises a load-time error via the `try`/`catch` convention (Addition 6).

**Examples:**
```arb
// 1. Argument-aware --OV on a built-in
--OV print("\n") newlinePrint;
newlinePrint("First line");    // prints: \nFirst line
print("Normal");               // original print still works

// 2. Argument-aware --OV on a user function
--Function util.greet(name) { return "Hello, " + name + "!"; }
--OV greet("World") defaultGreet;
print(defaultGreet());         // → "Hello, World!"

// 3. --mod.ov + module override (success)
--mod.ov true;
--OV moduleFunc.localFunc;
// (module's function is now overridden)

// 4. --mod.ov counter-example (fails without flag)
// --OV moduleFunc.localFunc;
// → CatchableError: Cannot override module function 'localFunc' without --mod.ov true;

// 5. <> swap
--OV print <> input;
// Every call to print now runs input, and vice versa
```

### Addition 44 — `-w`/`-e` Flags for Warning/Error-Styled Output

The `print` function (and any styled text output) accepts `-w` and `-e` as flags that render using the script's current warning color (`fg: yellow` default) or error color (`fg: red` default), respectively.

**Syntax:**
```arb
print("text", -w);    // warning style (yellow)
print("text", -e);    // error style (red)
```

**Position independence:**
The flag can appear before or after any other styling arguments — both `print("text", -w, bg: black)` and `print("text", bg: black, -w)` are legal and equivalent.

**Conflict with explicit `fg:`:**
If a script passes an explicit `fg:` alongside `-w`/`-e`, the **explicit `fg:` wins**. This allows overriding the flag's color on a per-call basis.

**Interaction with `--ErrOV`:**
Since `-w`/`-e` reference the *current* warning/error color, an `--OV` change to that color (once unlocked via `--ErrOV`) is picked up automatically by any later `-w`/`-e` use:
```arb
--ErrOV true;
--OV defaults(err_fg) (err_fg: magenta);
print("Error in magenta", -e);    // renders in magenta, not red
--OV defaults(err_fg) (err_fg: red);
print("Back to red", -e);         // renders in red again
```

### Change — `for (i < N)` Loop Syntax

The `for` loop now supports a `<` (or `<=`) comparator form as an alternative to the `in`/`=`/`to` syntax:

```arb
for (i < 5) { ... }      // i goes 0..4
for (i <= 3) { ... }     // i goes 0..3
for (i < limit) { ... }  // using a variable as bound
for (i < randInt(3,6)) { ... }  // using a random value as bound
```

- `< N`: iterates from 0 to N-1 (exclusive)
- `<= N`: iterates from 0 to N inclusive
- The bound can be any expression: integer literal, variable, or function call returning a number

### Addition 45 — `let [type] name = value` — Typed Variable Declarations

Variables can now be declared with an explicit type annotation. If the type is omitted, auto-detection from the value works as before.

**Syntax:**
```arb
let [int] x = 42;
let [float] y = 3.14;
let [string] s = "hello";
let [boolean] flag = true;
let [list] arr = [1, 2, 3];
let [map] obj = map{ "a": 1 };
let [arb] data = arb{ 0x01("test"), 0x02(42) };
let [null] nothing = null;
```

**Supported types:**

| Type | Coercion |
|------|----------|
| `int` | `ArbInt(int(value))` |
| `float` | `ArbFloat(float(value))` |
| `string` | `ArbString(arb_to_string(value))` |
| `boolean` | `ArbBool(arb_truthy(value))` |
| `list` | `ArbList(...)` — wraps existing list, converts maps to values list |
| `map` | `ArbMap(...)` — wraps existing map, converts dict |
| `arb` | `ArbArb(...)` — wraps existing arb, converts list to arb |
| `null` | `ArbNull()` — always null |

**Auto-detection (no type hint):**
```arb
let x = 42;        // → ArbInt
let s = "hello";   // → ArbString
let arr = [1,2];   // → ArbList
// etc.
```

**Type coercion:**
When a type is specified, the value is coerced to that type:
```arb
let [int] x = "42";       // string "42" → ArbInt(42)
let [float] y = 10;       // int 10 → ArbFloat(10.0)
let [string] s = 123;     // int 123 → ArbString("123")
```

**With `const`:**
```arb
const [int] MAX = 100;    // typed constant
```

### Addition 46 — `openMedia()` Android/Termux Directory

On Android, `openMedia()` now opens files from the Termux data directory (`/data/data/com.termux/files/home/`) instead of the script's directory. This aligns with how Termux stores user files and makes `openMedia()` work correctly in the Android environment.

No syntax change is required — the path resolution is automatic based on the runtime environment.

### Addition 47 — `open.app()` Android `adr` Support

The `open.app()` function now accepts an `adr:` tag for launching apps on Android via `adb` (Android Debug Bridge):

```arb
// Launch by package name
open.app("", adr: "com.example.myapp");

// Launch specific activity
open.app("", adr: "am start -n com.example.myapp/.MainActivity");

// With additional args
open.app("", args: "--es greeting hello", adr: "com.example.myapp");
```

When `adr:` is provided, the function executes the value as an `adb` shell command instead of launching a desktop application. On non-Android environments without `adb`, a `try`/`catch` error is raised.

### color() Fix — ANSI Code Preservation

The `color()` block now correctly preserves ANSI styling codes when its result is:
- Concatenated with `+` operator: `print("Error: " + color("failed", fg: red))`
- Used in string interpolation: `print("Status: ${color("ok", fg: green)}")`
- Stored in variables, lists, or maps and later printed
- Returned from user-defined functions

Previously, `arb_to_string()` stripped the ANSI codes from `ArbColoredString` values, causing `color()` to silently lose all styling when used outside of a direct `print(color(...))` call. The fix ensures `arb_to_string()` calls `to_ansi_string()` on colored strings, preserving the escape codes through all string operations.

---

## Part 8: Addition 48 — List, Math & String Builtins

### Overview

33 new built-in blocks covering common list manipulation, mathematical, and string operations found in popular languages (Python, JavaScript, Ruby). These bring ArbPlus to **86 total builtins**.

### List Operations (14 blocks)

| Block | Signature | Description |
|-------|-----------|-------------|
| `append` | `append(list, item1, ...)` | Add item(s) to end of list (mutates in place, returns list) |
| `prepend` | `prepend(list, item1, ...)` | Add item(s) to beginning of list (mutates in place, returns list) |
| `insert` | `insert(list, index, item)` | Insert item at index (supports negative indexing) |
| `removeAt` | `removeAt(list, index)` | Remove and return item at index (supports negative indexing) |
| `pop` | `pop(list)` | Remove and return last item from list |
| `shift` | `shift(list)` | Remove and return first item from list |
| `reverse` | `reverse(list\|string)` | Return reversed copy of list or string |
| `sort` | `sort(list)` | Return sorted copy of list (numeric or string sort) |
| `indexOf` | `indexOf(list\|string, item)` | Return index of first match, or -1 if not found |
| `includes` | `includes(list\|string, item)` | Return true if collection contains item |
| `slice` | `slice(list\|string, start, end)` | Return slice from start to end (exclusive) |
| `flatten` | `flatten(list)` | Flatten one level of nested lists |
| `range` | `range(n)` or `range(start, end, step)` | Generate list of integers |
| `foreach` | `foreach(list, "funcName")` | Call named function for each (item, index) pair |

### Math Operations (8 blocks)

| Block | Signature | Description |
|-------|-----------|-------------|
| `abs` | `abs(n)` | Absolute value (returns int or float) |
| `round` | `round(n, decimals: 0)` | Round to optional decimal places (kwarg `decimals`) |
| `floor` | `floor(n)` | Round down to nearest integer |
| `ceil` | `ceil(n)` | Round up to nearest integer |
| `min` | `min(a, b, ...)` or `min(list)` | Return minimum value |
| `max` | `max(a, b, ...)` or `max(list)` | Return maximum value |
| `sum` | `sum(list)` | Sum all numeric elements |
| `clamp` | `clamp(n, min, max)` | Constrain value to [min, max] range |

### String Operations (11 blocks)

| Block | Signature | Description |
|-------|-----------|-------------|
| `replicate` | `replicate(str, n)` | Repeat string n times (named `replicate` not `repeat` to avoid keyword conflict) |
| `startsWith` | `startsWith(str, prefix)` | Check if string starts with prefix |
| `endsWith` | `endsWith(str, suffix)` | Check if string ends with suffix |
| `capitalize` | `capitalize(str)` | Capitalize first letter, lowercase rest |
| `titleCase` | `titleCase(str)` | Capitalize first letter of each word |
| `padLeft` | `padLeft(str, len, char: " ")` | Pad string on left to given length |
| `padRight` | `padRight(str, len, char: " ")` | Pad string on right to given length |
| `replaceAt` | `replaceAt(str, index, replacement)` | Replace character at index with new string |
| `format` | `format(template, ...args)` | Replace `{0}`, `{1}`, ... in template with args |
| `charCodeAt` | `charCodeAt(str, index)` | Return Unicode code point of character at index |
| `fromChar` | `fromChar(code)` | Convert Unicode code point to single-character string |

### `split()` Enhancement

`split(str, "")` now splits a string into individual characters (previously raised an error due to Python's empty-separator limitation).

### Naming Note

The string repeat function is named `replicate` (not `repeat`) because `repeat` is a reserved keyword in ArbPlus used for `repeat { } until (cond)` post-test loops.

### Example

```arb
// List operations
let [list] nums = [3, 1, 4, 1, 5, 9, 2, 6];
print(sort(nums));                    // [1, 1, 2, 3, 4, 5, 6, 9]
print(reverse(nums));                 // [6, 2, 9, 5, 1, 4, 1, 3]
print(slice(nums, 0, 3));             // [3, 1, 4]
print(indexOf(nums, 5));              // 4
print(includes(nums, 42));            // false

// Math operations
print(sum([1, 2, 3, 4, 5]));          // 15
print(min(5, 3, 8, 1));               // 1
print(max([5, 3, 8, 1]));             // 8
print(clamp(15, 0, 10));              // 10
print(round(3.14159, decimals: 2));   // 3.14

// String operations
print(replicate("ab", 3));            // ababab
print(capitalize("hello world"));     // Hello world
print(padLeft("42", 5, "0"));         // 00042
print(format("Hi {0}, you are {1}", "Bob", 30));  // Hi Bob, you are 30
print(charCodeAt("A", 0));            // 65
print(fromChar(66));                  // B

// foreach with named function
--Function pub.double(item, idx) {
    print("[${idx}] ${item} x2 = ${item * 2}");
}
foreach([1, 2, 3, 4], "double");
```
