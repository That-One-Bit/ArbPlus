# ArbPlus Prompt Addendum - Part 2 of 6

**Part 2 of 6** (send after Part 1, before Parts 3-6). Covers Additions 13-21; references try/catch (Addition 6), string interpolation (Addition 1), and original Step numbers.

---

## Addition 13 - Regex / Pattern Matching

String operations so far only cover concatenation and interpolation - add pattern-based search/match/replace, e.g. `match(str, pattern)`, `replace(str, pattern, replacement)`. Define the regex flavor supported (or whether it's a simplified custom pattern language rather than full regex) and the return shape of a match (boolean, matched substring, or a list of captured groups).

## Addition 14 - Network Fetch: `fetch.url(url)`

Add a built-in that reads the contents of a URL and returns them into a variable, as distinct from `open.url(url)` (which just opens a link in a browser and returns nothing): `let content = fetch.url(url)`. Define: what type the result is (a raw string, or something richer with status code/headers alongside the body), how request failures (network error, non-200 status, timeout) surface - reusing the try/catch convention from Addition 6 rather than a separate mechanism - and whether this requires the script to declare a "network" capability up front the way shells/extensions are declared, given it's the first built-in that reaches off the local machine.

## Addition 15 - Manual Type Switching

Add explicit type-casting syntax on a variable itself, rather than only relying on the implicit coercion rules defined earlier: `variableName.type(data-type)`, e.g. `age.type(string)` to force-cast `age` to a string. Define: whether this returns a new value (leaving the original variable's type untouched) or mutates the variable in place, what happens when the cast isn't valid for the current value (e.g. casting a non-numeric string to `int`) - reusing the try/catch convention from Addition 6 rather than a separate error path - and how this interacts with `arb`'s existing on-demand decode from the type-system step, since that's already a form of manual type switching for one specific type.

## Addition 16 - Variable Deletion

Add a way to delete a variable that currently holds a value, e.g. `del(variableName)` or an ArbPlus-flavored equivalent, freeing the name so a later re-declaration isn't a redeclaration error (if the language has one). Define specifically what happens when a script tries to delete a variable that was never declared in the first place, or one that's already been deleted - reusing the try/catch convention from Addition 6 so this is a catchable error rather than a silent no-op or a crash - and whether deletion is scoped the same way declaration is (a `del` inside a function only removes the function-local variable, not a global of the same name).

## Addition 17 - Colored Segments Within a Concatenated String

Add a way to specify color/brightness on individual pieces of a concatenated string, so a single `print`/`input` call can render multiple colors in one line rather than the whole call sharing one `fg`/`bg`/`b`. Since Step 6 already defines a concatenation operator and Step 11 defines colored `print`, tie the two together rather than inventing a third mechanism - e.g. a segment-coloring function that wraps just the piece of text it applies to and is concatenation-compatible:

`print("Normal text " + color("colored piece", fg: red, bg: black, b: bright) + " more normal text")`

Define: what `color(...)` returns (a special colored-string value distinct from a plain `string`, carrying its styling alongside its text) and how concatenating that value with a plain string behaves (does the plain string on either side fall back to the script's current defaults from Addition 2's `--OV defaults(...)`, or to no color at all?); whether a colored segment can itself be built from string interpolation (Addition 1); and whether nesting a `color(...)` call inside another `color(...)` call is legal, and if so, which one wins for the overlapping styling.

## Addition 18 - Relative File Paths in `open.url`

Extend `open.url` so it also accepts a plain file path - not just a `http(s)://` URL - and automatically builds the correct `file:///` URL to open it in the system default browser/viewer. Reuse the same `./`/`../` relative-path resolution rules already defined for file building and directory operations (Step 9) rather than defining separate path rules just for this: `open.url("./report.html")` should resolve the relative path first, then convert the resulting absolute path into a well-formed `file:///` URL. Define:

- How `open.url` tells a file path apart from an actual web URL (e.g. no `://` scheme present, or it starts with `./`/`../`/a bare filename)
- The exact `file:///` construction, since this differs slightly by platform (forward slashes and drive-letter handling on Windows vs. plain POSIX paths on macOS/Linux)
- What happens if the resolved path doesn't exist - reusing the try/catch convention from Addition 6 rather than a silent failure

## Addition 19 - `localhost` URLs and `javascript:` on an Already-Open Page

Two more cases for `open.url` beyond plain web/file paths:

- **`localhost` support** - `open.url` should treat `localhost` (with or without a port, e.g. `localhost:3000` or `http://localhost:3000`) as a regular web URL, not a file path. This needs an explicit carve-out in the file-vs-URL detection logic from Addition 18, since `localhost:3000` contains a colon but no `://` scheme and could otherwise be misread the same way a Windows drive-letter path (`C:\...`) would be. Define the exact detection rule (e.g. check for a recognized scheme *or* a `localhost`/`127.0.0.1`/loopback-address prefix before falling back to file-path handling).
- **`javascript:` URIs against an already-open page** - `open.url` should also accept a `javascript:` URI to run script against a page that's already open, rather than always opening something new. Since "already open" implies a specific existing tab/window rather than "the system default browser" in general, define: how a script gets a reference/handle to a previously opened page in the first place (e.g. does a prior `open.url(...)` call return a handle that a later `open.url(javascript:..., target: handle)` call can reuse?), what happens if no such page is currently open, and - since running arbitrary script against a page has real security implications - whether this capability needs to be declared up front the same way network access was flagged in Addition 14, and what a sane default restriction looks like (e.g. only allowed against pages ArbPlus itself opened, never against an arbitrary externally-opened tab).

## Addition 20 - Metadata for Extensions Too

Extension files (C, C++, and Python) should carry the same kind of metadata block as a `.arb` file's own metadata (Step 2) - not just the core language. Define an equivalent metadata block for each extension language, using the same field set: name, version, author, `description`, `image` (file-path or base64 form), dependencies, and languages used (for an extension, this would just be its own implementation language plus anything *it* in turn depends on). Cover:

- The exact syntax per language - since C/C++/Python don't have ArbPlus's `#meta { }` block, define an idiomatic equivalent for each (e.g. a comment-block convention the runtime specifically parses, a required constant/struct the registration entry point must populate, or a sidecar file shipped alongside the extension)
- How the main `.arb` script sees this metadata - e.g. can a script query a loaded extension's declared version/author/description at runtime, the way it might query its own metadata?
- What happens on a **version mismatch** between what a `.arb` file's dependency declaration expects (from Step 2) and what the extension's own metadata reports - is this a load-time error (reusing the try/catch convention from Addition 6), a warning, or ignored?
- Whether the three extension worked examples from Step 14 should each be updated to include this metadata block, so the metadata convention isn't just described but actually demonstrated in all three languages

## Addition 21 - Cross-Feature Composability

Make sure the addressed-data features from Step 8 (`addr.[dataType](...)` and `txtRC(Row, Column)`) aren't limited to reading from a file on disk - they should also be usable directly against data pulled in from other sources this addendum has added, most notably `fetch.url(url)`'s result. For example: `txtRC` against the rows/columns of a CSV fetched over the network, or `addr.hex(...)`/finding a byte marker inside binary content that came back from a `fetch.url(...)` call, without first having to write that content to a temporary file just to re-read it. Define:

- Whether `addr.[dataType](...)` and `txtRC(...)` take a data source as an explicit argument (e.g. `txtRC(fetchResult, Row, Column)`) or whether they operate on ArbPlus's existing string/`arb`/binary-shaped values generically, regardless of where the value came from
- Whether a marker/address search (`addr.hex(0x1A)` style) against fetched content behaves identically to the same search against a file - same return shape, same out-of-bounds/not-found behavior (reusing the try/catch convention from Addition 6)
- More generally, state the underlying principle explicitly for the LLM to apply throughout the rest of the implementation: any built-in that operates on "data" (addressing, row/column access, image encoding, pattern matching) should work uniformly across ArbPlus's data-bearing types and sources - a file read, a `fetch.url` result, an `arb` value - rather than being hardcoded to only accept one specific source