# ArbPlus Prompt Addendum - Part 3 of 6

**Part 3 of 6** (send after Parts 1-2, before Part 4). Covers Additions 22-25; references try/catch (Addition 6), `--OV` defaults (Addition 2), `del` (Addition 16).

---

## Addition 22 - Sending Variables Between `.arb` Files

Beyond importing a *function* from another `.arb` file (Addition 11), define how one `.arb` file can send a *variable's value* to another `.arb` file - e.g. when one script invokes another as a sub-process/sub-script rather than just importing its functions. Define:

- The syntax for passing one or more variables out to another named `.arb` file, and how that file receives them (e.g. do they arrive as pre-populated variables of the same name, or via a defined parameter list the receiving file declares?)
- Whether this is one-directional (parent hands values to child, no values come back) or whether the calling file can also receive a value back once the other file finishes
- How type information travels along with the value (does an `arb` or `map` passed this way arrive intact on the other side, or does it need to be encoded/decoded across the boundary?)
- How this differs from, and interacts with, the plain function-import mechanism from Addition 11 - are these two related mechanisms unified under one syntax, or kept as two distinct features for two different use cases?

## Addition 23 - Download Function: `dl.url(url)`

Add a built-in that downloads a URL's content and saves it directly to disk, as a third option alongside `open.url(url)` (opens in a browser, saves nothing) and `fetch.url(url)` (reads content into a variable, saves nothing): `dl.url(url)`. Define:

- Where the downloaded file is saved by default, and how a script overrides that - reusing the same programmer-hardcoded-path vs. variable-supplied-path modes, and the same `./`/`../` relative-path resolution, already defined for file building (Step 9)
- How the saved filename is determined when the URL itself doesn't make one obvious (e.g. derived from the URL's last path segment, a `Content-Disposition` header if present, or a required explicit filename argument)
- How download failures (network error, non-200 status, disk write failure) surface - reusing the try/catch convention from Addition 6 rather than a separate mechanism
- Whether `dl.url` requires the same upfront network-capability declaration discussed for `fetch.url` in Addition 14, since it's the same category of off-machine access

## Addition 24 - Manual Memory Cleanup: `--clean;`

Add a Lua-`collectgarbage()`-style manual trigger for memory cleanup, using the same `--`-prefixed statement style as `--OV`: `--clean;`. Since ArbPlus should already be garbage-collecting unreachable functions, variables, and other runtime objects automatically in the background (the normal expectation for a language like this), `--clean;` is the manual, on-demand version - forcing an immediate collection pass rather than waiting for the runtime's own schedule. Define:

- What counts as eligible for cleanup: variables gone out of scope, functions no longer referenced (including ones replaced by a later `--OV` override, if the original is no longer reachable), closed/unused file and directory handles from Steps 8-9, and any extension-held resources that have signaled they're done
- How `--clean;` relates to `del(variableName)` from Addition 16 - `del` is an explicit, immediate removal of one named variable, while `--clean;` is a broader sweep of everything currently unreachable; define whether calling `del` on something still leaves other unreachable garbage around until the next `--clean;` or automatic pass
- Scope: does `--clean;` sweep the whole running program, or only the scope it's called from (e.g. inside a function, does it only clean that function's locals)?
- Whether `--clean;` returns any information about what happened (e.g. a count of freed items, or nothing at all - a silent operation like Lua's default `collectgarbage()` call)
- Whether there's a way to disable or tune the automatic background collection (again mirroring Lua's `collectgarbage("stop")`/`("restart")`), or whether ArbPlus keeps that simple and only exposes the manual trigger

## Addition 25 - `return()` for Any Type, and `--F` to Delegate to Another Function's Return

Two related pieces of function-return behavior to formalize, since the original prompt's function step didn't pin either down explicitly:

- **`return()` accepting any data type** - confirm and specify explicitly that `return(value)` can hand back a value of *any* ArbPlus type covered so far: `int`, `float`, `string`, `boolean`, `array`, `list`, `arb`, `map` (Addition 7), or a colored-string value (Addition 17) - not just a restricted subset. Define what a bare `return()` with no value does (implicit `null`/void-equivalent, or disallowed), and whether a function's declared `Role` from the original `(--Function Role.Name (Args) { ... })` syntax can constrain what type `return()` is allowed to hand back, or whether typing stays fully dynamic.
- **`--F` - delegate to another function's return value** - using the same `--`-prefixed statement style as `--OV` and `--clean;`, add a way for one function to call another and adopt *that* function's return as its own, rather than calling it as a normal sub-expression and manually re-returning the result: `(--F OtherFunction(Args))`. This is meant for cases like custom user-facing prompts, where a function might want to hand off entirely to a different function (e.g. a menu handler delegating to whichever option's function the user picked) and have the caller see it as if the delegating function itself had returned that value. Define:
  - How `--F` differs from a plain `return(OtherFunction(Args))` - is it purely sugar for that, or does it change anything about scope/stack behavior (e.g. does the delegating function's own local state get cleaned up before or after the delegated call runs, tying into `--clean;` from Addition 24)?
  - What happens if `OtherFunction` itself doesn't return anything, or raises an error caught by `try`/`catch` (Addition 6) - does the error propagate through `--F` the same way it would through a normal nested call?
  - Whether `--F` can be used anywhere in a function body, or only as the function's final statement (since its whole purpose is "this is what my caller gets back")

