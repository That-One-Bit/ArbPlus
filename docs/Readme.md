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
| OS Globals | `snap.time()`, `count.time()`, `wait(m,s,ms)`, `cs()`, `cs(scheme)`, `locale.prf`, `locale.cur`, `locale.alt`, `locale.check(loc)`, `battery()`, `network()`, `screen()`, `os.name`, `os.version` |
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
let ts = snap.time();                              // one-shot: "2026-07-23 12:39:00"
let detailed = snap.time(Year: 0, Month: 0, Day: 0); // "Year=2026, Month=7, Day=23"
let now = count.time();                              // live: re-samples on each call
wait(0, 2, 500);                                      // pause 2.5 seconds
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
battery()    // "85%"
network()    // true/false
screen()     // "1920x1080"
os.name      // "Linux"
os.version   // kernel version
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
| `>` terminator vs comparison | Context-dependent: `>` alone = terminator, `>=` = comparison |
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

### /n Newline Token & Brightness (Addition 5)
```arb
// /n becomes newline when displayed via print
print("Line 1/nLine 2/nLine 3");

// //n shows /n literally
print("Literal //n stays as /n");

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
| snap time | `snap.time(Year: y)` |
| count time | `count.time(MS: 0)` |
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
| /n newline | `print("a/nb")` |
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
| terminator | `;` (primary) or `>` (alternative) |

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
