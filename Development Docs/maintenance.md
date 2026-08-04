# ArbPlus Interpreter Maintenance Guide

This manual maintenance guide describes the internal architecture of the ArbPlus interpreter and serves as a step-by-step developer guide for adding features, types, built-ins, system globals, and extension hooks, and for running regression tests.

## Interpreter Source Layout Overview
The ArbPlus interpreter is a self-contained, single-file interpreter located at `arbplus/interpreter.py`. The file is organized into 8 logically distinct sections.

### Section-by-Section Breakdown

1. **SECTION 1: TYPE SYSTEM** (Approx. lines ~30-170; Actual lines 30-194)
   - Contains the `ArbValue` base class and its primary subclass typed values: `ArbInt`, `ArbFloat`, `ArbString`, `ArbBool`, `ArbArray`, `ArbList`, and the tagged hex-encoded container `ArbArb`.
   - Key utility functions:
     - `to_arb_value(val)`: Coerces raw Python objects into appropriate `ArbValue` subclasses.
     - `arb_truthy(val)`: Evaluates custom truthiness logic for all `ArbValue` types.
     - `arb_to_string(val)`: Handles standard string representation (e.g., custom format for `arb{ ... }`).
     - `arb_coerce(val, target_type)`: Performs runtime coercion to target types.

2. **SECTION 2: ERROR TYPES** (Approx. lines ~170-195; Actual lines 195-212)
   - Contains interpreter exception classes:
     - `ArbPlusError`: Base exception for parse errors, runtime errors, and type check failures.
     - `BreakException`: Raised to break out of `for` and `while` loops.
     - `ReturnException`: Carries return values up the call stack.
     - `ExitException`: Terminates execution with an integer exit code.

3. **SECTION 3: LEXER** (Approx. lines ~195-430; Actual lines 213-566)
   - Handles tokenization of raw ArbPlus code.
   - Key components:
     - `TokenType` enum: Identifies valid tokens (e.g., `INT`, `FLOAT`, `STRING`, `IDENT`, operators, delimiters, and `DOT`).
     - `KEYWORDS` set: Defines standard keywords (e.g., `func`, `if`, `else`, `const`, `return`, `break`, `override`, `import`).
     - `Token` dataclass: Holds token type, value, and line/column numbers.
     - `Lexer` class: Performs lexing. Key methods include `tokenize()`, `peek()`, `advance()`, `read_string()`, `read_number()`, `read_identifier()`, and `read_raw_block()`.

4. **SECTION 4: AST NODES** (Approx. lines ~430-560; Actual lines 567-706)
   - Defines all AST node data structures as `@dataclass` classes.
   - Includes node types: `ProgramNode`, `MetaNode`, `DeclNode`, `OverrideNode`, `FuncDefNode`, `AssignNode`, `IfNode`, `ForNode`, `WhileNode`, `CallNode`, `IndexNode`, `MemberNode`, `BinOpNode`, `TernaryNode`, `ArbLitNode`, `ListNode`, `VarNode`, `LiteralNode`, etc.

5. **SECTION 5: PARSER** (Approx. lines ~560-900; Actual lines 707-1243)
   - Contains the `Parser` class, implementing a recursive descent parser.
   - Key entry points and sub-parsers:
     - `parse()`: Parses metadata, declarations, overrides, and function definitions, followed by the program body.
     - `parse_metadata()`: Parses block comments containing metadata.
     - `parse_function_def()`: Parses custom user function declarations.
     - `parse_block_until()`: Groups statements into blocks.
     - `parse_statement()`: Decides how to parse different statements (assignments, control flow, loops, etc.).
     - `parse_expr()`: Parses mathematical expressions and function calls using operator precedence climbing.

6. **SECTION 6: ENVIRONMENT** (Approx. lines ~900-950; Actual lines 1244-1292)
   - Contains the `Environment` class, which manages variable scope, symbols, constants, and nested lexical scopes (using `parent` references).
   - Core API: `get(name)`, `set(name, value, is_const)`, `declare(name, value, is_const, type_hint)`, and `has(name)`.

7. **SECTION 7: INTERPRETER / EVALUATOR** (Approx. lines ~950-2135; Actual lines 1293-2135)
   - Contains the `Interpreter` class, which traverses the AST and executes/evaluates nodes.
   - Core runtime loop and routing:
     - `run(program)`: Entry point that registers overrides/functions, sets up metadata, and executes statements.
     - `execute(node, env)`: Executes statements that don't produce a value (e.g., `AssignNode`, `IfNode`, `ForNode`).
     - `eval(node, env)`: Evaluates expressions to return `ArbValue` objects (e.g., binops, literals, ternary, member access).
     - `eval_binop()`, `eval_call()`: Handles operations and calls.
     - `call_builtin(name, args, kwargs, env)`: Invokes registered core built-in functions, applying any active extension hooks first.
     - Built-in functions: Handled via `_b_*` methods (e.g., `_b_add`, `_b_print`, `_b_readfile`, `_b_load_ext`).

8. **SECTION 8: ENTRY POINT** (Actual lines 2136-end)
   - Executes when running `arbplus/interpreter.py` directly from the CLI. Parses CLI arguments, reads the specified script, tokenizes, parses, runs it, and prints errors with traceback details where appropriate.

---

## Where to Add Things in the Source Tree

### New Built-in Function
1. **Declare**: Add an entry to the `_setup_builtins` dict (in the `Interpreter` class), mapping the function name to a method like `self._b_functionname` (e.g., `"newFunc": self._b_newfunc`).
2. **Implement**: Write the method `def _b_functionname(self, args, kwargs, env):` that takes evaluated arguments (list of `ArbValue`), keyword arguments (dict of `ArbValue`), and the environment, and returns an `ArbValue`.
3. **Register**: It's automatically registered once it's in the `_setup_builtins` dict.
4. **Document**: Add it to `docs/usage.md` quick-reference table.

### New Type
1. Add a new class in **SECTION 1**, extending `ArbValue` (e.g., `class ArbMyNewType(ArbValue):`).
2. Update `to_arb_value()` to handle the new type and wrap standard Python values correctly.
3. Update `arb_to_string()` to define how the type is serialized or printed.
4. Update `arb_truthy()` to specify custom truthiness rules for this type.
5. Add literal syntax in the lexer (if needed, in `TokenType` / `Lexer`) and parser (if needed, e.g., in `parse_expr()`).

### New OS Global
1. Add the built-in function in `_setup_builtins`.
2. If it uses dot-notation (like `locale.prf` or `os.name`), add handling in `eval_locale_member()` or `eval_os_member()`, or add a new `eval_*_member()` method inside SECTION 7.
3. Follow the **two-shapes pattern**: no-arg returns the value, with-arg returns a boolean check (for instance, `locale.prf()` or `locale.cur()` returns the locale string, while `locale.check("en")` returns a boolean indicating a match).

### New Extension Hook Point
1. The hook mechanism is located in `call_builtin()` — hooks are stored in `self.ext_hooks`.
2. To add a new hookable function, just add it to `self.builtins` (it is automatically hookable because `call_builtin()` intercepts calls to any function in `self.builtins`).
3. Extensions register hooks dynamically using the engine's public hook registry method: `engine.register_hook(builtin_name, hook_func)`.

---

## Minimal Checklist to Add a New Built-in Function by Hand

- [ ] Add to `_setup_builtins` dict: `"funcName": self._b_funcname`
- [ ] Write the method: `def _b_funcname(self, args, kwargs, env):` returning `ArbValue`
- [ ] Handle argument validation (e.g., checking `len(args)` and parameter types)
- [ ] Return the appropriate `ArbValue` type (e.g., `ArbInt`, `ArbString`, `ArbBool`)
- [ ] Add to `usage.md` documentation
- [ ] Test: write a `.arb` script that calls it and run: `python3 interpreter.py test.arb`

---

## Adding Support for a New Extension Language

At a high level:
1. Add a new branch in `_b_load_ext` for the new language.
2. For interpreted languages (such as JavaScript/Node or Python dynamic environments): use subprocess or a bridge to load and call the extension.
3. For compiled languages (such as Rust or Go): compile to a shared library, load via `ctypes` (or corresponding binding library), and call the register function.
4. Document the registration entry point convention for the new language (e.g., defining what symbol the extension must export).
5. **The key contract**: the extension must register functions with the engine via `register_extension(name, func)` and optionally register hooks via `register_hook(builtin_name, hook_func)`.

---

## Testing Changes Against Existing Examples

The example scripts in `arbplus/examples/` cover all major features:
- **01_hello.arb**: metadata, print, colored output
- **02_midcomplex.arb**: variables, functions, override, inline-if, shell-escape
- **03_stringswap.arb**: concatenation, swap (same and different types)
- **04_controlflow.arb**: loops, break, not, ternary, if/elif/else
- **05_files.arb**: readFile, fileExists, txtRC, addr.hex/binary, writeFile, buildFile
- **06_directories.arb**: dir.make, dir.list (both filters), dir.name, dir.del
- **07_globals.arb**: snap.time, count.time, cs (both forms), locale.*, battery, network, os.*
- **08_full.arb**: arb, functions, recursion, control flow, shell, OS globals, files

To test: run all examples after any change:
```bash
cd arbplus && for f in examples/*.arb; do echo "=== $f ==="; python3 interpreter.py "$f" 2>&1; done
```

If any example breaks, investigate before proceeding. Each example exercises specific features, so a failure pinpoints what was affected.
