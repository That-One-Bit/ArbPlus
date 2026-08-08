# ArbPlus Tkinter Extension (Python)
# @arbplus-meta name="Tkinter"
# @arbplus-meta version="0.2"
# @arbplus-meta author="ThatOneBit"
# @arbplus-meta description="Python based extension bringing native Tkinter functions to ArbPlus."
# @arbplus-meta dependencies="tkinter, customtkinter"
# @arbplus-meta languages="python"

_TK_AVAILABLE = True
_TK_ERROR = ""
_CTK_AVAILABLE = True
_CTK_ERROR = ""

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, simpledialog, colorchooser
    _TK_AVAILABLE = True
except ImportError as e:
    _TK_AVAILABLE = False
    _TK_ERROR = str(e)
try:
    import customtkinter as ctk
    _CTK_AVAILABLE = True
except ImportError as e:
    _CTK_AVAILABLE = False
    _CTK_ERROR = str(e)

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

def _parse_filetypes(raw_val):
    """Parses the filetypes provided by the Arb script, as ArbPlus doesn't handle tuples very well."""
    default_fallback = [("All Files", "*.*")]
    if not raw_val:
        return default_fallback

    if hasattr(raw_val, 'py'):
        raw_val = raw_val.py()
    elif hasattr(raw_val, 'val'):
        raw_val = raw_val.val

    if isinstance(raw_val, str):
        raw_val = raw_val.strip()
        if (raw_val.startswith('[') and raw_val.endswith(']')) or (raw_val.startswith('(') and raw_val.endswith(')')):
            try:
                raw_val = ast.literal_eval(raw_val)
            except Exception:
                return default_fallback
        else:
            return default_fallback

    try:
        cleaned_list = []
        for item in raw_val:
            if hasattr(item, 'py'): 
                item = item.py()
            elif hasattr(item, 'val'): 
                item = item.val

            if isinstance(item, (list, tuple)) and len(item) >= 2:
                label = _to_str(item[0])
                extension = _to_str(item[1])
                cleaned_list.append((label, extension))
        
        return cleaned_list if cleaned_list else default_fallback
    except Exception:
        return default_fallback

def _def_icon(root):
    try:
        cur = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(cur, "icon.png")
        
        if os.path.exists(icon_path):
            icon = tk.PhotoImage(file=icon_path)
            root.wm_iconphoto(True, icon)
    except Exception:
        pass

def _tk_fail(msg=""):
    return f"Error: tkinter not available — {_TK_ERROR}" if not msg else f"Error: {msg}"


class MessageBox:
    """The class containing every Tkinter MessageBox function. Included since v0.1"""

    @staticmethod
    def showWarning(args, kwargs):
        """Displays a warning box."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Warning"
            message = _to_str(args[1]) if len(args) > 1 else "Default warning message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "warning"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            messagebox.showwarning(str(title), str(message), icon=icon, detail=detail, parent=parent)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def showError(args, kwargs):
        """Displays error message."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Error"
            message = _to_str(args[1]) if len(args) > 1 else "Default error message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "error"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            messagebox.showerror(str(title), str(message), icon=icon, detail=detail, parent=parent)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def showInfo(args, kwargs):
        """Creates and displays an information message box with the specified title and message."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Information"
            message = _to_str(args[1]) if len(args) > 1 else "Default information."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "info"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            messagebox.showinfo(str(title), str(message), icon=icon, detail=detail, parent=parent)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askyesno(args, kwargs):
        """Ask the user a question. Returns TRUE or FALSE."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            message = _to_str(args[1]) if len(args) > 1 else "Default message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "question"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            highlight = _to_str(kwargs.get("highlight")) if "highlight" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return messagebox.askyesno(str(title), str(message), default=highlight, icon=icon, detail=detail, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askquestion(args, kwargs):
        """Ask the user a question. Returns string of YES or NO."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            message = _to_str(args[1]) if len(args) > 1 else "Default message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "question"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            highlight = _to_str(kwargs.get("highlight")) if "highlight" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return messagebox.askquestion(str(title), str(message), default=highlight, icon=icon, detail=detail, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askokcancel(args, kwargs):
        """Ask the user a question, and give ok or cancel options. Returns TRUE or FALSE."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            message = _to_str(args[1]) if len(args) > 1 else "Default message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "question"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            highlight = _to_str(kwargs.get("highlight")) if "highlight" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return messagebox.askokcancel(str(title), str(message), default=highlight, icon=icon, detail=detail, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askretrycancel(args, kwargs):
        """Ask the user a question, and give retry or cancel options. Returns TRUE or FALSE."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            message = _to_str(args[1]) if len(args) > 1 else "Default message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "question"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            highlight = _to_str(kwargs.get("highlight")) if "highlight" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return messagebox.askretrycancel(str(title), str(message), default=highlight, icon=icon, detail=detail, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askyesnocancel(args, kwargs):
        """Ask the user a question, and give yes, no, or cancel options. Returns TRUE, FALSE, or NONE."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            message = _to_str(args[1]) if len(args) > 1 else "Default message."
            icon = _to_str(kwargs.get("icon")) if "icon" in kwargs else "question"
            detail = _to_str(kwargs.get("detail")) if "detail" in kwargs else None
            highlight = _to_str(kwargs.get("highlight")) if "highlight" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return messagebox.askyesnocancel(str(title), str(message), default=highlight, icon=icon, detail=detail, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))
class FileDialog:
    """This class contains the filedialog module functions. Included since v0.1"""

    @staticmethod
    def askopenfilename(args, kwargs):
        """Ask the user to supply a file, returns file path."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Open File"
            initialdir = _to_str(args[1]) if len(args) > 1 else "./"
            types = _parse_filetypes(kwargs.get("types")) if "types" in kwargs else [("All Files", "*.*")]
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return filedialog.askopenfilename(title=str(title), initialdir=initialdir, filetypes=types, parent=parent)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askopenfilenames(args, kwargs):
        """Ask the user to supply multiple files, returns file path."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Open Files"
            initialdir = _to_str(args[1]) if len(args) > 1 else "./"
            types = _parse_filetypes(kwargs.get("types")) if "types" in kwargs else [("All Files", "*.*")]
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return list(filedialog.askopenfilenames(title=str(title), initialdir=initialdir, filetypes=types, parent=parent))
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def asksaveasfilename(args, kwargs):
        """Ask the user to save file. Returns TRUE or FALSE."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Open Files"
            initialdir = _to_str(args[1]) if len(args) > 1 else "./"
            types = _parse_filetypes(kwargs.get("types")) if "types" in kwargs else [("All Files", "*.*")]
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            default = _to_str(kwargs.get("default")) if "default" in kwargs else None
            root.update()
            return filedialog.asksaveasfilename(title=str(title), initialdir=initialdir, filetypes=types, parent=parent, defaultextension=default)
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askdirectory(args, kwargs):
        """Ask the user to supply a directory, returns directory path."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Open Files"
            initialdir = _to_str(args[1]) if len(args) > 1 else "./"
            mexist = _to_str(kwargs.get("mexist")) if "mexist" in kwargs else TRUE
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return list(filedialog.askdirectory(title=str(title), initialdir=initialdir, mustexist=mexist, parent=parent))
        except Exception as e:
            return _tk_fail(str(e))
class SimpleDialog:
    """This class contains every simpledialog function. Included since v0.1"""

    @staticmethod
    def askstring(args, kwargs):
        """Ask the user to supply a string, returns the string."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Supply String"
            message = _to_str(args[1]) if len(args) > 1 else "Input"
            initial = _to_str(kwargs.get("initial")) if "initial" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            check = simpledialog.askstring(str(title), str(message), initialvalue=initial, parent=parent)
            if check == None:
                return "ced"
            else:
                return check
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askinteger(args, kwargs):
        """Ask the user to supply an integer, returns the integer."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Supply Integer"
            message = _to_str(args[1]) if len(args) > 1 else "Input"
            initial = _to_str(kwargs.get("initial")) if "initial" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            minimum = _to_str(kwargs.get("_min")) if "_min" in kwargs else None
            maximum = _to_str(kwargs.get("_max")) if "_max" in kwargs else None
            root.update()
            check = simpledialog.askinteger(str(title), str(message), minvalue=minimum, maxvalue=maximum, initialvalue=initial, parent=parent)
            if check == None:
                return "ced"
            else:
                return check
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def askfloat(args, kwargs):
        """Ask the user to supply a float, returns the float."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Supply Float"
            message = _to_str(args[1]) if len(args) > 1 else "Input"
            initial = _to_str(kwargs.get("initial")) if "initial" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            minimum = _to_str(kwargs.get("_min")) if "_min" in kwargs else None
            maximum = _to_str(kwargs.get("_max")) if "_max" in kwargs else None
            root.update()
            check = simpledialog.askfloat(str(title), str(message), minvalue=minimum, maxvalue=maximum, initialvalue=initial, parent=parent)
            if check == None:
                return "ced"
            else:
                return check
        except Exception as e:
            return _tk_fail(str(e))
class ColorChooser:
    """This class contains every simpledialog function. Included since v0.1"""

    @staticmethod
    def color(args, kwargs):
        """Ask the user to choose a color, returns the color in HEX."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Supply String"
            initial = _to_str(kwargs.get("initial")) if "initial" in kwargs else None
            parent = _to_str(kwargs.get("parent")) if "parent" in kwargs else root
            root.update()
            return colorchooser.askcolor(title=str(title), color=initial, parent=parent)[1]
        except Exception as e:
            return _tk_fail(str(e))
class TkinterBase:
    """Base class for Tkinter extensions. Included since v0.2."""

    @staticmethod
    def rootTitle(args, kwargs):
        """Set the window title."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            title = _to_str(args[0]) if args else "Default Title"
            root.update()
            root.title(title)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def rootGeometry(args, kwargs):
        """Set the window geometry."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            x = _to_str(args[0]) if args else "300"
            y = _to_str(args[1]) if len(args) > 1 else "250"

            geo = f"{x}x{y}"

            if len(args) > 3:
                ox = _to_str(args[2])
                oy = _to_str(args[3])
                geo += f"+{ox}+{oy}"
            
            root.deiconify()
            root.update()
            root.geometry(geo)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def rootResizable(args, kwargs):
        """Is the window resizable?"""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            rx = _to_str(args[0]) if args else True
            ry = _to_str(args[1]) if len(args) > 1 else True
            root.update()
            root.resizable(rx, ry)
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def rootAttributes(args, kwargs):
        """Defines the root attributes."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            if "alpha" in kwargs:
                alpha_val = float(_to_str(kwargs.get("alpha")))
                root.attributes("-alpha", alpha_val)
            if "topmost" in kwargs:
                topmost_val = float(_to_str(kwargs.get("topmost")))
                root.attributes("-topmost", topmost_val)
            root.update()
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def rootState(args, kwargs):
        """State of the window, minimized, display, or hidden."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            state = _to_str(args[0]) if args else "normal"
            root.update()
            root.state(state)
            return state
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def rootDestroy(args, kwargs):
        """Destroys the window."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            root.destroy()
            return True
        except Exception as e:
            return _tk_fail(str(e))

    @staticmethod
    def mainLoop(args, kwargs):
        """Run the mainloop for TK."""
        if not _TK_AVAILABLE: return _tk_fail()
        root = _get_root()
        if root is None: return _tk_fail("Display root not found.")
        try:
            root.mainloop()
            return True
        except Exception as e:
            return _tk_fail(str(e))

def register(engine):
    """Registration entry point — called by loadExt()."""
    engine.register_extension("tk.show_info", MessageBox.showInfo)
    engine.register_extension("tk.show_warn", MessageBox.showWarning)
    engine.register_extension("tk.show_error", MessageBox.showError)
    engine.register_extension("tk.ask_yn", MessageBox.askyesno)
    engine.register_extension("tk.ask_qt", MessageBox.askquestion)
    engine.register_extension("tk.ask_okc", MessageBox.askokcancel)
    engine.register_extension("tk.ask_ryc", MessageBox.askretrycancel)
    engine.register_extension("tk.ask_ync", MessageBox.askyesnocancel)
    engine.register_extension("tk.file_open", FileDialog.askopenfilename)
    engine.register_extension("tk.files_open", FileDialog.askopenfilenames)
    engine.register_extension("tk.file_save", FileDialog.asksaveasfilename)
    engine.register_extension("tk.dir_open", FileDialog.askdirectory)
    engine.register_extension("tk.in_str", SimpleDialog.askstring)
    engine.register_extension("tk.in_int", SimpleDialog.askinteger)
    engine.register_extension("tk.in_flt", SimpleDialog.askfloat)
    engine.register_extension("tk.color", ColorChooser.color)
    engine.register_extension("tk.app_title", TkinterBase.rootTitle)
    engine.register_extension("tk.app_geo", TkinterBase.rootGeometry)
    engine.register_extension("tk.app_resize", TkinterBase.rootResizable)
    engine.register_extension("tk.app_attrs", TkinterBase.rootAttributes)
    engine.register_extension("tk.app_kill", TkinterBase.rootDestroy)
    engine.register_extension("tk.mainloop", TkinterBase.mainLoop)
