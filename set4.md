# ArbPlus Prompt Addendum - Part 4 of 6

**Part 4 of 6** (send after Parts 1-3, before Parts 5-6). Covers Additions 26-27 (inline Python, and file-path escapes for c{}/py{}/cmd{}/ps{} blocks); references try/catch (Addition 6), the c{} block (Step 1), and Step 13's extension mechanism.

---

## Addition 26 - Inline Python: a `py{ ... }` Escape Block

Since the interpreter itself is implemented in Python (Step 3), add a `py{ ... }` block as an inline escape into raw Python code within a `.arb` file, similar in spirit to the existing `c{ ... }` block from Step 1 - but running directly in the same Python process as the interpreter rather than being handed off to a separate compiler/toolchain. Define:

- How values pass between ArbPlus and the `py{ }` block: which ArbPlus variables are visible inside the block, how a value the block computes gets assigned back to an ArbPlus variable, and how types translate both directions (an ArbPlus `arb`/`map`/colored-string vs. a native Python value)
- **Standard-library-only restriction**: a `py{ }` block may only use Python's built-in/standard-library modules (e.g. `math`, `json`, `re`, `datetime`) - it must NOT `import` any third-party/non-base package. Anything needing a third-party Python package has to be built as a proper ArbPlus extension instead (Step 13's Python extension path), not smuggled in through an inline block. Define how the interpreter enforces this at parse-time or load-time (e.g. statically scanning the block's `import` statements against an allowlist of standard-library module names before running it) and what error a script gets if it violates this (reusing the try/catch convention from Addition 6).
- How `py{ }` blocks interact with the "one interpreter, no separate compiler" architecture from Step 3 - since Python doesn't need a compile step the way `c{ }` blocks do, clarify that a `py{ }` block just executes directly rather than being built into anything
- Whether a `py{ }` block can call ArbPlus built-in functions from inside it, or whether it's a one-way handoff (ArbPlus data goes in, a Python value comes back, nothing else crosses the boundary mid-block)

## Addition 27 - Loading a File's Contents Into an Escape Block via `$!`

Add a way to load an external file's contents directly into a `c{ }`, `py{ }`, `cmd{ }`, or `ps{ }` escape block by path, rather than only ever writing that block's code inline. This is distinct from Addition 1's `${variable}` string interpolation (which embeds a *value* into a string) - `$!` specifically means "treat this block's source as the contents of the file at this path," where the path itself comes from an ArbPlus variable holding a file path (per Step 8/9's existing path-variable handling):

```
c{$!cSourcePathVar}
py{$!pySourcePathVar}
cmd{$!scriptPathVar}
ps{$!scriptPathVar}
```

Define:

- That `$!pathVariable` must be the sole content of the block when used this way (i.e. it's either "load this whole block from a file" or "write the code inline," not a mix of both in one block) - or, if partial mixing is meaningful, define exactly where the loaded content is spliced in
- Path resolution: reuse the same `./`/`../` relative-path rules already defined for file building (Step 9) rather than a separate rule just for this
- What happens when the path variable doesn't point to an existing/readable file - reusing the try/catch convention from Addition 6, consistent with the plain file-reading error handling from Step 8
- For `py{$!...}`: the loaded file's contents are still subject to the standard-library-only restriction from Addition 26 - importing a third-party package from a loaded `.py` file must be rejected exactly the same way as it would be in an inline `py{ }` block
- For `cmd{$!...}`/`ps{$!...}`: confirm this is the mechanism for running an existing `.bat`/`.ps1` script file from within ArbPlus, as opposed to Step 4's inline shell-escape syntax for short one-off commands
- Whether the loaded file needs a specific extension to match its block type (e.g. does `c{$!path}` require `path` to end in `.c`, or is any extension accepted since the block type already declares the language?)

