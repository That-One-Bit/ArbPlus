# ArbPlus GUI Extension — Desktop Dialogs (Python/tkinter)
# @arbplus-meta name="ext_gui"
# @arbplus-meta version="2.1"
# @arbplus-meta author="ArbPlus"
# @arbplus-meta description="Desktop GUI dialogs via tkinter: message boxes, inputs, file pickers, color pickers, forms"
# @arbplus-meta dependencies="tkinter"
# @arbplus-meta languages="python"
#
# Usage (load by name, like Python's built-in modules):
#   loadExt("ext_gui", "python");
#   gui.dialog("Hello!");               # message box
#   gui.input("Enter name:", "World");   # input dialog
#   gui.yesNo("Continue?");              # yes/no dialog
#   gui.fileOpen();                      # file picker
#   gui.fileSave();                      # save dialog
#   gui.colorPicker();                   # color picker
#   gui.password("Enter password:");     # masked input
#   gui.form("User Info", "Name:|Email:|Age:0");  # multi-field form
#   gui.menu("Choose:", "Option A|Option B|Option C");  # dropdown menu
#   gui.notify("Title", "Message");       # notification
#
# Falls back gracefully if tkinter is not available or no display is found.


_TK_AVAILABLE = True
_TK_ERROR = ""

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog
    _TK_AVAILABLE = True
except ImportError as e:
    _TK_AVAILABLE = False
    _TK_ERROR = str(e)

_root = None

def _get_root():
    global _root, _TK_AVAILABLE, _TK_ERROR
    if not _TK_AVAILABLE:
        return None
    try:
        if _root is None or not _root.winfo_exists():
            _root = tk.Tk()
            _root.withdraw()
            _root.attributes('-topmost', True)
        return _root
    except Exception as e:
        _TK_AVAILABLE = False
        _TK_ERROR = str(e)
        return None

def _to_str(val):
    if val is None: return ""
    if hasattr(val, 'val'): return str(val.val)
    if hasattr(val, 'py'): return str(val.py())
    return str(val)

def _tk_fail(msg=""):
    return f"Error: tkinter not available — {_TK_ERROR}" if not msg else f"Error: {msg}"

def dialog(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        message = _to_str(args[0]) if args else ""
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "ArbPlus"
        root.update()
        messagebox.showinfo(title, str(message))
        return True
    except Exception as e:
        return _tk_fail(str(e))

def input_dialog(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        prompt = _to_str(args[0]) if args else "Enter value:"
        default = _to_str(args[1]) if len(args) > 1 else ""
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "ArbPlus Input"
        root.update()
        result = simpledialog.askstring(title, str(prompt), initialvalue=str(default))
        return result if result is not None else None
    except Exception as e:
        return _tk_fail(str(e))

def yes_no(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        prompt = _to_str(args[0]) if args else "Yes or No?"
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "ArbPlus"
        root.update()
        return messagebox.askyesno(title, str(prompt))
    except Exception as e:
        return _tk_fail(str(e))

def file_open(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "Open File"
        root.update()
        path = filedialog.askopenfilename(title=title)
        return path if path else None
    except Exception as e:
        return _tk_fail(str(e))

def file_save(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "Save File"
        root.update()
        path = filedialog.asksaveasfilename(title=title)
        return path if path else None
    except Exception as e:
        return _tk_fail(str(e))

def color_picker(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        root.update()
        from tkinter import colorchooser
        result = colorchooser.askcolor(title="Pick a Color")
        return result[1] if result and result[1] else None
    except Exception as e:
        return _tk_fail(str(e))

def password(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        prompt = _to_str(args[0]) if args else "Enter password:"
        title = _to_str(kwargs.get("title")) if "title" in kwargs else "Password"
        root.update()
        result = simpledialog.askpassword(title, str(prompt), show="*")
        return result if result is not None else None
    except Exception as e:
        return _tk_fail(str(e))

def notify(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        title = _to_str(args[0]) if args else "Notification"
        message = _to_str(args[1]) if len(args) > 1 else ""
        root.update()
        messagebox.showinfo(str(title), str(message))
        return True
    except Exception as e:
        return _tk_fail(str(e))

def menu(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        title = _to_str(args[0]) if args else "Select:"
        items_str = _to_str(args[1]) if len(args) > 1 else ""
        items = items_str.split("|") if items_str else []
        if not items: return None
        root.update()
        selected = {"value": None}
        win = tk.Toplevel(); win.title(str(title)); win.geometry("300x250")
        win.transient(root); win.grab_set()
        tk.Label(win, text=str(title), font=("", 12, "bold"), pady=10).pack()
        listbox = tk.Listbox(win, height=10, width=35)
        listbox.pack(pady=10, padx=20, expand=True, fill="both")
        for item in items: listbox.insert(tk.END, item.strip())
        def on_select():
            sel = listbox.curselection()
            if sel: selected["value"] = listbox.get(sel[0])
            win.destroy()
        listbox.bind("<Double-Button-1>", lambda e: on_select())
        tk.Button(win, text="OK", command=on_select).pack(pady=5)
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.wait_window()
        return selected["value"] if selected["value"] else None
    except Exception as e:
        return _tk_fail(str(e))

def form(args, kwargs):
    if not _TK_AVAILABLE: return _tk_fail()
    root = _get_root()
    if root is None: return _tk_fail("no display available")
    try:
        title = _to_str(args[0]) if args else "Form"
        fields_str = _to_str(args[1]) if len(args) > 1 else ""
        fields = []
        if fields_str:
            for part in fields_str.split("|"):
                if ":" in part:
                    name, default = part.split(":", 1)
                    fields.append((name.strip(), default.strip()))
                else:
                    fields.append((part.strip(), ""))
        if not fields: return None
        root.update()
        win = tk.Toplevel(); win.title(str(title))
        win.geometry("350x" + str(80 + len(fields) * 30))
        win.transient(root); win.grab_set()
        tk.Label(win, text=str(title), font=("", 12, "bold"), pady=10).pack()
        entries = {}
        for name, default in fields:
            frame = tk.Frame(win); frame.pack(pady=3, padx=20, fill="x")
            tk.Label(frame, text=name, width=12, anchor="w").pack(side="left")
            entry = tk.Entry(frame, width=25); entry.insert(0, default)
            entry.pack(side="left", padx=5, expand=True, fill="x")
            entries[name] = entry
        result = {"values": {}}
        def on_submit():
            for name, entry in entries.items(): result["values"][name] = entry.get()
            win.destroy()
        def on_cancel(): win.destroy()
        btn_frame = tk.Frame(win); btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="OK", command=on_submit, width=10).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=on_cancel, width=10).pack(side="left", padx=10)
        win.protocol("WM_DELETE_WINDOW", on_cancel)
        win.wait_window()
        return result["values"] if result["values"] else None
    except Exception as e:
        return _tk_fail(str(e))

def register(engine):
    """Registration entry point — called by loadExt()."""
    engine.register_extension("gui.dialog", dialog)
    engine.register_extension("gui.input", input_dialog)
    engine.register_extension("gui.yesNo", yes_no)
    engine.register_extension("gui.fileOpen", file_open)
    engine.register_extension("gui.fileSave", file_save)
    engine.register_extension("gui.colorPicker", color_picker)
    engine.register_extension("gui.password", password)
    engine.register_extension("gui.notify", notify)
    engine.register_extension("gui.menu", menu)
    engine.register_extension("gui.form", form)
