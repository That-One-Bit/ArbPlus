# ArbPlus Prompt Addendum - Part 1 of 4

This is **Part 1 of 4** of a set of additions on top of the ArbPlus design prompt you already gave the LLM - send this as a follow-up message rather than re-sending the whole original. Send Parts 2, 3, and 4 in separate follow-up messages right after this one, in order; they continue the same numbered addition list (Addition 13 onward) and depend on context established here.

---

## Addition 1 - String Interpolation

Add this alongside the existing string-concatenation work:

**String interpolation** - a template syntax for embedding a variable's value directly inside a string literal, e.g. `"${query}"` or an ArbPlus-flavored equivalent, so other features (like the new opening-links-and-apps feature below) can reuse the same mechanism rather than each inventing its own. Define the exact delimiter syntax, what happens when the referenced variable doesn't exist, and whether nested/expression interpolation (e.g. `${a + b}`) is supported or only bare variable names.

## Addition 2 - Key Bindings, Text Brightness, Default Colors & Opening Links/Apps

Add this as a new step/feature area:

- **Key-to-function mapping** - a way to bind a keypress (or key combination) to an ArbPlus function so the script reacts to input outside of a blocking `input()` call, e.g. `bindKey(KeyName, FunctionName)`. Define which key names/combinations are supported, whether binding is global (whole program) or scoped to a running block, what happens if the same key is bound twice, and how a binding is removed.
- **Text brightness** - a separate axis from the existing fg/bg color system: an intensity/brightness modifier for printed text (e.g. dim, normal, bright/bold), settable independently of which color is chosen, e.g. `print("text", fg: red, b: bright)`. Define the brightness levels supported and how it interacts with a terminal that doesn't support intensity levels.
- **Default color/brightness override via `--OV`** - rather than a separate `setDefaults()` function, reuse the existing `--OV` override mechanism to redefine the script's defaults in one call:
  `(--OV defaults(fg, bg, b, other defaults) [newfg, newbg, newb, new-other things])`
  Here `fg`, `bg`, `b`, and any other default-able settings are the base names being overridden, and the bracketed list gives their new values in the same order - e.g. `(--OV defaults(fg, bg, b) [red, black, bright])` would make every subsequent `print`/`input` call that doesn't specify its own colors/brightness fall back to red-on-black, bright, instead of the standard white-on-black/normal. Define: whether this can be called more than once in a file (last one wins, or is it metadata-only and must appear once near the top), whether a partial list (e.g. only overriding `fg`) is allowed and leaves the rest at their prior defaults, and how this interacts with the general `--OV` collision/scoping rules already defined for functions.
- **Opening links and apps** - a built-in to open a URL or launch an OS application directly (distinct from the existing "read a file via the system default browser" mode, which is about viewing a *file*), e.g. `open.url(url)` and `open.app(pathOrName, args)`. Define how each shells out per platform (Windows/macOS/Linux each differ), what happens if the target app/URL handler doesn't exist, and whether `open.app` can pass arguments to the launched application. Cover two specific data-argument cases explicitly:
  - **Opening a file in a specific application, not just the OS default** - e.g. `open.app("gimp", args: "photo.png")` to open an image in a named image editor rather than whatever the OS has registered as default. Define how `args` distinguishes "the file/data to open" from other flags the target app might accept, and what happens if the named app isn't installed.
  - **Building a URL with a variable substituted in before opening it** - e.g. `open.url("https://example.com/search?q=${query}")` where `${query}` is filled in from an ArbPlus variable at call time before the link is opened. Define the interpolation syntax (reusing the string-interpolation rules from Addition 1 above rather than inventing a second one), whether the substituted value is URL-encoded automatically, and what happens if the referenced variable doesn't exist.

## Addition 3 - Newline Support in Text Output

Add `/n` as the newline token, recognized inside any string that ends up as displayed/entered text - not just `print`, but every other place text is output or echoed (colored `print`, the colored `input()` prompt string, and any other built-in that writes text to the screen). Define:

- Where `/n` is interpreted (only inside string literals passed to output functions, or anywhere a string is built, including via concatenation/interpolation from Addition 1)
- Whether `/n` needs escaping to be shown literally (e.g. if a script actually wants to print the two characters `/n` rather than a line break)
- How this interacts with the existing comment/line-ending symbols so `/n` inside a string isn't confused with a statement terminator or comment marker

## Addition 4 - `repeat...until` Loop

Add a `repeat...until` loop alongside the existing loop constructs, taking the same/similar condition arguments as an `if` statement (reusing the condition-expression grammar rather than defining a new one):

`repeat { ... } until (condition)`

Define:

- That the body runs at least once before the condition is ever checked (the defining trait of a repeat-until vs. a `while`), and confirm this is the intended semantics
- How it interacts with `break` and `not` from the existing conditionals/control-flow work - both should work the same way inside a `repeat...until` body as inside any other loop
- Whether an `elif`-style multi-condition form makes sense here, or whether `until` only ever takes a single condition expression

## Addition 5 - Worked Examples & Reference Updates (continued)

- Extend the worked example from Addition 2's list to include a `/n` newline inside a printed and an input-prompt string
- Add a separate worked example for `repeat...until`, including a `break` inside it
- The quick-reference table and formal grammar should also cover: the `/n` newline token, and `repeat...until`

## Addition 6 - Error Handling

Add a formal `try`/`catch`/`finally` construct, since earlier steps (file reads, directory operations, extension calls) already assume errors are "catchable" without ever defining what catches them:

```
try { ... } catch (err) { ... } finally { ... }
```

Define: what an `err` value looks like (a message string, a typed error object with a code/category, or both), whether `finally` is required or optional, whether uncaught errors propagate up to the script's own `exit`/`quit` behavior from the conditionals/control-flow work, and how this reconciles with any built-in that was previously described as "returns a boolean/status code instead of raising" - pick one consistent convention and apply it everywhere.

## Addition 7 - Map/Dictionary Type

Add a key-value collection type alongside `array`/`list`/`arb` - e.g. `map`. Define: literal syntax (e.g. `map{ "key": value, ... }`), lookup/assignment syntax, what happens on a missing-key lookup (error, or a null-like value), key type restrictions (strings only, or any hashable type), and iteration order guarantees (insertion order, or unordered).

## Addition 8 - Comparison & Logical Operators

Pin down the operators that `if`/`elif`/`while`/`repeat...until` conditions and the inline-if all rely on, since none of these have been explicitly specified yet: equality (`==`/`!=`), ordering (`<`, `>`, `<=`, `>=`), and logical AND/OR (`&&`/`and`, `||`/`or`). Define precedence relative to each other and to `not`, and whether comparison across mismatched types (e.g. `int` vs `string`) is an error or does an implicit coercion.

## Addition 9 - `switch`/`case`

Add a multi-branch construct for when there are more than two or three `elif` branches:

```
switch (value) {
  case A: { ... }
  case B: { ... }
  default: { ... }
}
```

Define whether cases fall through to the next one by default (like C) or stop after a match (like most modern languages), and whether `break` (from the loop work) is reused here or unnecessary.

## Addition 10 - Random Numbers

Add built-ins for randomness alongside the existing math functions - e.g. `random()` for a float in [0,1) and `randInt(min, max)` for an integer in a range. Define inclusivity of the range bounds and whether a script can seed the generator for reproducible output.

## Addition 11 - Module/Import System Between `.arb` Files

The metadata block already lets a file *declare* other `.arb` files as dependencies - define how a script actually pulls a function defined in one `.arb` file into another. Cover: the import statement syntax, namespacing (does an imported function need a prefix, or does it just become callable directly?), what happens on a name collision between an imported function and a local one or another import, and whether circular imports between two `.arb` files are detected and rejected.

## Addition 12 - Command-Line Arguments & Environment Variables

Add built-ins for a script to read what it was invoked with and the OS environment around it - e.g. `args()` or `args[n]` for command-line arguments passed to the script, and `env(name)` to read an environment variable. Define behavior when an argument index is out of range or an environment variable doesn't exist (ties into the error-handling convention from Addition 6).
