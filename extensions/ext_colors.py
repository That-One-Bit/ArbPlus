# ArbPlus Extension: Colored Output for Inline Language Blocks
# Addition 32 — provides ArbPlus-consistent colored output for c{}/py{}/cmd{}/ps{} blocks
#
# Usage from ArbPlus scripts:
#   loadExt("extensions/ext_colors.py", "python");
#   let colored = ext_colors.color_text("Hello", "blue", "", "bright");
#   print(colored);
#   ext_colors.color_print("Red text", "red", "", "normal");
#
# Usage from py{} blocks (direct import):
#   py{
#       import sys
#       sys.path.insert(0, "extensions")
#       from ext_colors import color_text, color_print
#       color_print("Hello from Python", "green", "", "bright")
#   }

import math

NAMED_COLORS = {
    "black": (0, 0, 0), "red": (205, 0, 0), "green": (0, 205, 0), "yellow": (205, 205, 0),
    "blue": (0, 0, 238), "magenta": (205, 0, 205), "cyan": (0, 205, 205), "white": (229, 229, 229),
    "bright_black": (127, 127, 127), "bright_red": (255, 85, 85), "bright_green": (85, 255, 85),
    "bright_yellow": (255, 255, 85), "bright_blue": (85, 85, 255), "bright_magenta": (255, 85, 255),
    "bright_cyan": (85, 255, 255), "bright_white": (255, 255, 255),
}

BRIGHT_MAP = {"dim": "2", "normal": "22", "bright": "1"}

BASIC_NAMED_FG = {
    "black": "30", "red": "31", "green": "32", "yellow": "33",
    "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
    "bright_black": "90", "bright_red": "91", "bright_green": "92",
    "bright_yellow": "93", "bright_blue": "94", "bright_magenta": "95",
    "bright_cyan": "96", "bright_white": "97",
}

def _oklch_to_rgb(l, c, h):
    h_rad = math.radians(h)
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)
    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b
    l3, m3, s3 = l_**3, m_**3, s_**3
    r_lin = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    g_lin = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    b_lin = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3
    def to_srgb(v):
        if v <= 0: return 0
        if v >= 1: return 255
        return int(round((1.055 * (v ** (1/2.4)) - 0.055) * 255))
    return (to_srgb(r_lin), to_srgb(g_lin), to_srgb(b_lin))

def _parse_color(name):
    if not name or not isinstance(name, str):
        return None
    if name in NAMED_COLORS:
        return NAMED_COLORS[name]
    if name.startswith("#") and len(name) == 7:
        try:
            return (int(name[1:3], 16), int(name[3:5], 16), int(name[5:7], 16))
        except ValueError:
            return None
    if name.startswith("rgb(") and name.endswith(")"):
        try:
            parts = name[4:-1].split(",")
            return (int(parts[0].strip()), int(parts[1].strip()), int(parts[2].strip()))
        except (ValueError, IndexError):
            return None
    if name.startswith("oklch(") and name.endswith(")"):
        try:
            parts = name[6:-1].split(",")
            return _oklch_to_rgb(float(parts[0].strip()), float(parts[1].strip()), float(parts[2].strip()))
        except (ValueError, IndexError):
            return None
    return None

def _to_ansi(name, is_bg=False):
    if not name:
        return ""
    if name in BASIC_NAMED_FG:
        code = BASIC_NAMED_FG[name]
        return str(int(code) + 10) if is_bg else code
    rgb = _parse_color(name)
    if rgb:
        r, g, b = rgb
        return f"48;2;{r};{g};{b}" if is_bg else f"38;2;{r};{g};{b}"
    return ""

def color_text(text, fg="", bg="", b=""):
    """Return colored ANSI text consistent with ArbPlus's colorize()."""
    codes = []
    if b and b in BRIGHT_MAP:
        codes.append(BRIGHT_MAP[b])
    if fg:
        ansi = _to_ansi(fg, is_bg=False)
        if ansi: codes.append(ansi)
    if bg:
        ansi = _to_ansi(bg, is_bg=True)
        if ansi: codes.append(ansi)
    if codes:
        return f"\033[{';'.join(codes)}m{text}\033[0m"
    return text

def color_print(text, fg="", bg="", b=""):
    """Print colored text consistent with ArbPlus's print()."""
    print(color_text(text, fg, bg, b))

# --- ArbPlus extension ABI ---

def _ext_color_text(args, kwargs):
    """ArbPlus-callable wrapper for color_text."""
    text = args[0].py() if args else ""
    fg = args[1].py() if len(args) > 1 else kwargs.get("fg", "")
    bg = args[2].py() if len(args) > 2 else kwargs.get("bg", "")
    b = args[3].py() if len(args) > 3 else kwargs.get("b", "")
    if isinstance(fg, str) and fg == "" and "fg" in kwargs: fg = kwargs["fg"]
    if isinstance(bg, str) and bg == "" and "bg" in kwargs: bg = kwargs["bg"]
    if isinstance(b, str) and b == "" and "b" in kwargs: b = kwargs["b"]
    return color_text(str(text), str(fg) if fg else "", str(bg) if bg else "", str(b) if b else "")

def _ext_color_print(args, kwargs):
    """ArbPlus-callable wrapper for color_print."""
    text = args[0].py() if args else ""
    fg = args[1].py() if len(args) > 1 else kwargs.get("fg", "")
    bg = args[2].py() if len(args) > 2 else kwargs.get("bg", "")
    b = args[3].py() if len(args) > 3 else kwargs.get("b", "")
    if isinstance(fg, str) and fg == "" and "fg" in kwargs: fg = kwargs["fg"]
    if isinstance(bg, str) and bg == "" and "bg" in kwargs: bg = kwargs["bg"]
    if isinstance(b, str) and b == "" and "b" in kwargs: b = kwargs["b"]
    color_print(str(text), str(fg) if fg else "", str(bg) if bg else "", str(b) if b else "")
    return None

def register(engine):
    """Registration entry point — called by loadExt()."""
    engine.register_extension("ext_colors.color_text", _ext_color_text)
    engine.register_extension("ext_colors.color_print", _ext_color_print)

# Extension metadata
__meta__ = {
    "name": "ext_colors",
    "version": "1.0",
    "author": "ArbPlus",
    "description": "Colored output extension for inline language blocks",
    "language": "python",
    "functions": ["color_text", "color_print"],
    "hooks": {},
}
