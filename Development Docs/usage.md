# ArbPlus Usage Documentation

## Installation & Setup

### Running the Interpreter

```bash
python3 interpreter.py script.arb
```

The interpreter requires Python 3.8+. No external packages are needed as it uses only the standard library.

### Missing Toolchain Errors

The interpreter will return an error if one of the following toolchains is called but doesn't exist on the path.

| Feature | Required Tool | Error Message |
|---------|--------------|---------------|
| `c{ }` blocks | gcc, cc, or clang | "C block requires a C compiler (gcc/cc/clang) but none was found on PATH. Install a C compiler to use c{ } blocks." |
| `cmd{ }` blocks | cmd.exe (Windows) or sh (Linux/macOS) | Falls back to sh on non-Windows |
| `ps{ }` blocks | powershell or pwsh | Falls back to sh if not found |
| C/C++ Extensions | gcc/cc/clang | "C/C++ extension requires a C compiler but none was found." |

### Bundling Python with Interpreter

```bash
pip install pyinstaller
pyinstaller --onefile interpreter.py
# Does not include an Arb script
```

---

## Writing Your First Arb Script

Writing in Arb is simple, with easy functions such as print, input, and --Functions. Hello World in Arb is as simple as:

```arb
print("Hello World")
```

Although, to make your Arb file be professional and easier to read, add the #meta block:

```arb
#meta {
    // Applies every type of metadata field
    name: "Hello World";
    version: "1.0";
    author: "ThatOneBit";
    description: "Hello World";
    langauges: "Arb";
};

print("Hello World")
```

*Metadata entries can be accessed in functions using meta.'entry', whereas 'entry' is the name of the key

Running your file:

```bash
# For standalone
python interpreter.py script.arb

# For bundled
./ArbPlus.exe script.arb

# For bundled script
./Script.exe
```

---

## File Structure

Every `.arb` file follows this order:

1. `#meta { ... }` — Metadata Block
2. `#use 'shell';` — Shell Declarations
3. `--OV built-in new;` — Overrides
4. `--Function Role.Name() { ... }` — Functions
5. `Main body` — Non-Function Executable Statements

---

## Functions and Overrides

### Defining Functions

```arb
--Function pub.greet(name) {
    return "Hello, " .. name .. "!";
}

--Function util.calculate(x: int, y: int) {
    return add(x, y);
}
```

### Calling Functions

```arb
let msg = greet("World");
let sum = calculate(10, 20);
```

### Overrides (--OV)

```arb
--OV print myprint;
--OV len length;

myprint("This uses the overridden print!");
let n = length("hello");  // same as len("hello")
```

The original function name remains callable. The override creates an alias.

### Built-in Functions

| Category | Functions |
|----------|-----------|
| Arithmetic | `add(a,b)`, `sub(a,b)`, `mul(a,b)`, `div(a,b)`, `mod(a,b)`, `pow(a,b)` |
| String | `concat(...)`, `len(s)`, `upper(s)`, `lower(s)`, `trim(s)`, `split(s,d)`, `join(lst,d)`, `substr(s,n[,m])`, `replace(s,old,new)`, `contains(s,sub)` |
| I/O | `print(text, fg: color, bg: color)`, `input(prompt, fg: color, bg: color)` |
| Type | `toInt(v)`, `toFloat(v)`, `toString(v)`, `toBool(v)`, `typeof(v)` |
| File | `readFile(path)`, `fileExists(path)`, `writeFile(path,content,mode:)`, `buildFile(path,content)`, `encodeImage(path)`, `decodeImage(arb,path)`, `openMedia(path)`, `openBrowser(url)` |
| Addressing | `addr.hex(val)`, `addr.binary(val)`, `addr.meta("marker")`, `txtRC(row,col,data)` |
| Directory | `dir.list(path[,filter])`, `dir.name(path,newname)`, `dir.make(path,files)`, `dir.del(path)` |
| OS Globals | `snap.time()`, `count.time()`, `wait(m,s,ms)`, `cs()`/`os.CS()`, `locale.prf`, `locale.cur`, `locale.alt`, `locale.check(loc)`, `os.Battery()`/`battery()`, `os.Network()`/`network()`, `os.Screen()`/`screen()`, `os.Name()`/`os.name`, `os.Version()`/`os.version` |
| Extensions | `loadExt(path, lang)` |

---

## Type System Quick Reference

| Type | Description | Example |
|------|-------------|---------|
| `int` | 64-bit integer | `42`, `0x1A` |
| `float` | Double-precision | `3.14` |
| `string` | UTF-8 text | `"hello"` |
| `boolean` | true/false | `true`, `false` |
| `array` | Fixed, homogeneous | (constructed via builtins) |
| `list` | Dynamic, heterogeneous | `[1, "two", 3.0]` |
| `arb` | Tagged hex container | `arb{ 0x01("hi"), 0x02(42) }` |

### arb Sub-Type Tags
| Tag | Hex | Type |
|-----|-----|------|
| str | 0x01 | String |
| int | 0x02 | Integer |
| float | 0x03 | Float |
| bool | 0x04 | Boolean |
| image | 0x10 | Base64 image |
| raw | 0xFF | Raw bytes |

### Coercion
```arb
toInt("42")     // → 42
toFloat(42)     // → 42.0
toString(true)  // → "true"
toBool(0)       // → false
```

---

## File Operations Quick Reference

### Reading
```arb
if (fileExists("./data.txt")) {
    let content = readFile("./data.txt");
    print(content);
}
```

### Addressing
```arb
addr.hex(0x1A)           // → "0x1A"
addr.binary(1024)        // → "0b10000000000"
addr.meta("EXIF:DateTaken")
```

### txtRC (Row/Column Access)
```arb
let data = readFile("./data.csv");
txtRC(2, 3, data)  // row 2, col 3 (1-based indexing)
```
- 1-based indexing
- Auto-detects delimiter: tab, comma, semicolon, or whitespace
- Out of bounds raises error

### Writing
```arb
writeFile("./out.txt", "content");                     // overwrite (default)
writeFile("./out.txt", "content", mode: error);          // error if exists
buildFile("./out.txt", "content");                       // auto-rename if exists
```

### Image Encoding
```arb
let img = encodeImage("./photo.png");   // → arb with image tag
decodeImage(img, "./restored.png");      // write back to file
```

### Media & Browser
```arb
openMedia("./image.jpg");   // opens in OS default viewer
openBrowser("https://example.com");
```

---

## Directory Operations Quick Reference

```arb
dir.make("./newdir", "a.txt;b.txt;c.arb");   // creates dir with empty files
dir.list("./newdir");                         // all entries
dir.list("./newdir", "files");                // files only
dir.list("./newdir", "folders");              // folders only
dir.name("./newdir", "renamed");              // rename
dir.del("./newdir");                          // recursive delete
```

### Relative Paths
- `./` — current folder (relative to script location)
- `../` — parent folder
- `../../` — multi-level parent

---

## Control Flow Quick Reference

### Conditionals
```arb
if (x > 10) { print("big"); }
elif (x > 5) { print("medium"); }
else { print("small"); }

if (not isEmpty) { print("has data"); }
```

### Loops
```arb
for (i = 1 to 10) { print(i); }
for (i = 0 to 100 step 2) { print(i); }
for (item in myList) { print(item); }
while (x > 0) { x = x - 1; }
```

### break
```arb
for (i = 1 to 100) {
    if (i > 10) { break; }
}
```

### Ternary
```arb
let label = (score >= 60 ? "pass" : "fail");
```

### exit / quit
```arb
exit 1;   // terminate with code 1
quit;      // terminate with code 0
```

---

## I/O with Color

### Named Colors
```arb
print("error", fg: red);
print("warning", fg: yellow, bg: black);
print("success", fg: green);
input("Name: ", fg: cyan);
```

### Available Colors
black, red, green, yellow, blue, magenta, cyan, white, plus bright_ variants (bright_red, etc.)

### Hex Colors
```arb
print("custom", fg: #FF6600, bg: #1A1A2E);
```

---

## OS Globals Quick Reference

### Time
```arb
let ts = snap.time();                        // one-shot: "2026-08-01 14:37:00"
let minute = snap.time("minute");              // → "37" (presence-based)
let hm = snap.time("hour", "minute");          // → "14 37"
let now = count.time();                        // "14:37:00.123"
wait(0, 2, 500);                                // pause 2.5 seconds
```

### Color Scheme
```arb
let scheme = cs();       // "light" or "dark"
let isDark = cs(dark);    // true/false
let isLight = cs(light);  // true/false
```

### Locale
```arb
locale.prf               // preferred locale
locale.cur               // current active locale
locale.alt               // alternatives ("en-US, en-GB")
locale.check("en_GB")    // boolean: is locale available?
```

### Other Globals
```arb
os.Battery()   // 85  (alias: battery())
os.Network()   // true/false  (alias: network())
os.Screen()    // "1920x1080"  (alias: screen())
os.Name()       // "Linux"  (alias: os.name)
os.Version()    // kernel version  (alias: os.version)
os.CS()         // "dark"/"light"  (alias: cs())
```

---

## Extensions

### Loading
```arb
loadExt("./myext.py", "python");
loadExt("./myext.c", "c");
loadExt("./myext.cpp", "c++");
```

### Calling Extension Functions
```arb
let result = ext.myFunction(arg1, arg2);
```

### Writing a Python Extension
```python
def my_function(args, kwargs):
    # args is a list of ArbValue objects
    # kwargs is a dict of ArbValue objects
    val = args[0].py() if args else ""
    return f"Processed: {val}"  # return plain Python value

def register(engine):
    engine.register_extension("ext.myFunction", my_function)
    # Hooks: extend existing builtins
    engine.register_hook("snap.time", my_time_hook)

def my_time_hook(args, kwargs, original_func):
    import datetime
    return datetime.datetime.now().strftime("%H:%M:%S.%f")
```

### Writing a C Extension
```c
ArbValue ext_double(int argc, ArbValue* args) {
    ArbValue r;
    r.type = ARB_INT;
    r.data.int_val = args[0].data.int_val * 2;
    return r;
}

void arbplus_register(ArbEngine* engine) {
    engine->register_func("ext.double", ext_double);
}
```

---

## Common Pitfalls

| Pitfall | Fix |
|---------|-----|
| arb sub-type tag mixups | Check the tag map: str=0x01, int=0x02, float=0x03, bool=0x04 |
| Forgetting to declare a shell | Add `#use batch;` or `#use powershell;` before using `cmd{}`/`ps{}` |
| Off-by-one in txtRC | txtRC uses 1-based indexing (first row = 1, first column = 1) |
| Unsandboxed variable write paths | Validate paths before writing: check for `..` traversal |
| Confusing snap.time vs count.time | snap.time = one-shot; count.time = live/re-sampling |
| Not checking fileExists before readFile | Always check first: `if (fileExists(path)) { readFile(path); }` |
| `>` comparison | Greater-than comparison operator (not a terminator) |
| Bare identifiers as arguments | Undefined identifiers fall back to string literals (for color names, enums) |
| Extension returns ArbValue | Return plain Python values; the interpreter wraps them automatically |

---

## v2.0 New Features

### String Interpolation (Addition 1)
```arb
let name = "World";
print("Hello, ${name}!");
print("Count: ${count} and doubled: ${count * 2}");
// Undefined variables produce empty string:
print("Missing: ${nonexistent}");  // → "Missing: "
```

### Map Type (Addition 4)
```arb
// Create a map
let config = map{ "name": "ArbPlus", "version": "2.0", "debug": true };

// Access by key
print(config.name);         // → "ArbPlus"
print(config["version"]);  // → "2.0"

// Add/update keys
config.newKey = "added";

// Map operations
print(keys(config));        // → ["name", "version", "debug", "newKey"]
print(values(config));      // → ["ArbPlus", "2.0", true, "added"]
print(has(config, "name")); // → true
print(has(config, "xyz"));  // → false
```

### repeat...until (Addition 6)
```arb
// Post-test loop: always executes at least once
let i = 0;
repeat {
    i = i + 1;
    print("iteration ${i}");
} until (i >= 5);

// Break works inside repeat too
let j = 0;
repeat {
    j = j + 1;
    if (j > 3) { break; }
    print("j = ${j}");
} until (false);
```

### switch/case (Addition 9)
```arb
switch (grade) {
    case "A": { print("Excellent!"); }
    case "B": { print("Good job!"); }
    case "C": { print("Passing"); }
    case "F": { print("Failed"); }
    default: { print("Unknown grade"); }
}
```

### try/catch/finally (Addition 9)
```arb
try {
    let data = readFile("./missing.txt");
} catch (err) {
    print("Caught error: ${err}");
} finally {
    print("Cleanup always runs");
}

// try with finally only (no catch)
try {
    print("In try block");
} finally {
    print("Cleanup runs");
}
```

### and / or Keywords (Addition 10)
```arb
// These are equivalent:
if (a && b) { }
if (a and b) { }

if (a || b) { }
if (a or b) { }

// Can be mixed:
if (a and b or c) { }
```

### Newline Escape & Brightness (Addition 5)
```arb
// \n is the newline escape (standard, applied at lexer time)
print("Line 1\nLine 2\nLine 3");

// Text brightness: dim, normal (default), bright
print("Dim text", fg: cyan, b: dim);
print("Normal text", fg: cyan, b: normal);
print("Bright text", fg: cyan, b: bright);
```

### Default Color Override (Addition 7)
```arb
// Set default colors for all print/input calls
--OV defaults(fg, bg, b) (fg: cyan, bg: black, b: bright);

// All subsequent print calls use these defaults unless overridden
print("This is cyan on black, bright");
print("Override", fg: red);  // overrides fg only, bg and b still default
```

### Cross-Type Comparison (Addition 8)
```arb
// String vs int with == and != (coerced)
print("42" == 42);   // → true
print("5" != 3);     // → true

// Numeric comparison coerces string-looking values
print("5" < "10");   // → false (string comparison: '5' > '1')
print(5 < 10);       // → true (numeric comparison)
```

### Random Numbers (Addition 3)
```arb
let r = random();          // float in [0.0, 1.0)
let n = randInt(1, 100);   // int in [1, 100]

// Seeded (reproducible)
random.seed(42);
print(randInt(1, 10));     // → always 2
print(randInt(1, 10));     // → always 1

// Reseed same value → same sequence
random.seed(42);
print(randInt(1, 10));     // → 2 again
```

### CLI Arguments & Environment (Addition 3, 12)
```arb
// Run: python3 interpreter.py script.arb hello world 42

print(args());     // → ["hello", "world", "42"]
print(args(0));    // → "hello"
print(args(1));    // → "world"

print(env("HOME"));     // → "/home/user"
print(env("PATH"));     // → "/usr/bin:..."
print(env("MISSING"));  // → ""
```

### Module Imports (Addition 11)
```arb
// mymods.arb - a module file
--Function util.greet(name) {
    return "Hello, ${name}!";
}

--Function util.double(x: int) {
    return add(x, x);
}

// main.arb - imports the module
#import mymods;

print(mymods.greet("Alice"));      // → "Hello, Alice!"
print(mymods.double(21));          // → 42
```
Module files must be in the same directory as the importing script. Functions are accessed via `ModuleName.FunctionName()`.

### open.url / open.app / bindKey (Addition 2)
```arb
// Open a URL in the default browser
open.url("https://example.com/search?q=${query}");

// Launch an OS application
open.app("gimp", args: "photo.png");

// Register key bindings (for interactive mode)
bindKey("F1", "showHelp");
bindKey("Ctrl+C", "exitScript");
```

### Map Builtins (Addition 4)
| Function | Description |
|----------|-------------|
| `keys(map)` | Returns list of map keys |
| `values(map)` | Returns list of map values |
| `has(map, key)` | Returns boolean: does map contain key? |

### New Builtins Summary (v2.0)
| Category | Functions |
|----------|-----------|
| Random | `random()`, `randInt(min,max)`, `random.seed(n)` |
| Map | `keys(m)`, `values(m)`, `has(m,key)` |
| CLI | `args()`, `args(index)` |
| Env | `env("VAR")` |
| Open | `open.url(url)`, `open.app(name, args: val)` |
| Keys | `bindKey(combo, funcName)` |

## Quick-Reference Syntax Table

| Feature | Syntax |
|---------|--------|
| Metadata | `#meta { name: "x"; version: "1.0"; }` |
| Declare shell | `#use batch;` |
| Import | `#import module;` |
| Override | `--OV print myprint;` |
| Function | `--Function pub.name(args) { body }` |
| Variable | `let x = value;` / `const x = value;` |
| String concat | `a .. b` or `concat(a, b)` |
| Swap | `a <> b` |
| Shell escape | `cmd{ shell code }` |
| Inline C | `c{ C code }` |
| arb literal | `arb{ 0x01("str"), 0x02(42) }` |
| if/elif/else | `if (cond) { } elif (cond) { } else { }` |
| not | `if (not cond) { }` |
| for range | `for (i = 1 to 10 step 2) { }` |
| for in | `for (item in list) { }` |
| while | `while (cond) { }` |
| break | `break;` |
| ternary | `(cond ? a : b)` |
| exit | `exit 0;` |
| colored print | `print(text, fg: red, bg: black)` |
| input | `input("prompt: ", fg: cyan)` |
| read file | `readFile(path)` |
| write file | `writeFile(path, content)` |
| build file | `buildFile(path, content)` |
| file exists | `fileExists(path)` |
| addr hex | `addr.hex(0x1A)` |
| txtRC | `txtRC(row, col, data)` |
| dir list | `dir.list(path, "files")` |
| dir make | `dir.make(path, "a.txt;b.txt")` |
| dir name | `dir.name(path, newname)` |
| dir del | `dir.del(path)` |
| snap time | `snap.time("minute")` → `"37"` |
| count time | `count.time("hour")` → `"14"` |
| wait | `wait(minutes, seconds, ms)` |
| color scheme | `cs()` / `cs(dark)` |
| locale | `locale.prf` / `locale.check("en")` |
| **v2.0 Features** | |
| string interp | `"Hello ${name}!"` |
| map literal | `map{ "key": value }` |
| map access | `m.key` or `m["key"]` |
| map assign | `m.key = value` |
| repeat/until | `repeat { } until (cond)` |
| switch/case | `switch(x) { case "A": { } default: { } }` |
| try/catch | `try { } catch(e) { } finally { }` |
| and/or | `if (a and b or c) { }` |
| \n newline | `print("a\\nb")` |
| brightness | `print("x", b: bright)` |
| default colors | `--OV defaults(fg,bg,b) (fg: cyan, b: bright)` |
| random | `random()`, `randInt(1,100)`, `random.seed(42)` |
| CLI args | `args()`, `args(0)` |
| env var | `env("HOME")` |
| map ops | `keys(m)`, `values(m)`, `has(m,"k")` |
| open url | `open.url("https://...")` |
| open app | `open.app("gimp", args: "file.png")` |
| bind key | `bindKey("F1", "help")` |
| module import | `#import mymods;` → `mymods.func()` |
| load extension | `loadExt(path, lang)` |
| comment | `// single line` / `/* multi line */` |
| terminator | `;` (primary) or newline |

### v2.0 Additions 24-27

| Feature | Syntax |
|---------|--------|
| run.arb() | `let result = run.arb("child.arb", greeting: "hi", count: 42);` |
| dl.url() | `let path = dl.url("https://...", filename: "file.txt");` |
| --clean | `--clean;` (collect), `--clean stop;`, `--clean restart;`, `--clean count;` |
| return() any type | `return(42);` / `return("text");` / `return(map{...});` / `return();` (null) |
| --F delegate | `--F role.funcName(args);` — delegates return to another function |
| null literal | `if (x == null) { }` — null keyword for void/empty comparisons |


## Part 4 Features (Additions 26-27 + Extras)

| Feature | Syntax | Description |
|---------|--------|-------------|
| Inline Python | `py{ ... }` | Execute raw Python in the same process |
| Python stdlib only | (enforced) | Only standard-library imports allowed |
| File loading | `c{$!path}` `py{$!path}` `cmd{$!path}` | Load block code from external file |
| Increment | `i++` | Shorthand `i = i + 1` as statement |
| Decrement | `k--` | Shorthand `k = k - 1` as statement |
| Forward decl | `let [name];` | Declare variable without value (null) |
| var() | `var("name")` | Unquoted variable reference |
| count.time live | `count.time(live: true, MS: 1000)` | Live updating clock |
| snap.time | `snap.time()` | Timestamp snapshot |

### py{ } Block Examples

```
// Math via Python
let x = 10;
let result = 0;
py{
    import math
    result = math.factorial(x)
}
print("10! =", result);

// JSON processing
let raw = '{"items": [1, 2, 3]}';
let count = 0;
py{
    import json
    obj = json.loads(raw)
    count = len(obj["items"])
}
print("Item count:", count);

// Third-party import caught
try {
    py{ import numpy }
} catch (e) {
    print("Blocked:", e);
}
```

### $! File Loading Examples

```
// Write C code to file, then compile+run via $!
buildFile("hello.c", "#include <stdio.h>\nint main() {\n    printf(\"Hi!\\n\");\n    return 0;\n}\n");
let cPath = "hello.c";
c{$!cPath}

// Load Python script from file
buildFile("calc.py", "import math\nprint(f'pi = {math.pi}')\n");
let pyPath = "calc.py";
py{$!pyPath}

// Run existing shell script
let shPath = "deploy.sh";
cmd{$!shPath}
```

### Shorthand Arithmetic

```
let i = 0;
while (i < 5) {
    print(i);
    i++;
}

let n = 10;
n--;
n--;
print(n);  // 8
```

### Forward Declaration

```
let [maybe_later];
print(maybe_later);  // null
maybe_later = "assigned now";
print(maybe_later);  // "assigned now"
```

### var() Usage

```
let color = "cyan";
let bg = "black";
print("Color:", var("color"));
--OV defaults(fg, bg, b) (fg: var("color"), bg: var("bg"), b: bright);
```

### count.time vs snap.time

```
// snap.time: full timestamp for logging
print("Event at:", snap.time());  // 2026-07-25 18:30:00

// count.time: current time, can go live
print("Now:", count.time());  // 18:30:00.123

// Live clock (blocks execution, updates every 1000ms)
count.time(live: true, MS: 1000);

// Assigning captures the moment, NOT a live feed
let timestamp = count.time();
// timestamp holds the value from this call, doesn't auto-update
```

## Part 5 Features (Additions 30–36)

| Addition | Feature | Syntax | Example |
|----------|---------|--------|---------|
| 30 | `--ErrOV` color gate | `--ErrOV true;` then `--OV defaults(warn_fg, err_fg) (...)` | Top-level, before functions |
| 31 | Hex/RGB/OKLCH colors | `color("text", fg: "#ff6600")`, `fg: "rgb(100,200,50)"`, `fg: "oklch(0.7,0.15,240)"` | Works in color(), print overrides, --OV |
| 32 | Colored output extension | `loadExt("extensions/ext_colors.py", "python"); ext_colors.color_text(...)` | Also importable from py{} blocks |
| 33 | Parser fix | Commas and `>` in color() args parsed correctly | `color("text", fg: red, bg: white, b: bright)` |
| 34 | meta.* variables | `meta.name`, `meta.version`, `meta()` | Returns metadata fields, filters internal keys |
| 35 | Arb naming | Product: ArbPlus, Language: Arb, Extension: .arb | Convention, not a function |
| 36 | file() type | `let f = file("path.txt"); readFile(f); fileExists(f);` | Returns ArbFile reference with resolved path |


## Part 6 Features (Additions 37–42)

### `--OV` Universal Override (Addition 37)

`--OV` works on **every** block, not just `print`. The override automatically covers all forms of a built-in — statement form and inline-assignment form:

```arb
--OV input myinput;

// Both forms work with the alias:
myinput("Enter name: ");           // statement form
let name = myinput("Enter: ");      // inline-assignment form

--OV snap.time mytime;
let ts = mytime();                   // works
```

This is a general rule: any `--OV builtinName alias;` alias intercepts the function at the builtins table level, so every call site using the alias invokes the original function regardless of context.

### VS Code Extension (Addition 39)

Install the VS Code extension from `vscode-arbplus/`:
- Open the folder in VS Code, press F5 to run the extension in debug mode
- Or install the `.vsix` file: `code --install-extension arbplus-0.1.0.vsix`

Features: syntax highlighting, go-to-definition, hover provider with function docs, semantic token coloring (builtins vs user functions vs extensions).

The TextMate grammar (`syntaxes/arbplus.tmLanguage.json`) covers all 88 blocks, comments, metadata blocks, string interpolation, keywords, color arguments, and `--Function`/`--OV`/`--clean`/`--F` directives. A `color-guide.json` file maps each scope to a recommended color for theme authors.

### Post-Addendum Features

#### `open.app` with Android Support (`adr:`)

```arb
// Launch Android app by package name
open.app("", adr: "com.example.myapp");

// Launch specific activity via intent string
open.app("", adr: "am start -n com.example.myapp/.MainActivity");

// With intent extras
open.app("", args: "--es greeting hello", adr: "com.example.myapp");

// Error handling with try/catch
try {
    open.app("", adr: "com.example.myapp");
} catch (e) {
    print("Launch failed: " + e);
}
```

- Uses `adb` (Android Debug Bridge) — must be installed and in PATH
- Checks for connected device via `adb devices`
- Bare package name → launches default activity
- Full intent string → passes directly to `adb shell`
- Device/package errors are catchable `ArbPlusError`s

#### `snap.time()` — Reworked (Presence-Based)

```arb
snap.time()                        // → "2026-08-01 14:37:00" (full timestamp)
snap.time("minute")                // → "37"
snap.time("hour", "minute")         // → "14 37"
snap.time(minute: true)             // → "37" (kwarg form)
snap.time("year", "month", "day")   // → "2026 8 1"
```

No `Key=val` output — returns raw values only. Use `print()` with concatenation for formatted output:
```arb
print("Time: " + snap.time("hour") + ":" + snap.time("minute"));
```

#### `count.time()` — Reworked (Presence-Based)

```arb
count.time()                    // → "14:37:00.123"
count.time("minute")             // → "37"
count.time("hour", "minute")     // → "14 37"
count.time(live: true, MS: 1000) // live clock (blocks)
```

#### OS Functions with `os.` Prefix

All OS functions now have canonical `os.` prefixed names. Old bare names still work as aliases.

```arb
os.Battery()    // battery level (alias: battery())
os.Screen()     // screen resolution (alias: screen())
os.Network()   // network status (alias: network())
os.Name()       // OS name (alias: os.name)
os.Version()    // OS version (alias: os.version)
os.CS()         // color scheme (alias: cs())
```

All functions support Android via `adb` when a device is connected. `os.CS()` / `cs()` properly detects Android night mode.

#### `bindKey()` Outside Loops

```arb
// Standalone — installs signal handler for CTRL+C
bindKey("CTRL+C", "quit");

print("Press CTRL+C to quit.");
while (true) {
    wait(0, 0, 500);
}
```

Works as a standalone statement now. CTRL+C/CTRL+Z install signal handlers; other keys attempt the `keyboard` library if installed.

### Updated Quick-Reference Table

| Feature | Syntax |
|---------|--------|
| **Part 6 Additions** | |
| `--OV` universal | `--OV input myinput;` — overrides all forms (statement + inline) |
| VS Code extension | `vscode-arbplus/` — `.vsix` install, TextMate grammar + semantic tokens |
| open.app Android | `open.app("", adr: "com.example.app")` |
| snap.time reworked | `snap.time("minute")` → `"37"` (presence-based, raw values) |
| count.time reworked | `count.time("hour")` → `"14"` (presence-based, raw values) |
| os.* functions | `os.Battery()`, `os.Screen()`, `os.Network()`, `os.Name()`, `os.Version()`, `os.CS()` |
| bindKey standalone | `bindKey("CTRL+C", "quit")` — works outside repeat/until |
| TextMate color guide | `vscode-arbplus/syntaxes/color-guide.json` — scope-to-color mapping |

---

## Maps — Extended Guide

### Creating Maps

```arb
let config = map{ "name": "ArbPlus", "version": 2, "debug": true };
```

- Keys are string literals (quoted)
- Values can be any type: `int`, `float`, `string`, `bool`, `list`, `map`, `arb`, `null`
- Insertion order is preserved

### Accessing Map Values

```arb
// Dot notation — key must be a valid identifier
print(config.name);          // → "ArbPlus"

// Bracket notation — works with any key string
print(config["version"]);   // → 2

// Missing keys return empty string (not an error)
print(config.nonexistent);  // → ""
```

### Updating Maps

```arb
config.newKey = "added";
config["version"] = 3;
config.numbers = [1, 2, 3];
```

### Map Builtins

```arb
keys(m)          // → list of all keys
values(m)        // → list of all values
has(m, "key")   // → true/false
len(m)            // → number of entries
```

### Nested Maps

Maps can contain maps as values — chain dot notation to access nested keys:

```arb
let app = map{
    "server": map{
        "host": "localhost",
        "port": 8080
    },
    "auth": map{
        "user": "admin",
        "pass": "secret",
        "roles": map{
            "admin": true,
            "readonly": false
        }
    }
};

print(app.server.host);          // → "localhost"
print(app.server.port);           // → 8080
print(app.auth.roles.admin);      // → true

// Update nested values
app.server.port = 3000;
app.auth.pass = "newpass";
```

### Maps Containing Arbs

Arb values can be stored as map values and accessed normally:

```arb
let record = map{
    "name": "test.dat",
    "size": 1024,
    "raw_data": arb{ 0x01("header"), 0x02(42), 0x03(3.14) }
};

// Access arb elements through the map
print(record.name);           // → "test.dat"
print(record.raw_data[0]);    // → "header"
print(record.raw_data[1]);    // → 42
print(record.raw_data[2]);    // → 3.14
print(typeof(record.raw_data)); // → "arb"

// Iterate over arb inside map
for (item in record.raw_data) {
    print(item);
}
```

### Maps Inside Arbs

Arb containers support only predefined tags (str, int, float, bool, image, raw). Maps stored in arbs are serialized as `raw` (0xFF) with their string representation. For structured nesting, prefer maps-of-maps:

```arb
// Recommended — nest maps inside maps
let data = map{
    "person": map{
        "name": "Alice",
        "address": map{ "city": "NYC", "zip": "10001" }
    }
};

// Arb is for binary/tagged data, not structured nesting
let binary = arb{ 0x01("meta"), 0xFF("raw bytes") };
```

### Iterating Maps

```arb
let m = map{ "a": 1, "b": 2, "c": 3 };

// Iterate keys
for (k in keys(m)) {
    print(k, "=", m[k]);
}

// Iterate values
for (v in values(m)) {
    print(v);
}
```

---

## Arbs — Extended Guide

### Arb Sub-Type Tags

| Tag | Hex | Type |
|-----|-----|------|
| str | 0x01 | String (UTF-8) |
| int | 0x02 | 64-bit integer |
| float | 0x03 | Double-precision float |
| bool | 0x04 | Boolean |
| image | 0x10 | Base64 image |
| raw | 0xFF | Raw bytes |

### Creating Arbs

```arb
let data = arb{ 0x01("hello"), 0x02(42), 0x03(3.14), 0x04(true) };
let empty = arb{};
let withRaw = arb{ 0x01("label"), 0xFF("raw data") };
```

### Accessing Arb Elements

```arb
data[0]      // → "hello" (decoded to string)
data[1]      // → 42 (decoded to int)
data[2]      // → 3.14 (decoded to float)
data[3]      // → true (decoded to bool)

len(data)    // → 4
typeof(data) // → "arb"
typeof(data[0]) // → "string"
typeof(data[1]) // → "int"
```

### Iterating Arbs

```arb
for (item in data) {
    print(item);
}
// hello, 42, 3.14, true
```

### Image Encoding with Arbs

```arb
let img = encodeImage("./photo.png");  // → arb{ 0x10(base64data) }
decodeImage(img, "./output.png");       // → writes decoded image
```

### Arbs Inside Maps

```arb
let container = map{
    "name": "binary_data",
    "payload": arb{ 0x01("magic"), 0x02(256), 0x04(false) }
};

print(container.payload[0]);    // → "magic"
print(container.payload[1]);    // → 256
print(container.payload[2]);    // → false
```

### Arbs Inside Arbs

Arb containers can nest by encoding one arb as a `raw` element in another. The inner arb is stored as raw bytes:

```arb
let inner = arb{ 0x01("inside"), 0x02(99) };
let outer = arb{ 0x01("wrapper"), 0xFF(inner) };

// outer[0] → "wrapper" (decoded string)
// outer[1] → raw representation of inner arb
```

Note: nested arb elements aren't individually indexable through the outer container. For structured nesting with direct access, use maps or lists to hold multiple arb containers.

## Set-7 Features (Additions 43-47)

### Argument-Aware `--OV` Overrides

`--OV` can now supply fixed arguments as part of the override:

```arb
// Fixed arg: always calls print with "\n"
--OV print("\n") newlinePrint;
newlinePrint("First line");    // → "\nFirst line"

// Plain rename (no args) — same as before
--OV print myPrint;
```

Works identically on user-defined functions:

```arb
--Function util.greet(name) { return "Hello, " + name + "!"; }
--OV greet("World") defaultGreet;
print(defaultGreet());         // → "Hello, World!"
```

### `<>` Swap Form

Completely exchange two functions:

```arb
--OV print <> input;
// Every call to print now runs input, and vice versa
// Reversible with another --OV print <> input;
```

### Cross-Category Override Flags

| Flag | Unlocks |
|------|---------|
| `--ext.ov true;` | Extension functions |
| `--mod.ov true;` | Module functions |
| `--chd.ov true;` | Child script functions |

Must appear at top of file before any `--OV`. Without the flag, a cross-category override raises a catchable error.

### `-w`/`-e` Styled Output Flags

```arb
print("Warning!", -w);              // yellow (warning color)
print("Error!", -e);                 // red (error color)
print("Warning", -w, bg: black);    // with background — order doesn't matter
print("Custom", -e, fg: blue);       // explicit fg overrides -e color
```

With `--ErrOV` to change error color:

```arb
--ErrOV true;
--OV defaults(err_fg) (err_fg: magenta);
print("Magenta error", -e);          // renders in magenta
```

### `for (i < N)` Loop Syntax

```arb
for (i < 5) { print(i); }        // 0..4
for (i <= 3) { print(i); }       // 0..3
let limit = 4;
for (i < limit) { print(i); }   // 0..3
let n = randInt(3, 6);
for (i < n) { print(i); }        // 0..n-1 (random bound)
```

### `let [type] name = value` — Typed Declarations

```arb
let [int] x = 42;
let [float] y = 3.14;
let [string] s = "hello";
let [boolean] flag = true;
let [list] arr = [1, 2, 3];
let [map] obj = map{ "a": 1, "b": 2 };
let [arb] data = arb{ 0x01("test"), 0x02(42) };
let [null] nothing = null;

// Auto-detection still works when type is omitted
let auto = 42;        // → ArbInt

// Type coercion
let [int] coerced = "42";    // string → int 42
let [float] f = 10;          // int → float 10.0

// With const
const [int] MAX = 100;
```

### `openMedia()` on Android

On Android/Termux, `openMedia()` resolves files from the Termux home directory (`/data/data/com.termux/files/home/`) instead of the script directory. No syntax change needed — automatic based on runtime environment.

### `open.app()` Android `adr` Support

```arb
// Launch by package name
open.app("", adr: "com.example.myapp");

// Launch specific activity
open.app("", adr: "am start -n com.example.myapp/.MainActivity");

// With additional args
open.app("", args: "--es greeting hello", adr: "com.example.myapp");
```

---

## Addition 48 — List, Math & String Builtins

33 new built-in blocks for common list, math, and string operations.

### List Operations

```arb
let [list] nums = [3, 1, 4, 1, 5, 9, 2, 6];

// Mutation (returns the modified list)
append(nums, 7);            // [3, 1, 4, 1, 5, 9, 2, 6, 7]
prepend(nums, 0);           // [0, 3, 1, 4, 1, 5, 9, 2, 6, 7]
insert(nums, 2, 99);        // insert 99 at index 2
print(pop(nums));           // 7 (removes last)
print(shift(nums));         // 0 (removes first)
print(removeAt(nums, 1));   // removes and returns item at index 1

// Non-mutating (returns new value)
print(sort(nums));          // sorted copy
print(reverse(nums));       // reversed copy
print(reverse("hello"));    // olleh (works on strings too)
print(slice(nums, 0, 3));   // first 3 elements
print(flatten([[1,2], 3, [4,5]]));  // [1, 2, 3, 4, 5]
print(range(5));            // [0, 1, 2, 3, 4]
print(range(2, 10, 2));     // [2, 4, 6, 8]

// Search
print(indexOf(nums, 5));    // 4 (or -1 if not found)
print(includes(nums, 42));  // false

// Iteration
--Function pub.process(item, idx) {
    print("[${idx}] ${item}");
}
foreach(nums, "process");
```

### Math Operations

```arb
print(abs(-42));            // 42
print(abs(-3.14));           // 3.14
print(round(3.7));           // 4
print(round(3.14159, decimals: 2));  // 3.14
print(floor(3.9));           // 3
print(ceil(3.1));            // 4
print(min(5, 3, 8, 1));     // 1
print(max([5, 3, 8, 1]));    // 8
print(sum([1, 2, 3, 4, 5])); // 15
print(clamp(15, 0, 10));    // 10
print(clamp(-5, 0, 10));    // 0
print(clamp(5, 0, 10));     // 5
```

### String Operations

```arb
print(replicate("ab", 3));           // ababab
print(startsWith("hello", "he"));     // true
print(endsWith("hello", "lo"));       // true
print(capitalize("hello world"));     // Hello world
print(titleCase("hello world"));      // Hello World
print(padLeft("42", 5, "0"));         // 00042
print(padRight("42", 5, "_"));        // 42___
print(replaceAt("hello", 1, "X"));    // hXllo
print(format("Hi {0}, age {1}", "Bob", 30));  // Hi Bob, age 30
print(charCodeAt("A", 0));             // 65
print(fromChar(66));                   // B

// split() now supports empty separator (splits into characters)
print(split("hello", ""));             // [h, e, l, l, o]
```

> **Note:** The string repeat function is `replicate`, not `repeat` — `repeat` is a keyword reserved for `repeat { } until (cond)` loops.
