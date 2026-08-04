# ArbPlus Formal Grammar (EBNF)

This grammar covers all features from Steps 1–14 plus the 12 Additions (v2.0).

## Notation
- `::=` — production
- `|` — alternation
- `[...]` — optional (0 or 1)
- `{...}` — repetition (0 or more)
- `(...)` — grouping
- `"..."` — terminal string literal
- Comments follow `//`

---

## Program Structure (Step 1)

```ebnf
program       ::= [metadata] {declaration} {override} {function_def} {statement} ;

metadata      ::= "#meta" "{" {meta_entry} "}" ;
meta_entry    ::= IDENT ":" meta_value {terminator} ;
meta_value    ::= STRING | IDENT | INT | FLOAT {IDENT | ":" | STRING | INT | FLOAT} ;
                // Value tokens are accumulated until a terminator

declaration   ::= ("#use" IDENT | "#import" IDENT) {terminator} ;
override      ::= "--OV" override_target {terminator} ;
override_target ::= IDENT IDENT                     -- alias override: old new
                  | "defaults" "(" override_args ")" override_vals ;  -- defaults override
override_args ::= IDENT {"," IDENT} ;               -- fg, bg, b
override_vals ::= "(" {val_pair} ")" ;
val_pair      ::= IDENT ":" expression ;             -- fg: red, bg: black, b: bright

function_def  ::= "--Function" IDENT "." IDENT "(" [param_list] ")" "{" {statement} "}" ;
param_list    ::= param {"," param} ;
param         ::= IDENT [":" type_name] ;

terminator    ::= ";" | NEWLINE ;
```

## Comments & Encoding (Step 1)

```ebnf
comment       ::= "//" {any_char_except_terminator} terminator
              | "/*" {any_char} "*/" ;
              // File encoding: UTF-8
```

## Types (Step 5 + Addition 4)

```ebnf
type_name     ::= "int" | "float" | "string" | "boolean" | "array" | "list" | "arb" | "map" ;

arb_tag       ::= INT ;   // Hex literal: 0x01, 0x02, 0x03, 0x04, 0x10, 0xFF
```

### arb Sub-Type Tag Map
| Tag Name | Hex Prefix |
|----------|-----------|
| str      | 0x01      |
| int      | 0x02      |
| float    | 0x03      |
| bool     | 0x04      |
| image    | 0x10      |
| raw      | 0xFF      |

### map Type (Addition 4)
- Key-value store with string keys and ArbValue values
- Construction: `map{ "key": value, "key2": value2 }`
- Access: `mapName.keyName` or `mapName["keyName"]`
- Assignment: `mapName.keyName = value`
- Built-ins: `keys(m)`, `values(m)`, `has(m, key)`

## Variables & Assignment (Step 6 + Addition 4)

```ebnf
var_decl      ::= ("let" | "const") IDENT [":" type_name] "=" expression ;
assignment    ::= IDENT "=" expression
              | map_assignment ;
map_assignment ::= IDENT "." IDENT "=" expression ;   -- mapName.key = value
swap          ::= IDENT "<>" IDENT ;
```

## Functions (Step 7)

```ebnf
call          ::= name "(" [arg_list] ")" ;
name          ::= IDENT {"." IDENT} ;   // supports dotted names: dir.list, snap.time
arg_list      ::= arg {"," arg} ;
arg           ::= expression | IDENT ":" kwarg_value ;
kwarg_value   ::= STRING | IDENT | INT | FLOAT | expression ;
              // Bare IDENT in kwarg position → string literal
```

## Expressions (Steps 5, 6, 7, 10 + Additions 5, 8, 10)

```ebnf
expression    ::= ternary ;

ternary       ::= or_expr ["?" ternary ":" ternary] ;

or_expr       ::= and_expr {("||" | "or") and_expr} ;       -- Addition 10: "or" keyword
and_expr      ::= not_expr {("&&" | "and") not_expr} ;      -- Addition 10: "and" keyword
not_expr      ::= "not" not_expr | comparison ;

comparison    ::= concat_expr {comp_op concat_expr} ;
comp_op       ::= "==" | "!=" | "<" | "<=" | ">" | ">=" ;
              // Addition 8: cross-type coercion for == and != (string "42" == int 42)
              // Addition 8: numeric coercion for <, <=, >, >= when both sides look numeric

concat_expr   ::= add_expr {".." add_expr} ;

add_expr      ::= mul_expr {("+" | "-") mul_expr} ;
              // + auto-coerces to string if either operand is string
mul_expr      ::= unary_expr {("*" | "/" | "%" | "^") unary_expr} ;
unary_expr    ::= ("-" | "+") unary_expr | postfix ;

postfix       ::= primary {index | member_access | call_args} ;
index         ::= "[" expression "]" ;
member_access ::= "." IDENT ["(" [arg_list] ")"] ;
call_args     ::= "(" [arg_list] ")" ;

primary       ::= INT | FLOAT | STRING | interp_string | "true" | "false"
              | IDENT
              | "(" expression ")"
              | list_literal
              | arb_literal
              | map_literal ;

// Interpolated string (Addition 1)
interp_string ::= '" {'${' expression '}' | literal_text} '" ' ;
              // "Hello ${name}!" — undefined variables produce empty string
              // \n escape produces newline (processed at lexer time)

list_literal  ::= "[" [expression {"," expression}] "]" ;

arb_literal   ::= "arb{" [arb_element {"," arb_element}] "}" ;
arb_element   ::= arb_tag "(" expression ")" ;

map_literal   ::= "map{" [map_pair {"," map_pair}] "}" ;   -- Addition 4
map_pair      ::= (STRING | IDENT) ":" expression ;
```

## Newline Escape (Addition 5)

```ebnf
// \n is the standard newline escape, processed at lexer time in string literals
// Runtime values (file paths, error messages) are not affected
```

## Text Brightness (Addition 5)

```ebnf
brightness    ::= "dim" | "normal" | "bright" ;
              // Used as kwarg b: in print/input
              // dim → ANSI code 2, normal → ANSI code 22, bright → ANSI code 1
              // Combined with fg color in ANSI escape sequence
```

## Statement Terminators (Step 1)

```ebnf
// ; is the primary terminator (C-family convention, matches inline C blocks)
// > is strictly a comparison operator (greater-than), NOT a terminator
// NEWLINE is a soft terminator (statement continues across lines)
```

## Shell Escapes (Step 4)

```ebnf
shell_block   ::= ("cmd" | "ps") "{" raw_text "}" ;
              // raw_text: everything between { and matching }, preserving whitespace
              // Variable interpolation: ${var} → variable value
```

## Inline C (Step 1)

```ebnf
c_block       ::= "c" "{" raw_c_code "}" ;
              // raw_c_code: C source code, compiled and executed
              // Variable interpolation: ${var} → variable value (as C literal)
```

## Control Flow (Step 10 + Additions 6, 9)

```ebnf
if_stmt       ::= "if" "(" expression ")" "{" {statement} "}"
                  {"elif" "(" expression ")" "{" {statement} "}"} 
                  ["else" "{" {statement} "}"] ;

for_stmt      ::= "for" "(" for_spec ")" "{" {statement} "}" ;
for_spec      ::= IDENT "in" expression
              | IDENT "=" expression "to" expression ["step" expression] ;

while_stmt    ::= "while" "(" expression ")" "{" {statement} "}" ;

repeat_stmt   ::= "repeat" "{" {statement} "}" "until" "(" expression ")" ;  -- Addition 6

switch_stmt   ::= "switch" "(" expression ")" "{" {case_clause} "}" ;        -- Addition 9
case_clause   ::= ("case" expression [":"] "{" {statement} "}") {case_clause}
              | "default" [":"] "{" {statement} "}" ;

try_stmt      ::= "try" "{" {statement} "}"                                  -- Addition 9
                  ["catch" "(" IDENT ")" "{" {statement} "}"]
                  ["finally" "{" {statement} "}"] ;
              // catch stores the error message in the named variable
              // finally always runs regardless of success/failure
              // try with finally (no catch) runs cleanup after any error

break_stmt    ::= "break" [IDENT] ;   // optional label (not evaluated in v1.0)

return_stmt   ::= "return" [expression] ;

exit_stmt     ::= ("exit" | "quit") [expression] ;  // expression = exit code

end_stmt     ::= "end" ;   // no-op (blocks are {} delimited)
```

## I/O with Color (Step 11 + Additions 5, 7)

```ebnf
print_stmt    ::= "print" "(" [arg_list] ")" ;
              // kwargs: fg: color, bg: color, b: brightness
              // color: named (red, cyan, ...) or hex (#RRGGBB)
              // brightness: dim, normal, bright (default: normal)
              // \n escape → newline (lexer-time)

input_expr    ::= "input" "(" [arg_list] ")" ;
              // kwargs: fg: color, bg: color, b: brightness
              // Returns: string (user input)
```

### Color Values
```ebnf
color_value   ::= color_name | hex_color | rgb_color | oklch_color ;
color_name    ::= "black" | "red" | "green" | "yellow" | "blue"
              | "magenta" | "cyan" | "white"
              | "bright_black" | "bright_red" | "bright_green"
              | "bright_yellow" | "bright_blue" | "bright_magenta"
              | "bright_cyan" | "bright_white" ;
hex_color     ::= "#" HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT HEX_DIGIT ;
rgb_color     ::= "rgb" "(" expression "," expression "," expression ")" ;
oklch_color   ::= "oklch" "(" expression "," expression "," expression ")" ;
```

### Default Color Override (Addition 7)
```ebnf
// --OV defaults(fg, bg, b) (fg: cyan, bg: black, b: bright)
// Sets default colors applied to all print/input calls without explicit fg/bg/b kwargs
// Per-script setting, applied before individual call kwargs
```

## File Operations (Steps 8, 9)

```ebnf
// Reading
read_file     ::= "readFile" "(" expression ")" ;
file_exists   ::= "fileExists" "(" expression ")" ;

// Addressing
addr_hex      ::= "addr" "." "hex" "(" expression ")" ;
addr_binary   ::= "addr" "." "binary" "(" expression ")" ;
addr_meta     ::= "addr" "." "meta" "(" expression ")" ;
txt_rc        ::= "txtRC" "(" expression "," expression ["," expression] ")" ;

// Image
encode_image  ::= "encodeImage" "(" expression ")" ;
decode_image  ::= "decodeImage" "(" expression ["," expression] ")" ;

// Media/Browser
open_media    ::= "openMedia" "(" expression ")" ;
open_browser  ::= "openBrowser" "(" expression ")" ;

// Writing
write_file    ::= "writeFile" "(" expression "," expression ["," "mode" ":" expression] ")" ;
build_file    ::= "buildFile" "(" expression "," expression ")" ;
              // mode: "overwrite" (default) | "error"

// Directory
dir_list      ::= "dir" "." "list" "(" expression ["," expression] ")" ;
dir_name      ::= "dir" "." "name" "(" expression "," expression ")" ;
dir_make      ::= "dir" "." "make" "(" expression ["," expression] ")" ;
dir_del       ::= "dir" "." "del" "(" expression ")" ;
```

### Path Resolution (Step 9)
```ebnf
path          ::= absolute_path | relative_path ;
absolute_path ::= "/" {path_segment} ;
relative_path ::= ("./" | "../" {"/.."} | ) {path_segment} ;
              // Resolved relative to the running script's directory
```

## OS Globals (Step 12)

```ebnf
// Time (presence-based: pass component names to get specific values)
snap_time     ::= "snap" "." "time" "(" [time_args] ")" ;
              // One-shot snapshot; returns raw values, not Key=val
              // snap.time() → full timestamp
              // snap.time("minute") → "37"
              // snap.time("hour", "minute") → "14 37"

count_time    ::= "count" "." "time" "(" [time_args] ")" ;
              // Live sampling; same presence-based model
              // Special kwargs: live: true, MS: <interval> for live clock mode

time_args     ::= time_component {"," time_component} ;
time_component ::= STRING | IDENT ;   // "year", "month", "day", "hour", "minute", "second", "millisecond", "ms"

wait_stmt     ::= "wait" "(" [expression {"," expression}] ")" ;
              // Args: minutes, seconds, milliseconds (positional)

// Color Scheme (supports Android night mode via adb)
cs_call       ::= "cs" "(" ")"           // returns: "light" | "dark"
              | "cs" "(" expression ")" ; // returns: boolean (true if matching scheme)

os_cs         ::= "os" "." "CS" "(" [expression] ")" ;  // alias for cs()

// Locale
locale_prf    ::= "locale" "." "prf" ;    // preferred locale (string)
locale_cur    ::= "locale" "." "cur" ;   // current locale (string)
locale_alt    ::= "locale" "." "alt" ;   // alternatives (string)
locale_check  ::= "locale" "." "check" "(" expression ")" ;  // boolean

// OS Globals (os.* prefix is canonical; bare names are aliases)
os_battery   ::= "os" "." "Battery" "(" ")" | "battery" "(" ")" ;
os_network   ::= "os" "." "Network" "(" ")" | "network" "(" ")" ;
os_screen    ::= "os" "." "Screen" "(" ")" | "screen" "(" ")" ;
os_name      ::= "os" "." "Name" "(" ")" | "os" "." "name" ;
os_version   ::= "os" "." "Version" "(" ")" | "os" "." "version" ;
              // All support Android via adb when device is connected
```

## New Builtins (Additions 2, 3, 4)

```ebnf
// Random (Addition 3)
random        ::= "random" "(" ")" ;          // returns float [0.0, 1.0)
rand_int      ::= "randInt" "(" expression "," expression ")" ;  // returns int in [min, max]
random_seed   ::= "random" "." "seed" "(" expression ")" ;       // seed the PRNG

// Key Bindings (Addition 2)
bind_key      ::= "bindKey" "(" expression "," expression ")" ;
              // args: key_combo, function_name
              // Works both inside repeat/until loops AND as standalone statement
              // Standalone: installs signal handlers (CTRL+C, CTRL+Z) or keyboard library hooks

// Open URL/App (Addition 2)
open_url      ::= "open" "." "url" "(" expression ")" ;     // opens URL in default browser
open_app      ::= "open" "." "app" "(" expression ["," "args" ":" expression] ["," "adr" ":" expression] ")" ;
              // launches OS application with optional arguments
              // adr: Android package name or full intent string (requires adb)

// CLI Args (Addition 3)
args_call     ::= "args" "(" ")" ;            // returns array of CLI args
args_index    ::= "args" "(" expression ")" ;  // returns specific arg by index

// Environment Variables (Addition 3)
env_call      ::= "env" "(" expression ")" ;   // returns env var value or empty string

// Map Operations (Addition 4)
keys_call     ::= "keys" "(" expression ")" ;   // returns list of map keys
values_call   ::= "values" "(" expression ")" ; // returns list of map values
has_call      ::= "has" "(" expression "," expression ")" ;  // boolean: key exists in map
```

## Module Imports (Addition 11)

```ebnf
import_decl   ::= "#import" IDENT {terminator} ;
              // Loads .arb file from same directory as script
              // Module functions become available as ModuleName.FunctionName()
              // Non-.arb imports (Python extensions) are silently skipped (use loadExt)
              // Circular imports are prevented via import tracking
```

## Extensions (Step 13)

```ebnf
load_ext      ::= "loadExt" "(" expression ["," expression] ")" ;
              // First arg: path; Second arg: language ("python" | "c" | "c++" | "cpp")

ext_call      ::= "ext" "." IDENT "(" [arg_list] ")" ;
              // Extension functions called via ext. namespace
```

### C/C++ ABI
```ebnf
c_entry       ::= "void" "arbplus_register" "(" "ArbEngine*" engine ")" ;
c_register    ::= engine "->" "register_func" "(" string "," function_pointer ")" ;
c_hook        ::= engine "->" "register_hook" "(" string "," function_pointer ")" ;
```

### Python ABI
```ebnf
py_entry      ::= "def" "register" "(" "engine" ")" ":" ... ;
py_register   ::= engine "." "register_extension" "(" string "," callable ")" ;
py_hook       ::= engine "." "register_hook" "(" string "," callable ")" ;
```

## Complete Program Grammar

```ebnf
program       ::= [metadata_block] {declaration} {override} {function_def} body ;
metadata_block ::= "#meta" "{" {meta_entry} "}" ;
meta_entry    ::= IDENT ":" meta_value {terminator} ;
declaration   ::= ("#use" IDENT | "#import" IDENT) {terminator} ;
override      ::= "--OV" override_target {terminator} ;
function_def  ::= "--Function" IDENT "." IDENT "(" [param_list] ")" "{" body "}" ;
body          ::= {statement} ;

statement     ::= var_decl | assignment | map_assignment | swap | if_stmt | for_stmt
              | while_stmt | repeat_stmt | switch_stmt | try_stmt
              | break_stmt | return_stmt | exit_stmt | end_stmt
              | print_stmt | shell_block | c_block
              | call | expression {terminator} ;

expression    ::= ternary ;
ternary       ::= or_expr ["?" ternary ":" ternary] ;
or_expr       ::= and_expr {("||" | "or") and_expr} ;
and_expr      ::= not_expr {("&&" | "and") not_expr} ;
not_expr      ::= "not" not_expr | comparison ;
comparison    ::= concat_expr {comp_op concat_expr} ;
comp_op       ::= "==" | "!=" | "<" | "<=" | ">" | ">=" ;
concat_expr   ::= add_expr {".." add_expr} ;
add_expr      ::= mul_expr {("+" | "-") mul_expr} ;
mul_expr      ::= unary_expr {("*" | "/" | "%" | "^") unary_expr} ;
unary_expr    ::= ("-" | "+") unary_expr | postfix ;
postfix       ::= primary {index | member_access | call_args} ;
primary       ::= INT | FLOAT | STRING | interp_string | "true" | "false"
              | IDENT | "(" expression ")" | list_literal | arb_literal | map_literal ;
```

---

## v2.0 Additions Summary

| # | Feature | Syntax |
|---|---------|--------|
| 1 | String interpolation | `"Hello ${name}!"` |
| 2 | open.url / open.app / bindKey | `open.url("https://...")`, `open.app("gimp")`, `bindKey("F1","help")` |
| 3 | Random / CLI args / env | `random()`, `randInt(1,100)`, `random.seed(42)`, `args()`, `env("HOME")` |
| 4 | Map type | `map{ "k": v }`, `m.key = v`, `keys(m)`, `values(m)`, `has(m,"k")` |
| 5 | \n newline escape, text brightness | `print("a\\nb")`, `print("x", b: bright)` |
| 6 | repeat...until | `repeat { ... } until (cond)` |
| 7 | --OV defaults | `--OV defaults(fg,bg,b) (fg: cyan, bg: black, b: bright)` |
| 8 | Cross-type comparison | `"42" == 42` → `true`, numeric coercion for `<`, `>` etc. |
| 9 | switch/case, try/catch/finally | `switch(x) { case "A": { } default: { } }`, `try { } catch(e) { } finally { }` |
| 10 | and/or keywords | `if (a and b or c) { }` |
| 11 | Module imports | `#import mymods;` — loads `.arb` file, functions via `modname.func()` |
| 12 | CLI arg passing | `python3 interpreter.py script.arb arg1 arg2` → `args()` returns `["arg1","arg2"]` |

## Part 4 Grammar Additions

### Inline Python Block
```
py_block       ::= "py{" [ "$!" IDENT | raw_text ] "}"
```
- When `$!IDENT` is used, the block loads code from the file at the path stored in `IDENT`
- Otherwise, raw Python code is written inline
- Standard-library imports only; third-party imports raise catchable `ArbPlusError`

### $! File Loading in Escape Blocks
```
escape_block   ::= ("c{" | "py{" | "cmd{" | "ps{") ( "$!" IDENT | raw_text ) "}"
```
- `$!IDENT` must be the sole content when used
- Path resolution uses `./` and `../` relative rules (same as Step 9)

### Shorthand Increment/Decrement
```
inc_dec_stmt   ::= IDENT "++" | IDENT "--"
```
- Standalone statement only (not an expression)
- `++` adds 1, `--` subtracts 1

### Forward Declaration
```
forward_decl   ::= "let" "[" IDENT "]" ";"
```
- Declares variable with `null` value
- Can be assigned later or never

### var() Builtin
```
var_call       ::= "var(" STRING ")"
```
- Returns the value of the variable named by the string argument
- Allows unquoted variable references where strings are expected

## Part 5 Grammar Additions

### --ErrOV flag (top-level)
```
top_level ::= ... | "--ErrOV" ("true" | "false") terminator
```

### Extended color values
```
color_value ::= named_color | hex_color | rgb_color | oklch_color
named_color ::= "black" | "red" | "green" | ... | "bright_white"
hex_color    ::= "#" hex_digit hex_digit hex_digit hex_digit hex_digit hex_digit
rgb_color    ::= "rgb(" int "," int "," int ")"
oklch_color  ::= "oklch(" float "," float "," float ")"
```

### file() type
```
file_call   ::= "file" "(" expression ")"
```
Returns an `ArbFile` value with resolved path. Compatible with `readFile()`, `fileExists()`, `addr.hex()`.

### meta.* access
```
meta_access ::= "meta" "(" [expression] ")"
```
- `meta(key)` → returns the metadata field value
- `meta()` → returns all metadata as a map (internal `_`-prefixed keys filtered)

### Set-7 Grammar Additions

#### Argument-aware --OV
```
override_decl ::= "--OV" ident "(" arg_list? ")" ident
                | "--OV" ident "<>" ident
                | "--OV" ident ident
arg_list      ::= expr ("," expr)*
```
- With `(...)`: fixed-argument override (args baked in at declaration time)
- With `<>`: complete swap of two functions
- Without `(...)` or `<>`: plain rename (original Step 7 behavior)

#### Cross-category override flags
```
ext_ov_flag   ::= "--ext.ov" "true" terminator
mod_ov_flag   ::= "--mod.ov" "true" terminator
chd_ov_flag   ::= "--chd.ov" "true" terminator
```
Must appear at top of file, before any `--OV` declaration. Each gates only its own category.

#### -w / -e print flags
```
flag_arg      ::= "-" "w" | "-" "e"
print_call    ::= "print" "(" expr ("," (flag_arg | kwarg))* ")"
```
- `-w`: use warning color (fg: yellow default)
- `-e`: use error color (fg: red default)
- Position-independent within the call arguments
- Explicit `fg:` kwarg overrides the flag's color

#### for (i < N) loop
```
for_loop_lt   ::= "for" "(" ident "<" expr ")" block
                | "for" "(" ident "<=" expr ")" block
```
- `< N`: iterates 0..N-1
- `<= N`: iterates 0..N inclusive
- Expr can be integer, variable, or function call

#### Typed variable declaration
```
typed_var_decl ::= "let" "[" type_name "]" ident "=" expr terminator
                 | "const" "[" type_name "]" ident "=" expr terminator
type_name      ::= "int" | "float" | "string" | "boolean" | "list" | "map" | "arb" | "null"
```
- If type is omitted: `let name = expr` — auto-detection from value
- With type: value is coerced to the specified type

#### open.app adr argument
```
open_app_call ::= "open.app" "(" expr ("," "adr:" expr)? ("," "args:" expr)? ")"
```
- `adr:` — Android adb command string
- `args:` — additional arguments passed to the app/adb command

#### openMedia Android resolution
No grammar change — `openMedia(path)` resolves from Termux home directory on Android automatically.

### Addition 48 — List, Math & String Builtins

#### New block calls (all standard function-call syntax)

```
// List operations
list_call    ::= "append" "(" expr ("," expr)+ ")"
              | "prepend" "(" expr ("," expr)+ ")"
              | "insert" "(" expr "," expr "," expr ")"
              | "removeAt" "(" expr "," expr ")"
              | "pop" "(" expr ")"
              | "shift" "(" expr ")"
              | "reverse" "(" expr ")"
              | "sort" "(" expr ")"
              | "indexOf" "(" expr "," expr ")"
              | "includes" "(" expr "," expr ")"
              | "slice" "(" expr ("," expr)* ")"
              | "flatten" "(" expr ")"
              | "range" "(" expr ("," expr ("," expr)?)? ")"
              | "foreach" "(" expr "," expr ")"

// Math operations
math_call    ::= "abs" "(" expr ")"
              | "round" "(" expr ("," "decimals" ":" expr)? ")"
              | "floor" "(" expr ")"
              | "ceil" "(" expr ")"
              | "min" "(" expr ("," expr)* ")"
              | "max" "(" expr ("," expr)* ")"
              | "sum" "(" expr ")"
              | "clamp" "(" expr "," expr "," expr ")"

// String operations
string_call  ::= "replicate" "(" expr "," expr ")"
              | "startsWith" "(" expr "," expr ")"
              | "endsWith" "(" expr "," expr ")"
              | "capitalize" "(" expr ")"
              | "titleCase" "(" expr ")"
              | "padLeft" "(" expr "," expr ("," expr)? ")"
              | "padRight" "(" expr "," expr ("," expr)? ")"
              | "replaceAt" "(" expr "," expr "," expr ")"
              | "format" "(" expr ("," expr)* ")"
              | "charCodeAt" "(" expr "," expr ")"
              | "fromChar" "(" expr ")"
```

#### Notes

- `min()` and `max()` accept either variadic arguments (`min(5, 3, 8)`) or a single list (`min([5, 3, 8])`).
- `range()` mirrors Python's `range()`: `range(n)` → `[0..n-1]`, `range(start, end, step)` → `[start, start+step, ..., <end]`.
- `slice()` works on both lists and strings: `slice("hello", 0, 3)` → `"hel"`.
- `indexOf()` works on both lists and strings: `indexOf("hello", "ll")` → `2`.
- `includes()` works on both lists and strings: `includes([1,2,3], 2)` → `true`.
- `foreach()` calls a named user-defined function (string argument) for each `(item, index)` pair.
- `replicate` is used instead of `repeat` because `repeat` is a keyword for post-test loops.
- `split()` with empty separator now splits into individual characters.
