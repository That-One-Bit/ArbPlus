# ext_gui_web — Web-based HTML GUI Extension

Built-in extension providing HTML/CSS/JS sandboxed windows with bidirectional communication and a builder API.

## Loading


```arb
loadExt("ext_gui_web", "python");
```

## Core Blocks (7)

| Block | Description |
|-------|-------------|
| `gui.open(html, title: "...", width: 800, height: 600)` | Open raw HTML in a sandboxed window. Returns the localhost URL. |
| `gui.openUrl(url, title: "...")` | Fetch HTML from a URL and open it in the GUI window. |
| `gui.on("action", handlerFunc)` | Register an ArbPlus function to handle an action from the page. |
| `gui.send("action", data)` | Push data from ArbPlus to the page via Server-Sent Events (SSE). |
| `gui.close()` | Shut down the GUI server and close the window. |
| `gui.status()` | Returns `true` if the GUI server is running, `false` otherwise. |
| `gui.wait(seconds: 30)` | Keep the server alive for the specified seconds so the user can interact with GUI windows. Blocks until the timeout expires. |

## Builder Blocks (13)

| Block | Description |
|-------|-------------|
| `gui.create(title, width: 800, height: 600)` | Start building a new GUI page. Resets all accumulated elements. |
| `gui.add(type, content, id: ..., class: ..., style: ..., action: ...)` | Add any HTML element by tag name. |
| `gui.box(content, id: ..., class: ..., style: ...)` | Add a `<div>` box. |
| `gui.text(content, tag: "p", id: ..., style: ...)` | Add a text element (`<p>`, `<h1>`, `<span>`, etc. via `tag:`). |
| `gui.button(label, action: "...", id: ..., style: ...)` | Add a button that triggers an ArbPlus action via `ARB.call()`. |
| `gui.inputField(placeholder: "...", id: ..., type: "text", style: ...)` | Add an input field. |
| `gui.image(src, alt: ..., id: ..., width: ..., height: ...)` | Add an image. |
| `gui.link(href, label, id: ...)` | Add a hyperlink. |
| `gui.list(items, ordered: ..., id: ...)` | Add a list. `items` is pipe-separated (`"a|b|c"`). |
| `gui.style(css)` | Add CSS styling to the page. |
| `gui.script(js)` | Add JavaScript code to the page. |
| `gui.html()` | Build and return the full HTML string from accumulated elements. |
| `gui.show()` | Render accumulated elements and open the window (calls `gui.open()` internally). |

## Page-to-ArbPlus Communication

The `gui.open()` block automatically injects a communication bridge script into the HTML. The bridge provides:

- `ARB.call(action, data)` — Send a POST request to the local server, which dispatches to a registered ArbPlus handler. Returns a Promise.
- `ARB.on(action, callback)` — Register a JavaScript callback for messages pushed from ArbPlus via `gui.send()`.

## Usage Examples

### Approach 1: Raw HTML

```arb
loadExt("ext_gui_web", "python");

gui.open("<h1>Hello!</h1><button onclick='ARB.call(\"greet\", \"world\")'>Click</button>");
gui.on("greet", myHandler);

--Function pub.myHandler(data) {
    print("Button clicked: " + data);
    gui.send("update", "Processed: " + data);
}
```

### Approach 2: Builder API

```arb
loadExt("ext_gui_web", "python");

gui.create("My App", width: 500, height: 400);
gui.style("body { background: #1a1a2e; color: white; }");
gui.text("Enter your name:", tag: "label");
gui.inputField(placeholder: "Name...", id: "name");
gui.button("Submit", action: "submit", id: "btn");
gui.show();
```

### Approach 3: URL Fetching

```arb
loadExt("ext_gui_web", "python");

gui.openUrl("https://example.com", title: "Example");
```

## Grammar

```
gui_open     ::= "gui.open" "(" expr ("," tag)* ")"
gui_open_url ::= "gui.openUrl" "(" expr ("," tag)* ")"
gui_on       ::= "gui.on" "(" expr "," expr ")"
gui_send     ::= "gui.send" "(" expr "," expr ")"
gui_close    ::= "gui.close" "(" ")"
gui_status   ::= "gui.status" "(" ")"
gui_wait     ::= "gui.wait" "(" (expr)? ("," "seconds" ":" expr)? ")"

gui_create   ::= "gui.create" "(" expr? ("," tag)* ")"
gui_add      ::= "gui.add" "(" expr ("," expr)? ("," tag)* ")"
gui_box      ::= "gui.box" "(" expr? ("," tag)* ")"
gui_text     ::= "gui.text" "(" expr ("," tag)* ")"
gui_button   ::= "gui.button" "(" expr ("," tag)* ")"
gui_input    ::= "gui.inputField" "(" ("," tag)* ")"
gui_image    ::= "gui.image" "(" expr ("," tag)* ")"
gui_link     ::= "gui.link" "(" expr "," expr ("," tag)* ")"
gui_list     ::= "gui.list" "(" expr ("," tag)* ")"
gui_style    ::= "gui.style" "(" expr ")"
gui_script   ::= "gui.script" "(" expr ")"
gui_html     ::= "gui.html" "(" ")"
gui_show     ::= "gui.show" "(" ")"

gui_tag      ::= "title" | "width" | "height" | "id" | "class" | "style"
               | "action" | "placeholder" | "src" | "href" | "alt"
               | "onclick" | "type" | "tag" | "ordered"
```

## Architecture Notes

### Threading Model

The extension uses `socketserver.ThreadingTCPServer` (not the single-threaded `TCPServer`) so that the long-lived SSE connection (`/api/events`) and button-click POSTs (`/api/call`) can be served concurrently. With a single-threaded server, the SSE connection blocks the only thread and no further requests can be processed — button clicks silently time out.

### Double-Import Fix

When the interpreter runs as `python3 interpreter.py`, the module is loaded as `__main__`. The handler closures must NOT use `from interpreter import ArbString` — that would import a *second copy* of the module with different class identities, causing `isinstance` checks in `arb_to_string()` to fail (values would render as `ArbValue(string, '...')` instead of their string value). The fix uses `sys.modules[type(interp).__module__]` to get the correct `ArbString`/`ArbNull` classes from the running interpreter's own module.

### Browser Tabs vs OS Windows

- `gui.open()` and `gui.show()` open **browser tabs** (via `webbrowser.open()`) — these are HTML pages in the user's default browser
- `gui.dialog()`, `gui.yesNo()`, etc. (from `ext_gui`) open **native OS windows** via tkinter
- Browser tabs support bidirectional communication (button clicks → ArbPlus handlers, SSE → DOM updates)
- OS windows are modal dialogs that block until the user responds

## Dynamic DOM Update Blocks (27)

These blocks push live updates to the browser via SSE — no restart, no page reload. The bridge script auto-handles them, so no user JavaScript is required.

### Content Manipulation (6)

| Block | Description |
|-------|-------------|
| `gui.update(id, text)` | Set element's text content (textContent). |
| `gui.setHTML(id, html)` | Set element's innerHTML. |
| `gui.append(id, html)` | Append HTML to end of element. |
| `gui.prepend(id, html)` | Insert HTML at beginning of element. |
| `gui.clear(id)` | Clear element's content (innerHTL = ''). |
| `gui.replace(id, html)` | Replace element entirely (outerHTML). |

### CSS & Classes (4)

| Block | Description |
|-------|-------------|
| `gui.setStyle(id, css)` | Set element's style attribute. |
| `gui.addClass(id, class)` | Add a CSS class. |
| `gui.removeClass(id, class)` | Remove a CSS class. |
| `gui.toggleClass(id, class)` | Toggle a CSS class on/off. |

### Attributes (2)

| Block | Description |
|-------|-------------|
| `gui.setAttr(id, attr, value)` | Set any attribute on an element. |
| `gui.removeAttr(id, attr)` | Remove an attribute from an element. |

### Visibility & Removal (3)

| Block | Description |
|-------|-------------|
| `gui.showEl(id)` | Show a hidden element (removes `display: none`). |
| `gui.hideEl(id)` | Hide an element (sets `display: none`). |
| `gui.remove(id)` | Remove an element from the DOM entirely. |

### Element Insertion (3)

| Block | Description |
|-------|-------------|
| `gui.insertBefore(id, html)` | Insert HTML before an element. |
| `gui.insertAfter(id, html)` | Insert HTML after an element. |
| `gui.clone(id, newId)` | Clone an element and give the clone a new id. |

### Form & Input Control (5)

| Block | Description |
|-------|-------------|
| `gui.setVal(id, value)` | Set an input element's value. |
| `gui.focus(id)` | Focus an element. |
| `gui.blur(id)` | Remove focus from an element. |
| `gui.disable(id)` | Disable a form element. |
| `gui.enable(id)` | Enable a form element. |

### Scroll Control (2)

| Block | Description |
|-------|-------------|
| `gui.scroll(id, behavior: "smooth")` | Scroll element into view. |
| `gui.scrollTop(id, pixels)` | Set scroll position of a scrollable element. |

### Page-Level (2)

| Block | Description |
|-------|-------------|
| `gui.setTitle(title)` | Update the browser tab title. |
| `gui.evalJS(code)` | Evaluate arbitrary JavaScript in the page. Escape hatch for anything not covered. |

### How It Works

1. ArbPlus calls e.g. `gui.update("mydiv", "New text")`.
2. The extension sends an SSE event with `action: "_arb_dom"` and a JSON payload like `{"op": "text", "id": "mydiv", "value": "New text"}`.
3. The browser's bridge script intercepts `_arb_dom` events and applies the DOM operation directly — no user JS needed.

### Usage Pattern

```arb
--Function pub.onGreet(data) {
    // Live update — no restart, no page reload
    gui.update("result", "Hello, " + data + "!");
    gui.setStyle("result", "color: green; font-weight: bold;");
    gui.showEl("message");
}

loadExt("ext_gui_web", "python");
gui.on("greet", "onGreet");

// Open the page
let [string] html = "<button onclick=\"ARB.call('greet', 'world')\">Click</button>
<div id='result'>Waiting...</div>
<div id='message' style='display: none;'>Live!</div>";
let [string] url = gui.open(html);

// Also push updates from ArbPlus without a button click
gui.wait(seconds: 3);
gui.update("result", "Updated from ArbPlus!");
gui.append("result", "<br><small>Appended live</small>");

gui.wait(seconds: 10);
gui.close();
```
