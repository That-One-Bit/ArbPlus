# ArbPlus Interpreter Implementation Notes

This document provides a comprehensive overview of the design, architecture, and internal implementation details of the ArbPlus interpreter. It is intended for developers maintaining the interpreter, authoring extensions, or debugging language behavior.

---

## Interpreter Architecture

The ArbPlus interpreter is built as a single-file, lightweight Python tree-walking interpreter that operates in three distinct stages: **Lexer**, **Parser**, and **Interpreter** (Evaluator).

### Direct AST Interpretation (No JIT, No Bytecode)
Unlike interpreters that compile source code to an intermediate bytecode representation or use a Just-In-Time (JIT) compiler, ArbPlus uses direct AST (Abstract Syntax Tree) interpretation. This design prioritizes code simplicity, ease of debugging, and fast startup times, which are well-suited for scripting and orchestration workloads.

### Execution pipeline:
1. **Lexer (Tokenization)**: Scans the source file character-by-character to produce a list of `Token` objects. Each `Token` represents a syntactic unit (e.g., identifiers, operators, keywords, literals, and specialized shell block boundaries).
2. **Parser (Syntactic Analysis)**: Uses a top-down recursive descent approach to build an AST. The parser converts the linear token stream into a hierarchical structure made of Python `dataclass` nodes (e.g., `ProgramNode`, `FuncDefNode`, `IfNode`, `AssignNode`, `CBlockNode`, `ShellBlockNode`).
3. **Evaluator (Execution)**: Walks the resulting AST. It maintains execution state, evaluates expressions recursively, manages environment scopes, and executes built-in or user-defined statements.

```
Source Code ──> [Lexer] ──> Token Stream ──> [Parser] ──> AST Nodes ──> [Evaluator] ──> Output
```

### Environment Scoping
The `Environment` class manages variable storage and scoping rules. It features:
- **Parent Chain Delegation**: Each execution context (like a function invocation or block) creates a new child `Environment` that contains a reference to its `parent` environment.
- **Variable Resolution**: When querying a variable via `get(name)` or checking existence via `has(name)`, the environment searches its local scope first. If not found, it recursively traverses the parent chain until it reaches the global environment. If the variable is undefined, it raises an `ArbPlusError`.
- **Declaration and Assignment**:
  - `declare(name, value, is_const, type_hint)`: Explicitly defines a new variable in the local scope, optionally applying type hints and constant constraints.
  - `set_existing(name, value)`: Updates an already declared variable. It searches up the parent chain to modify the variable where it was first defined, ensuring that block-level updates to global or outer-scope variables propagate correctly instead of creating shadowed local duplicates.
  - Constant constraints (`self.consts`) prevent reassignment, throwing an `ArbPlusError` if re-declaration or set-existing operations attempt to overwrite a constant.

---

## Shell Call Sandboxing

ArbPlus supports native command and PowerShell block execution using `cmd{}` and `ps{}` constructs.

### Lexing and Parsing Shell Blocks
Shell blocks are treated as raw text by the lexer to preserve original spacing, backslashes, quotes, and newlines. The lexer recognizes `cmd` and `ps` keyword prefixes followed by `{` and scans until the balancing `}` is reached, retaining everything inside as a literal string block inside a `ShellBlockNode`.

### Variable Interpolation
Before a shell command is handed over to the host operating system, ArbPlus parses the command string for `${var}` patterns.
- It extracts the variable name.
- It checks the active `Environment` (and its parent chain) for the variable.
- If the variable exists, the `${var}` placeholder is replaced by its string representation.
- If the variable is undefined, the literal expression `${var}` remains untouched.

### Platform-Specific Command Execution
The interpreter adapts shell calls dynamically depending on the host OS:
- **Windows**:
  - `cmd{ ... }` executes via `cmd.exe /c "<interpolated_code>"`.
  - `ps{ ... }` executes via `powershell -Command "<interpolated_code>"` if `powershell` is available on the path; otherwise, it falls back to `pwsh -Command ...`.
- **Linux / macOS**:
  - `cmd{ ... }` falls back to `sh -c "<interpolated_code>"`.
  - `ps{ ... }` checks for the presence of `powershell` or `pwsh` on the system's `PATH` via `shutil.which`. If available, it executes via `pwsh -Command "<interpolated_code>"`; otherwise, it falls back to `sh -c "<interpolated_code>"`.

### Subprocess Output Capture
Shell output (stdout) is captured entirely using Python's `subprocess.run(..., capture_output=True, text=True)`. The stdout is stripped of leading and trailing whitespace and returned as an `ArbString`.

### Sandboxing Limitations (Trusted Environment Model)
ArbPlus implements **no sandboxing beyond basic subprocess isolation**. Any scripts or shell commands executed via `cmd{}` or `ps{}` run with the full privileges of the user running the ArbPlus interpreter. Because of this, ArbPlus assumes that scripts being run are from a trusted source, which is a documented language limitation.

---

## Extension Dynamic Loading

ArbPlus provides an extensible architecture allowing developers to write high-performance or platform-specific extensions in Python or native C/C++.

### Python Extensions
Python extensions are loaded dynamically from source files at runtime:
1. The dynamic loader resolves the file path and calls `importlib.util.spec_from_file_location("arbplus_ext", path)`.
2. It generates a Python module via `module_from_spec` and executes it within the interpreter process using `spec.loader.exec_module(mod)`.
3. The loaded module is expected to export a `register(engine)` function, where `engine` represents the active `Interpreter` instance. This function registers new functions or hooks.

### C/C++ Extensions
C/C++ extension sources are compiled on-the-fly and loaded dynamically:
1. The interpreter searches for a C compiler (`gcc`, `cc`, or `clang`) on the system `PATH`.
2. The source code is compiled into a shared library (`.so`) using the compilation flags `-shared -fPIC`.
3. The compiled library is dynamically loaded using Python's `ctypes.CDLL`.
4. The loaded library is expected to expose an `arbplus_register()` initialization routine which interacts with the interpreter interface.

### Registration Interfaces
Extensions can expand language features in two ways through the `Interpreter` object:
1. **New Functions**: Added via `engine.register_extension(name, func)`. The registered Python function `func` becomes callable within ArbPlus code as `name(...)`.
2. **Built-in Hooks**: Added via `engine.register_hook(builtin_name, hook_func)`. This allows overriding or enhancing core built-in functions.

### Hook Mechanism
Hooks allow interception of core built-in actions:
- Every time a built-in function is evaluated, the interpreter first checks if there are registered hooks in `self.ext_hooks` for that built-in.
- Registered hook functions are executed in order, receiving the arguments and keyword arguments.
- **Short-circuiting**: If a hook returns a value that is **not** `None` (e.g., an `ArbValue`), execution short-circuits, and that value is immediately returned as the function's result.
- **Fall-through**: If a hook returns `None`, the interpreter falls through to the next hook or executes the original built-in function.

### Parameter Passing
All registered extension and hook functions receive parameters as standard Python native lists of positional arguments (`args`) and dicts of keyword arguments (`kwargs`), where all parameters are wrapped inside `ArbValue` subclasses.

---

## count.time Live Sampling

The `count.time()` built-in is designed for periodic metric extraction and performance testing.

### Synchronous Clock Resampling
To avoid the architectural complexity and thread-safety issues associated with background execution threads inside a single-threaded tree-walking evaluator, `count.time()` operates on a **purely synchronous model**:
- Every call to `count.time()` directly re-queries the system clock on demand using `datetime.datetime.now()`.
- The returned value represents the exact system state at the moment of evaluation.

### Simulated Periodic Sampling (kwargs Interval)
To support testing and script simulation of periodic time capture, `count.time()` supports an optional `interval` keyword argument (`interval: ms`):
- When `interval` is provided, the interpreter forces the thread to sleep for that specified duration (using Python's `time.sleep`) prior to returning.
- This synchronous delay simulates a background sampling rate without spawning background worker threads.

### Simplified Design and Threading Trade-offs
A fully asynchronous implementation would run a background daemon thread that updates a shared mutable value. However:
- A synchronous model keeps the evaluator simple and deterministic.
- It prevents potential race conditions, lock overheads, and context switching.
- **Performance Precision Limitation**: Because of Python runtime interpretation overhead and thread scheduling, tight timing loops (especially sub-millisecond ranges) cannot guarantee true hardware-level real-time accuracy. However, for scripting and orchestration workloads (e.g., seconds-level countdowns, timeout tracking, file modification timing), this overhead is negligible and the precision is highly adequate.

---

## Type System Internals

ArbPlus implements a robust, tagged dynamic type system. All runtime values are represented by subclasses of the base class `ArbValue`.

```
                  ArbValue (.val, .type_name)
    ┌───────────┬───────┴───┬─────────────┬───────────┐
 ArbInt     ArbFloat     ArbString     ArbBool     ArbArray
                            │                         │
                         ArbList                   ArbArb
```

### The `ArbValue` Base Class
Each value has two core attributes:
- `.val`: The underlying Python representation of the value.
- `.type_name`: A string tag representing the ArbPlus type (e.g., `"int"`, `"float"`, `"string"`, `"boolean"`, `"array"`, `"list"`, `"arb"`).

### Subclasses
- **`ArbInt`**: Wrapper for Python `int`.
- **`ArbFloat`**: Wrapper for Python `float`.
- **`ArbString`**: Wrapper for Python `str`.
- **`ArbBool`**: Wrapper for Python `bool`.
- **`ArbArray`**: A homogenous or heterogeneous indexed sequence of `ArbValue`s.
- **`ArbList`**: Similar to array, used for flexible sequential structures.
- **`ArbArb`**: A specialized, tagged container representing raw hex-encoded bytes of structured data.

### ArbArb Struct Representation
The `ArbArb` subclass acts as a typed serialization container. Elements inside are stored as a list of 4-tuples:
`(_tag_name, _tag_byte, _hex_bytes, _decoded_value)`
- **`tag_name`**: String tag mapping (e.g., `"str"`, `"int"`, `"float"`, `"bool"`, `"image"`, `"raw"`).
- **`tag_byte`**: A single-byte integer marker representing the type (resolved via a predefined map `ARB_TAG_MAP`).
- **`hex_bytes`**: A hex-encoded string of the binary representation:
  - Integers and floats use big-endian binary packing via Python's standard `struct.pack` (`'>q'` for 64-bit int, `'>d'` for 64-bit double).
  - Strings are UTF-8 encoded and then converted to hex (`value.encode('utf-8').hex()`).
  - Booleans use a single byte (`0x01` for true, `0x00` for false).
- **`decoded_value`**: The native Python object decoded from the hex representation, cached for rapid indexed access.

### Type Coercion (`arb_coerce`)
Implicit and explicit conversions are handled via `arb_coerce(val, target_type)`.
- It is extensively used during variable declarations with type hints (e.g., `let x: int = 5.2`) and parameter parsing.
- Coerces values dynamically based on target type tags (`"int"`, `"float"`, `"string"`, `"boolean"`).

### Truthiness Rules
Truthiness of any `ArbValue` is evaluated using `arb_truthy`:
- **`ArbInt`**: Truthy if value $\neq 0$.
- **`ArbFloat`**: Truthy if value $\neq 0.0$.
- **`ArbString`**: Truthy if non-empty (`len(value) > 0`).
- **`ArbArray` / `ArbList` / `ArbArb`**: Truthy if they contain at least one element.
- **`ArbBool`**: Evaluated directly based on its inner boolean value.

### String Serialization
When printing or formatting:
- Booleans print as lowercase `'true'` or `'false'`.
- Collections (arrays/lists) print as comma-separated values wrapped in brackets `[...]`.

---

## Error Handling

ArbPlus handles runtime and control-flow situations through standard Python exceptions.

### Language-Level Errors (`ArbPlusError`)
The `ArbPlusError` exception is thrown during syntactic, typing, or operational failures (e.g., division by zero, invalid type coercions, file I/O failures, missing variables, compilation errors in dynamic C blocks).
- These errors are user-facing, carry diagnostic messages, print to `stderr` and cause the interpreter to terminate execution with an exit status of `1`.

### Control Flow Exceptions
ArbPlus uses Python's exception mechanism to propagate control signals up the AST tree-walking call stack. Since tree walking uses recursive function evaluation, standard function returns or loops cannot easily break execution across nested function calls without checks at every step. Exceptions provide a clean and fast channel for this:
- **`BreakException`**: Raised when a `break` statement is encountered. It is caught by the closest enclosing `while` or `for` loop handler in the evaluator, immediately terminating the loop.
- **`ReturnException`**: Raised when a `return expr` statement is evaluated. It carries the returned `ArbValue` inside the exception object. The interpreter's function-calling mechanism catches this exception, unwinds the call stack, and extracts the carried value as the function's output.
- **`ExitException`**: Raised when an `exit code` statement is evaluated. It carries the specified integer exit code and signals immediate program termination. The top-level `run()` loop catches this exception and returns the exit code to the operating system shell.

---

## Performance Trade-offs

When designing and executing scripts in ArbPlus, developers must keep several performance trade-offs in mind.

### Tree-Walking Interpreter Overhead
As a Python-based tree-walking interpreter, ArbPlus incurs a significant speed penalty compared to native compiled code or optimized JIT runtimes (such as PyPy, V8, or LuaJIT).
- Running nested loop blocks, complex math computations, or tight timing checks (`count.time`) in pure ArbPlus can be **~100x slower** than compiled C or native Python code due to the overhead of AST node traversal, dynamic typing checks, and scope lookups.

### Scripting vs. Compute Workloads
- **I/O-Bound Orchestration**: For tasks such as system automation, orchestrating shell subprocesses (`cmd{}` or `ps{}`), manipulating file structures, and handling configuration files, the interpreter overhead is completely negligible. This is because execution time is dominated by operating system I/O, file system calls, or external processes.
- **Performance-Critical Code**: If high-throughput math, raw data compression, or real-time sampling is required, pure ArbPlus loops should be avoided.
- **Solving the Performance Gap**:
  - Developers can write critical loops as **C blocks** (`c{ }`). C blocks compile directly to native binaries on-the-fly and execute at raw machine speeds.
  - Performance critical components can be factored out into precompiled C shared libraries (`.so`) and loaded as high-speed native extensions via `load_ext()`.

---

## Packaging

ArbPlus requires zero setup, making it ideal for portable deployments across multiple platforms.

### No External Dependencies
The ArbPlus interpreter is written entirely using the Python standard library. It requires **Python 3.8 or higher** and has zero third-party dependencies (no pip installation required).

### Executable Bundling via PyInstaller
To distribute ArbPlus as a standalone utility without requiring users to install Python on the host machine, the interpreter can be compiled into a single executable using PyInstaller:

```bash
pyinstaller --onefile arbplus/interpreter.py
```

This commands packs the Python interpreter, runtime, standard libraries, and `interpreter.py` script into a single executable binary (`interpreter` or `interpreter.exe` depending on the platform).

### Runtime Extension Requirements
- **Python Extensions**: Require a Python interpreter to be available (either globally installed on the system or bundled inside the executable).
- **C/C++ Extensions and C Blocks**: Rely on a local compiler (`gcc`, `cc`, or `clang`) on the target machine's `PATH` at runtime to compile the dynamic code blocks. If no compiler is found, attempting to compile C blocks or C/C++ extensions will raise an `ArbPlusError`.
