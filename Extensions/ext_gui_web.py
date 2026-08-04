# ArbPlus Built-in Extension — Web-based HTML GUI
# @arbplus-meta name="ext_gui_web"
# @arbplus-meta version="2.0"
# @arbplus-meta author="ArbPlus"
# @arbplus-meta description="HTML/CSS/JS sandboxed window system with bidirectional communication, URL fetching, builder API, and multi-window support"
# @arbplus-meta dependencies=""
# @arbplus-meta languages="python"
#
# This is a built-in extension — load it via loadExt("ext_gui_web", "python")
#
# Core Blocks (7):
#   gui.open(html, title: "...", width: 800, height: 600)  -> URL string
#   gui.openUrl(url, title: "...")                         -> URL string (fetches HTML from URL)
#   gui.on("action", handlerFunc)                           -> bool
#   gui.send("action", data)                                -> bool
#   gui.close(url: "...")                                    -> bool  (closes all, or one by URL)
#   gui.status()                                             -> bool
#   gui.wait(seconds: 30)                                    -> bool  (keeps server alive for user interaction)
#
# Builder Blocks (13):
#   gui.create, gui.add, gui.box, gui.text, gui.button,
#   gui.inputField, gui.image, gui.link, gui.list,
#   gui.style, gui.script, gui.html, gui.show

import os
import sys
import json as _json
import threading
import time as _time
import http.server
import socketserver
import urllib.parse
import urllib.request
import webbrowser

_state = {}

def _get_state(interp):
    key = id(interp)
    if key not in _state:
        _state[key] = {
            "windows": [],          # list of {server, thread, port, html, handlers, sse_clients, url}
            "handlers": {},         # global handlers (shared across all windows)
            "sse_clients": [],      # global SSE clients list (legacy)
            "builder": {"title": "ArbPlus GUI", "elements": [], "css": "", "js": "", "width": 800, "height": 600},
        }
    return _state[key]

def _to_str(val):
    if val is None: return ""
    if hasattr(val, 'val'): return str(val.val)
    if hasattr(val, 'py'): return str(val.py())
    return str(val)

def _to_int(val, default=0):
    try: return int(_to_str(val))
    except:
        try: return int(val)
        except: return default

BRIDGE_SCRIPT = '''
<script>
(function() {
    const ARB = {
        call: async function(action, data) {
            const res = await fetch('/api/call', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: action, data: data})
            });
            return await res.json();
        },
        callbacks: {},
        on: function(action, callback) {
            ARB.callbacks[action] = callback;
        }
    };

    // Auto-handle DOM updates from ArbPlus (no user JS needed)
    function _arb_dom(op, payload) {
        // Special pseudo-ids for page-level operations
        if (payload.id === '__arb_eval__') { eval(payload.value); return; }
        if (payload.id === '__arb_title__') { document.title = payload.value; return; }
        const el = document.getElementById(payload.id);
        if (!el) return;
        switch(op) {
            case 'text':       el.textContent = payload.value; break;
            case 'html':       el.innerHTML = payload.value; break;
            case 'style':      el.setAttribute('style', payload.value); break;
            case 'show':       el.style.display = ''; break;
            case 'hide':       el.style.display = 'none'; break;
            case 'append':     el.insertAdjacentHTML('beforeend', payload.value); break;
            case 'prepend':    el.insertAdjacentHTML('afterbegin', payload.value); break;
            case 'insertBefore': el.insertAdjacentHTML('beforebegin', payload.value); break;
            case 'insertAfter':  el.insertAdjacentHTML('afterend', payload.value); break;
            case 'attr':       el.setAttribute(payload.attr, payload.value); break;
            case 'removeAttr': el.removeAttribute(payload.value); break;
            case 'remove':     el.remove(); break;
            case 'clear':      el.innerHTML = ''; break;
            case 'replace':    el.outerHTML = payload.value; break;
            case 'addClass':   el.classList.add(payload.value); break;
            case 'removeClass': el.classList.remove(payload.value); break;
            case 'toggleClass': el.classList.toggle(payload.value); break;
            case 'val':        el.value = payload.value; break;
            case 'focus':      el.focus(); break;
            case 'blur':       el.blur(); break;
            case 'disable':    el.disabled = true; break;
            case 'enable':     el.disabled = false; break;
            case 'clone':      const clone = el.cloneNode(true); clone.id = payload.value; el.parentNode.appendChild(clone); break;
            case 'scroll':     el.scrollIntoView({behavior: payload.value || 'smooth'}); break;
            case 'scrollTop':  el.scrollTop = parseInt(payload.value) || 0; break;
        }
    }

    const evtSource = new EventSource('/api/events');
    evtSource.addEventListener('message', function(e) {
        const msg = JSON.parse(e.data);
        // Auto-handle _arb_dom events
        if (msg.action === '_arb_dom' && typeof msg.data === 'object') {
            _arb_dom(msg.data.op, msg.data);
            return;
        }
        // User-registered callbacks
        if (ARB.callbacks[msg.action]) {
            ARB.callbacks[msg.action](msg.data);
        }
    });
    window.ARB = ARB;
})();
</script>
'''

def _inject_bridge(html_content):
    if '</body>' in html_content.lower():
        idx = html_content.lower().rfind('</body>')
        return html_content[:idx] + BRIDGE_SCRIPT + html_content[idx:]
    elif '</html>' in html_content.lower():
        idx = html_content.lower().rfind('</html>')
        return html_content[:idx] + BRIDGE_SCRIPT + html_content[idx:]
    return html_content + BRIDGE_SCRIPT

def _wrap_html(html_content, title):
    if '<html' not in html_content.lower():
        return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title>
<style>body {{ font-family: sans-serif; margin: 0; padding: 20px; }}</style>
</head><body>{html_content}</body></html>'''
    return html_content

def _open_browser(url):
    """Try multiple ways to open the browser."""
    try:
        webbrowser.open(url, new=1, autoraise=True)
        return True
    except:
        pass
    for browser in ('firefox', 'chrome', 'chromium', 'safari', 'opera'):
        try:
            webbrowser.get(browser).open(url)
            return True
        except:
            continue
    print(f"[GUI] Open this URL in your browser: {url}")
    return False

# ── Core Blocks ──────────────────────────────────────────────────────

def gui_open(args, kwargs, interp):
    state = _get_state(interp)
    html_content = _to_str(args[0]) if args else ""
    title = _to_str(kwargs.get("title")) if "title" in kwargs else "ArbPlus GUI"
    width = _to_int(kwargs.get("width"), 800) if "width" in kwargs else 800
    height = _to_int(kwargs.get("height"), 600) if "height" in kwargs else 600
    html_content = _inject_bridge(html_content)
    html_content = _wrap_html(html_content, title)

    win = {
        "html": html_content,
        "handlers": state["handlers"],
        "sse_clients": [],
        "port": 0,
        "server": None,
        "thread": None,
        "url": "",
    }
    win_ref = win

    class GUIHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/events':
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('Connection', 'keep-alive')
                self.end_headers()
                win_ref["sse_clients"].append(self)
                state["sse_clients"].append(self)
                try:
                    while True: _time.sleep(1)
                except: pass
            else:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(win_ref["html"].encode('utf-8'))
        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == '/api/call':
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length).decode('utf-8')
                req = _json.loads(body)
                action = req.get('action', '')
                data = req.get('data', None)
                handler_fn = win_ref["handlers"].get(action)
                if handler_fn:
                    try:
                        result = handler_fn(data)
                        response = {'ok': True, 'result': result}
                    except Exception as e:
                        response = {'ok': False, 'error': str(e)}
                else:
                    response = {'ok': False, 'error': f'No handler for action: {action}'}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(_json.dumps(response).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()

    server = socketserver.ThreadingTCPServer(('', port), GUIHandler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://localhost:{port}/"
    win["port"] = port
    win["server"] = server
    win["thread"] = thread
    win["url"] = url
    state["windows"].append(win)

    _open_browser(url)
    return url

def gui_open_url(args, kwargs, interp):
    """gui.openUrl(url, title: ...) — fetch HTML from URL and open in GUI."""
    url = _to_str(args[0]) if args else ""
    if not url:
        raise RuntimeError("gui.openUrl() requires a URL argument")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'ArbPlus/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html_content = response.read().decode('utf-8', errors='replace')
    except Exception as e:
        raise RuntimeError(f"gui.openUrl() fetch failed: {e}")
    html_content = _inject_bridge(html_content)
    title = _to_str(kwargs.get("title")) if "title" in kwargs else url
    new_kwargs = dict(kwargs)
    new_kwargs["title"] = title
    return gui_open([html_content], new_kwargs, interp)

def gui_on(args, kwargs, interp):
    state = _get_state(interp)
    action = _to_str(args[0]) if args else ""
    if len(args) < 2:
        raise RuntimeError("gui.on() requires an action name and a handler function")
    handler_str = _to_str(args[1])
    if handler_str in interp.functions:
        # Get ArbString/ArbNull from the interpreter's own module to avoid
        # the Python double-import problem (interpreter.py runs as __main__
        # but `from interpreter import` loads a second copy with different classes)
        import sys as _sys
        _interp_mod = _sys.modules.get(type(interp).__module__)
        _ArbString = getattr(_interp_mod, 'ArbString', None)
        _ArbNull = getattr(_interp_mod, 'ArbNull', None)
        def handler(data):
            if _ArbString and data is not None:
                arg = _ArbString(str(data))
            elif _ArbNull and data is None:
                arg = _ArbNull()
            else:
                arg = str(data) if data is not None else ""
            result = interp.call_user_function(handler_str, [arg], {}, interp.global_env)
            return _to_str(result)
    else:
        def handler(data):
            return str(data) if data is not None else ""
    state["handlers"][action] = handler
    return True

def gui_send(args, kwargs, interp):
    state = _get_state(interp)
    action = _to_str(args[0]) if args else ""
    data = _to_str(args[1]) if len(args) > 1 else ""
    msg = _json.dumps({"action": action, "data": data})
    sse_data = f"data: {msg}\n\n"
    sent = 0
    for win in state["windows"]:
        for client in win["sse_clients"]:
            try:
                client.wfile.write(sse_data.encode('utf-8'))
                client.wfile.flush()
                sent += 1
            except: pass
    for client in state["sse_clients"]:
        try:
            client.wfile.write(sse_data.encode('utf-8'))
            client.wfile.flush()
        except: pass
    return sent > 0 or True

def gui_close(args, kwargs, interp):
    state = _get_state(interp)
    url = _to_str(kwargs.get("url")) if "url" in kwargs else ""
    closed = 0
    if url:
        for win in state["windows"][:]:
            if win["url"] == url or url in win["url"]:
                try: win["server"].shutdown()
                except: pass
                state["windows"].remove(win)
                closed += 1
    else:
        for win in state["windows"]:
            try: win["server"].shutdown()
            except: pass
            closed += 1
        state["windows"] = []
        state["sse_clients"] = []
    return closed > 0

def gui_status(args, kwargs, interp):
    state = _get_state(interp)
    return len(state["windows"]) > 0

def gui_wait(args, kwargs, interp):
    """gui.wait(seconds: 30) — keep the server alive for user interaction."""
    seconds = _to_int(kwargs.get("seconds"), 30) if "seconds" in kwargs else 30
    if args:
        seconds = _to_int(args[0], 30)
    elapsed = 0
    while elapsed < seconds:
        _time.sleep(1)
        elapsed += 1
    return True

# ── Builder Blocks ───────────────────────────────────────────────────

def _ensure_builder(interp):
    return _get_state(interp)["builder"]

def gui_create(args, kwargs, interp):
    state = _get_state(interp)
    state["builder"] = {
        "title": _to_str(args[0]) if args else "ArbPlus GUI",
        "elements": [], "css": "", "js": "",
        "width": _to_int(kwargs.get("width"), 800) if "width" in kwargs else 800,
        "height": _to_int(kwargs.get("height"), 600) if "height" in kwargs else 600,
    }
    return True

def gui_add(args, kwargs, interp):
    b = _ensure_builder(interp)
    elem_type = _to_str(args[0]) if args else "div"
    content = _to_str(args[1]) if len(args) > 1 else ""
    attrs = []
    for attr_key in ("id", "class", "style", "action", "placeholder", "src", "href", "alt", "onclick", "type"):
        if attr_key in kwargs:
            val = _to_str(kwargs[attr_key])
            if attr_key == "action" and elem_type == "button":
                btn_id = _to_str(kwargs.get("id")) if "id" in kwargs else f"btn_{len(b['elements'])}"
                attrs.append(f"onclick=\"ARB.call('{val}', document.getElementById('{btn_id}')?.value || 'click')\"")
            elif attr_key == "type" and elem_type == "input":
                attrs.append(f'type="{val}"')
            elif attr_key == "placeholder" and elem_type == "input":
                attrs.append(f'placeholder="{val}"')
            elif attr_key == "src" and elem_type in ("img", "video", "audio"):
                attrs.append(f'src="{val}"')
            elif attr_key == "href" and elem_type == "a":
                attrs.append(f'href="{val}"')
            elif attr_key in ("id", "class", "style", "alt"):
                attrs.append(f'{attr_key}="{val}"')
    attr_str = (" " + " ".join(attrs)) if attrs else ""
    void_tags = {"br", "hr", "img", "input"}
    if elem_type in void_tags:
        html = f"<{elem_type}{attr_str}>"
    else:
        html = f"<{elem_type}{attr_str}>{content}</{elem_type}>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_box(args, kwargs, interp):
    b = _ensure_builder(interp)
    content = _to_str(args[0]) if args else ""
    attrs = []
    for key in ("id", "class", "style"):
        if key in kwargs:
            attrs.append(f'{key}="{_to_str(kwargs[key])}"')
    attr_str = (" " + " ".join(attrs)) if attrs else ""
    html = f"<div{attr_str}>{content}</div>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_text(args, kwargs, interp):
    b = _ensure_builder(interp)
    content = _to_str(args[0]) if args else ""
    tag = _to_str(kwargs.get("tag")) if "tag" in kwargs else "p"
    attrs = []
    for key in ("id", "class", "style"):
        if key in kwargs:
            attrs.append(f'{key}="{_to_str(kwargs[key])}"')
    attr_str = (" " + " ".join(attrs)) if attrs else ""
    html = f"<{tag}{attr_str}>{content}</{tag}>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_button(args, kwargs, interp):
    b = _ensure_builder(interp)
    label = _to_str(args[0]) if args else "Button"
    action = _to_str(kwargs.get("action")) if "action" in kwargs else ""
    btn_id = _to_str(kwargs.get("id")) if "id" in kwargs else f"btn_{len(b['elements'])}"
    style = _to_str(kwargs.get("style")) if "style" in kwargs else ""
    attrs = [f'id="{btn_id}"']
    if style: attrs.append(f'style="{style}"')
    if action:
        attrs.append(f"onclick=\"ARB.call('{action}', document.getElementById('{btn_id}')?.value || 'click')\"")
    attr_str = " ".join(attrs)
    html = f"<button {attr_str}>{label}</button>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_input_field(args, kwargs, interp):
    b = _ensure_builder(interp)
    input_type = _to_str(kwargs.get("type")) if "type" in kwargs else "text"
    elem_id = _to_str(kwargs.get("id")) if "id" in kwargs else f"input_{len(b['elements'])}"
    placeholder = _to_str(kwargs.get("placeholder")) if "placeholder" in kwargs else ""
    style = _to_str(kwargs.get("style")) if "style" in kwargs else ""
    attrs = [f'type="{input_type}"', f'id="{elem_id}"']
    if placeholder: attrs.append(f'placeholder="{placeholder}"')
    if style: attrs.append(f'style="{style}"')
    attr_str = " ".join(attrs)
    html = f"<input {attr_str}>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_image(args, kwargs, interp):
    b = _ensure_builder(interp)
    src = _to_str(args[0]) if args else ""
    attrs = [f'src="{src}"']
    if "alt" in kwargs: attrs.append(f'alt="{_to_str(kwargs["alt"])}"')
    if "id" in kwargs: attrs.append(f'id="{_to_str(kwargs["id"])}"')
    if "width" in kwargs: attrs.append(f'width="{_to_str(kwargs["width"])}"')
    if "height" in kwargs: attrs.append(f'height="{_to_str(kwargs["height"])}"')
    attr_str = " ".join(attrs)
    html = f"<img {attr_str}>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_link(args, kwargs, interp):
    b = _ensure_builder(interp)
    href = _to_str(args[0]) if args else "#"
    label = _to_str(args[1]) if len(args) > 1 else "link"
    attrs = [f'href="{href}"']
    if "id" in kwargs: attrs.append(f'id="{_to_str(kwargs["id"])}"')
    attr_str = " ".join(attrs)
    html = f"<a {attr_str}>{label}</a>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_list(args, kwargs, interp):
    b = _ensure_builder(interp)
    items_str = _to_str(args[0]) if args else ""
    items = [i.strip() for i in items_str.split("|")] if items_str else []
    ordered = "ordered" in kwargs
    tag = "ol" if ordered else "ul"
    attrs = ""
    if "id" in kwargs: attrs = f' id="{_to_str(kwargs["id"])}"'
    items_html = "".join(f"<li>{item}</li>" for item in items)
    html = f"<{tag}{attrs}>{items_html}</{tag}>"
    b["elements"].append(html)
    return len(b["elements"])

def gui_style(args, kwargs, interp):
    b = _ensure_builder(interp)
    css = _to_str(args[0]) if args else ""
    b["css"] += "\n" + css
    return True

def gui_script(args, kwargs, interp):
    b = _ensure_builder(interp)
    js = _to_str(args[0]) if args else ""
    b["js"] += "\n" + js
    return True

def gui_html(args, kwargs, interp):
    b = _ensure_builder(interp)
    elements_html = "\n".join(b["elements"])
    css = f"<style>{b['css']}</style>" if b["css"] else ""
    js = f"<script>{b['js']}</script>" if b["js"] else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{b['title']}</title>{css}</head><body>
{elements_html}{js}</body></html>"""

def gui_show(args, kwargs, interp):
    html = gui_html([], {}, interp)
    b = _ensure_builder(interp)
    new_kwargs = {"title": b["title"], "width": b["width"], "height": b["height"]}
    return gui_open([html], new_kwargs, interp)


# ── Dynamic DOM Update Blocks ───────────────────────────────────────

def _gui_dom_send(interp, payload, url_filter=None):
    """Send a _arb_dom SSE event to browser(s) to update the DOM directly."""
    msg = _json.dumps({"action": "_arb_dom", "data": payload})
    sse_data = "data: " + msg + "\n\n"
    state = _get_state(interp)
    for win in state["windows"]:
        if url_filter and url_filter not in win["url"]:
            continue
        for client in win["sse_clients"]:
            try:
                client.wfile.write(sse_data.encode("utf-8"))
                client.wfile.flush()
            except: pass
    for client in state["sse_clients"]:
        try:
            client.wfile.write(sse_data.encode("utf-8"))
            client.wfile.flush()
        except: pass

def gui_update(args, kwargs, interp):
    """gui.update(id, text) — update an element's text content live."""
    if len(args) < 2:
        raise RuntimeError("gui.update() requires an element id and text content")
    el_id = _to_str(args[0])
    text = _to_str(args[1])
    _gui_dom_send(interp, {"op": "text", "id": el_id, "value": text})
    return True

def gui_setHTML(args, kwargs, interp):
    """gui.setHTML(id, html) — update an element's innerHTML live."""
    if len(args) < 2:
        raise RuntimeError("gui.setHTML() requires an element id and HTML content")
    el_id = _to_str(args[0])
    html = _to_str(args[1])
    _gui_dom_send(interp, {"op": "html", "id": el_id, "value": html})
    return True

def gui_setStyle(args, kwargs, interp):
    """gui.setStyle(id, css) — update an element's style attribute live."""
    if len(args) < 2:
        raise RuntimeError("gui.setStyle() requires an element id and CSS string")
    el_id = _to_str(args[0])
    css = _to_str(args[1])
    _gui_dom_send(interp, {"op": "style", "id": el_id, "value": css})
    return True

def gui_showEl(args, kwargs, interp):
    """gui.showEl(id) — show a hidden element."""
    if not args:
        raise RuntimeError("gui.showEl() requires an element id")
    el_id = _to_str(args[0])
    _gui_dom_send(interp, {"op": "show", "id": el_id})
    return True

def gui_hideEl(args, kwargs, interp):
    """gui.hideEl(id) — hide an element."""
    if not args:
        raise RuntimeError("gui.hideEl() requires an element id")
    el_id = _to_str(args[0])
    _gui_dom_send(interp, {"op": "hide", "id": el_id})
    return True

def gui_append(args, kwargs, interp):
    """gui.append(id, html) — append HTML content to an element live."""
    if len(args) < 2:
        raise RuntimeError("gui.append() requires an element id and HTML content")
    el_id = _to_str(args[0])
    html = _to_str(args[1])
    _gui_dom_send(interp, {"op": "append", "id": el_id, "value": html})
    return True

def gui_setAttr(args, kwargs, interp):
    """gui.setAttr(id, attr, value) — set an element attribute live."""
    if len(args) < 3:
        raise RuntimeError("gui.setAttr() requires element id, attribute name, and value")
    el_id = _to_str(args[0])
    attr = _to_str(args[1])
    val = _to_str(args[2])
    _gui_dom_send(interp, {"op": "attr", "id": el_id, "attr": attr, "value": val})
    return True

def gui_remove(args, kwargs, interp):
    """gui.remove(id) — remove an element from the DOM."""
    if not args:
        raise RuntimeError("gui.remove() requires an element id")
    el_id = _to_str(args[0])
    _gui_dom_send(interp, {"op": "remove", "id": el_id})
    return True


def gui_prepend(args, kwargs, interp):
    """gui.prepend(id, html) — insert HTML at the beginning of an element."""
    if len(args) < 2:
        raise RuntimeError("gui.prepend() requires an element id and HTML content")
    _gui_dom_send(interp, {"op": "prepend", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_insertBefore(args, kwargs, interp):
    """gui.insertBefore(id, html) — insert HTML before an element."""
    if len(args) < 2:
        raise RuntimeError("gui.insertBefore() requires an element id and HTML content")
    _gui_dom_send(interp, {"op": "insertBefore", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_insertAfter(args, kwargs, interp):
    """gui.insertAfter(id, html) — insert HTML after an element."""
    if len(args) < 2:
        raise RuntimeError("gui.insertAfter() requires an element id and HTML content")
    _gui_dom_send(interp, {"op": "insertAfter", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_clear(args, kwargs, interp):
    """gui.clear(id) — clear an element's content."""
    if not args:
        raise RuntimeError("gui.clear() requires an element id")
    _gui_dom_send(interp, {"op": "clear", "id": _to_str(args[0])})
    return True

def gui_replace(args, kwargs, interp):
    """gui.replace(id, html) — replace an element entirely with new HTML."""
    if len(args) < 2:
        raise RuntimeError("gui.replace() requires an element id and HTML content")
    _gui_dom_send(interp, {"op": "replace", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_addClass(args, kwargs, interp):
    """gui.addClass(id, class) — add a CSS class to an element."""
    if len(args) < 2:
        raise RuntimeError("gui.addClass() requires an element id and class name")
    _gui_dom_send(interp, {"op": "addClass", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_removeClass(args, kwargs, interp):
    """gui.removeClass(id, class) — remove a CSS class from an element."""
    if len(args) < 2:
        raise RuntimeError("gui.removeClass() requires an element id and class name")
    _gui_dom_send(interp, {"op": "removeClass", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_toggleClass(args, kwargs, interp):
    """gui.toggleClass(id, class) — toggle a CSS class on an element."""
    if len(args) < 2:
        raise RuntimeError("gui.toggleClass() requires an element id and class name")
    _gui_dom_send(interp, {"op": "toggleClass", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_removeAttr(args, kwargs, interp):
    """gui.removeAttr(id, attr) — remove an attribute from an element."""
    if len(args) < 2:
        raise RuntimeError("gui.removeAttr() requires an element id and attribute name")
    _gui_dom_send(interp, {"op": "removeAttr", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_setVal(args, kwargs, interp):
    """gui.setVal(id, value) — set an input element's value."""
    if len(args) < 2:
        raise RuntimeError("gui.setVal() requires an element id and value")
    _gui_dom_send(interp, {"op": "val", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_focus(args, kwargs, interp):
    """gui.focus(id) — focus an element."""
    if not args:
        raise RuntimeError("gui.focus() requires an element id")
    _gui_dom_send(interp, {"op": "focus", "id": _to_str(args[0])})
    return True

def gui_blur(args, kwargs, interp):
    """gui.blur(id) — remove focus from an element."""
    if not args:
        raise RuntimeError("gui.blur() requires an element id")
    _gui_dom_send(interp, {"op": "blur", "id": _to_str(args[0])})
    return True

def gui_disable(args, kwargs, interp):
    """gui.disable(id) — disable a form element."""
    if not args:
        raise RuntimeError("gui.disable() requires an element id")
    _gui_dom_send(interp, {"op": "disable", "id": _to_str(args[0])})
    return True

def gui_enable(args, kwargs, interp):
    """gui.enable(id) — enable a form element."""
    if not args:
        raise RuntimeError("gui.enable() requires an element id")
    _gui_dom_send(interp, {"op": "enable", "id": _to_str(args[0])})
    return True

def gui_clone(args, kwargs, interp):
    """gui.clone(id, newId) — clone an element and give the clone a new id."""
    if len(args) < 2:
        raise RuntimeError("gui.clone() requires source element id and new id")
    _gui_dom_send(interp, {"op": "clone", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_scroll(args, kwargs, interp):
    """gui.scroll(id, behavior: 'smooth') — scroll element into view."""
    el_id = _to_str(args[0]) if args else ""
    behavior = _to_str(kwargs.get("behavior", "smooth")) if "behavior" in kwargs else "smooth"
    _gui_dom_send(interp, {"op": "scroll", "id": el_id, "value": behavior})
    return True

def gui_scrollTop(args, kwargs, interp):
    """gui.scrollTop(id, pixels) — set scroll position of a scrollable element."""
    if len(args) < 2:
        raise RuntimeError("gui.scrollTop() requires an element id and pixel offset")
    _gui_dom_send(interp, {"op": "scrollTop", "id": _to_str(args[0]), "value": _to_str(args[1])})
    return True

def gui_setTitle(args, kwargs, interp):
    """gui.setTitle(title) — update the browser tab title."""
    if not args:
        raise RuntimeError("gui.setTitle() requires a title string")
    _gui_dom_send(interp, {"op": "html", "id": "__arb_title__", "value": _to_str(args[0])})
    return True

def gui_evalJS(args, kwargs, interp):
    """gui.evalJS(code) — evaluate arbitrary JavaScript in the browser page."""
    if not args:
        raise RuntimeError("gui.evalJS() requires a JavaScript code string")
    code = _to_str(args[0])
    _gui_dom_send(interp, {"op": "eval", "id": "__arb_eval__", "value": code})
    return True

# ── Registration ─────────────────────────────────────────────────────

def register(engine):
    engine.register_extension("gui.open", lambda args, kwargs: gui_open(args, kwargs, engine))
    engine.register_extension("gui.openUrl", lambda args, kwargs: gui_open_url(args, kwargs, engine))
    engine.register_extension("gui.on", lambda args, kwargs: gui_on(args, kwargs, engine))
    engine.register_extension("gui.send", lambda args, kwargs: gui_send(args, kwargs, engine))
    engine.register_extension("gui.close", lambda args, kwargs: gui_close(args, kwargs, engine))
    engine.register_extension("gui.status", lambda args, kwargs: gui_status(args, kwargs, engine))
    engine.register_extension("gui.wait", lambda args, kwargs: gui_wait(args, kwargs, engine))
    engine.register_extension("gui.create", lambda args, kwargs: gui_create(args, kwargs, engine))
    engine.register_extension("gui.add", lambda args, kwargs: gui_add(args, kwargs, engine))
    engine.register_extension("gui.box", lambda args, kwargs: gui_box(args, kwargs, engine))
    engine.register_extension("gui.text", lambda args, kwargs: gui_text(args, kwargs, engine))
    engine.register_extension("gui.button", lambda args, kwargs: gui_button(args, kwargs, engine))
    engine.register_extension("gui.inputField", lambda args, kwargs: gui_input_field(args, kwargs, engine))
    engine.register_extension("gui.image", lambda args, kwargs: gui_image(args, kwargs, engine))
    engine.register_extension("gui.link", lambda args, kwargs: gui_link(args, kwargs, engine))
    engine.register_extension("gui.list", lambda args, kwargs: gui_list(args, kwargs, engine))
    engine.register_extension("gui.style", lambda args, kwargs: gui_style(args, kwargs, engine))
    engine.register_extension("gui.script", lambda args, kwargs: gui_script(args, kwargs, engine))
    engine.register_extension("gui.html", lambda args, kwargs: gui_html(args, kwargs, engine))
    engine.register_extension("gui.show", lambda args, kwargs: gui_show(args, kwargs, engine))
    engine.register_extension("gui.update", lambda args, kwargs: gui_update(args, kwargs, engine))
    engine.register_extension("gui.setHTML", lambda args, kwargs: gui_setHTML(args, kwargs, engine))
    engine.register_extension("gui.setStyle", lambda args, kwargs: gui_setStyle(args, kwargs, engine))
    engine.register_extension("gui.showEl", lambda args, kwargs: gui_showEl(args, kwargs, engine))
    engine.register_extension("gui.hideEl", lambda args, kwargs: gui_hideEl(args, kwargs, engine))
    engine.register_extension("gui.append", lambda args, kwargs: gui_append(args, kwargs, engine))
    engine.register_extension("gui.setAttr", lambda args, kwargs: gui_setAttr(args, kwargs, engine))
    engine.register_extension("gui.remove", lambda args, kwargs: gui_remove(args, kwargs, engine))
    engine.register_extension("gui.prepend", lambda args, kwargs: gui_prepend(args, kwargs, engine))
    engine.register_extension("gui.insertBefore", lambda args, kwargs: gui_insertBefore(args, kwargs, engine))
    engine.register_extension("gui.insertAfter", lambda args, kwargs: gui_insertAfter(args, kwargs, engine))
    engine.register_extension("gui.clear", lambda args, kwargs: gui_clear(args, kwargs, engine))
    engine.register_extension("gui.replace", lambda args, kwargs: gui_replace(args, kwargs, engine))
    engine.register_extension("gui.addClass", lambda args, kwargs: gui_addClass(args, kwargs, engine))
    engine.register_extension("gui.removeClass", lambda args, kwargs: gui_removeClass(args, kwargs, engine))
    engine.register_extension("gui.toggleClass", lambda args, kwargs: gui_toggleClass(args, kwargs, engine))
    engine.register_extension("gui.removeAttr", lambda args, kwargs: gui_removeAttr(args, kwargs, engine))
    engine.register_extension("gui.setVal", lambda args, kwargs: gui_setVal(args, kwargs, engine))
    engine.register_extension("gui.focus", lambda args, kwargs: gui_focus(args, kwargs, engine))
    engine.register_extension("gui.blur", lambda args, kwargs: gui_blur(args, kwargs, engine))
    engine.register_extension("gui.disable", lambda args, kwargs: gui_disable(args, kwargs, engine))
    engine.register_extension("gui.enable", lambda args, kwargs: gui_enable(args, kwargs, engine))
    engine.register_extension("gui.clone", lambda args, kwargs: gui_clone(args, kwargs, engine))
    engine.register_extension("gui.scroll", lambda args, kwargs: gui_scroll(args, kwargs, engine))
    engine.register_extension("gui.scrollTop", lambda args, kwargs: gui_scrollTop(args, kwargs, engine))
    engine.register_extension("gui.setTitle", lambda args, kwargs: gui_setTitle(args, kwargs, engine))
    engine.register_extension("gui.evalJS", lambda args, kwargs: gui_evalJS(args, kwargs, engine))
