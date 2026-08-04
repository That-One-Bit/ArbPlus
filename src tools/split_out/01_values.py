## 01 -- 01_values.py -- ArbValue hierarchy + coercion/color helpers
class ArbValue:
    """Base class for all ArbPlus typed values."""
    def __init__(self, val, type_name):
        self.val = val
        self.type_name = type_name
    def __repr__(self):
        return f"ArbValue({self.type_name}, {self.val!r})"
    def py(self):
        return self.val

class ArbInt(ArbValue):
    def __init__(self, val):
        super().__init__(int(val), "int")

class ArbFloat(ArbValue):
    def __init__(self, val):
        super().__init__(float(val), "float")

class ArbFile(ArbValue):
    """A file-reference variable type."""
    def __init__(self, path):
        super().__init__(path, "file")
        self.path = path
        self.exists = os.path.exists(path) if path else False
    def py(self):
        return self.path
    def __repr__(self):
        return f"ArbFile({self.path!r}, exists={self.exists})"

class ArbString(ArbValue):
    def __init__(self, val):
        super().__init__(str(val), "string")

class ArbBool(ArbValue):
    def __init__(self, val):
        super().__init__(bool(val), "boolean")

class ArbNull(ArbValue):
    """Null/void value for bare return() with no argument."""
    def __init__(self):
        super().__init__(None, "null")
    def py(self):
        return None
    def __repr__(self):
        return "ArbNull"
    def __str__(self):
        return "null"

class ArbArray(ArbValue):
    """An array data type for storing multiple strings."""
    def __init__(self, elements, elem_type=None):
        super().__init__(elements, "array")
        self.elem_type = elem_type or (elements[0].type_name if elements else "int")
        self._size = len(elements)

class ArbList(ArbValue):
    def __init__(self, elements):
        super().__init__(elements, "list")

class ArbMap(ArbValue):
    """A map data rype using keys and values, inserts data after previous."""
    def __init__(self, pairs=None):
        # Store as list of (key, value) tuples to preserve insertion order
        super().__init__(pairs or [], "map")
    def get(self, key):
        for k, v in self.val:
            if k == key:
                return v
        return None
    def set(self, key, value):
        for i, (k, v) in enumerate(self.val):
            if k == key:
                self.val[i] = (key, value)
                return
        self.val.append((key, value))
    def has(self, key):
        return any(k == key for k, v in self.val)
    def keys(self):
        return [k for k, v in self.val]
    def values(self):
        return [v for k, v in self.val]
    def __len__(self):
        return len(self.val)


class ArbColoredString(ArbValue):
    """A colored string segment - carries text + ANSI styling info."""
    def __init__(self, text, fg=None, bg=None, brightness="normal"):
        super().__init__(text, "colored_string")
        self.fg = fg
        self.bg = bg
        self.brightness = brightness
    def get_ansi_codes(self, default_colors=None):
        codes = []
        # Brightness
        if self.brightness == "dim":
            codes.append("2")
        elif self.brightness == "bright":
            codes.append("1")
        elif self.brightness == "normal":
            codes.append("22")
        # Foreground
        fg = self.fg or (default_colors.get("fg") if default_colors else None)
        if fg:
            codes.append(color_name_to_ansi(fg, is_bg=False))
        # Background
        bg = self.bg or (default_colors.get("bg") if default_colors else None)
        if bg:
            codes.append(color_name_to_ansi(bg, is_bg=True))
        return codes
    def to_ansi_string(self, default_colors=None):
        codes = self.get_ansi_codes(default_colors)
        if codes:
            return f"\033[{';'.join(codes)}m{self.val}\033[0m"
        return self.val



# --- A new data type storing info in HEX containers, useful for reading binary/unspecified files ---
ARB_TAG_MAP = {
    "str":   0x01,
    "int":   0x02,
    "float": 0x03,
    "bool":  0x04,
    "image": 0x10,
    "raw":   0xFF,
}
ARB_TAG_REVERSE = {v: k for k, v in ARB_TAG_MAP.items()}

class ArbArb(ArbValue):
    """arb - tagged container storing values as hex-encoded bytes."""
    def __init__(self, elements=None):
        super().__init__(elements or [], "arb")

    def add(self, tag_name, value):
        tag_byte = ARB_TAG_MAP.get(tag_name, 0xFF)
        if tag_name == "str":
            hex_bytes = str(value).encode('utf-8').hex()
            decoded = str(value)
        elif tag_name == "int":
            hex_bytes = struct.pack('>q', int(value)).hex()
            decoded = int(value)
        elif tag_name == "float":
            hex_bytes = struct.pack('>d', float(value)).hex()
            decoded = float(value)
        elif tag_name == "bool":
            hex_bytes = (b'\x01' if value else b'\x00').hex()
            decoded = bool(value)
        elif tag_name == "image":
            if isinstance(value, str):
                hex_bytes = value.encode('utf-8').hex()
                decoded = value
            else:
                hex_bytes = base64.b64encode(value).hex()
                decoded = base64.b64encode(value).decode()
        elif tag_name == "raw":
            if isinstance(value, bytes):
                hex_bytes = value.hex()
                decoded = value
            else:
                hex_bytes = str(value).encode('utf-8').hex()
                decoded = value
        else:
            hex_bytes = str(value).encode('utf-8').hex()
            decoded = value
        self.val.append((tag_name, tag_byte, hex_bytes, decoded))

    def get_decoded(self, index):
        if index < 0 or index >= len(self.val):
            raise ArbError(f"arb index {index} out of bounds (len={len(self.val)})")
        return self.val[index][3]

    def get_tag(self, index):
        return self.val[index][0]

    def __len__(self):
        return len(self.val)

def to_arb_value(val):
    if isinstance(val, ArbValue):
        return val
    if isinstance(val, bool):
        return ArbBool(val)
    if isinstance(val, int):
        return ArbInt(val)
    if isinstance(val, float):
        return ArbFloat(val)
    if isinstance(val, str):
        return ArbString(val)
    if isinstance(val, list):
        return ArbList(val)
    if isinstance(val, dict):
        return ArbMap([(k, to_arb_value(v)) for k, v in val.items()])
    return ArbString(str(val))

def arb_truthy(val):
    if isinstance(val, ArbValue):
        if val.type_name == "boolean":
            return bool(val.val)
        if val.type_name == "int":
            return val.val != 0
        if val.type_name == "float":
            return val.val != 0.0
        if val.type_name in ("string", "colored_string"):
            return len(val.val) > 0
        if val.type_name in ("array", "list", "arb", "map"):
            return len(val.val) > 0
        return bool(val.val)
    return bool(val)

def arb_to_string(val):
    if isinstance(val, ArbValue):
        if val.type_name == "boolean":
            return "true" if val.val else "false"
        if val.type_name == "string":
            return val.val
        if val.type_name == "colored_string":
            # Preserve ANSI codes so colors survive concatenation and interpolation
            return val.to_ansi_string()
        if val.type_name in ("array", "list"):
            return "[" + ", ".join(arb_to_string(e) for e in val.val) + "]"
        if val.type_name == "map":
            return "{" + ", ".join(f'"{k}": {arb_to_string(v)}' for k, v in val.val) + "}"
        if val.type_name == "arb":
            parts = []
            for tag_name, tag_byte, hex_bytes, decoded in val.val:
                parts.append(f"0x{tag_byte:02X}({decoded})")
            return "arb{ " + ", ".join(parts) + " }"
        if val.type_name == "null":
            return "null"
        if val.type_name == "float":
            return str(val.val)
        if val.type_name == "file":
            return val.py()
        return str(val.val)
    if isinstance(val, bool):
        return "true" if val else "false"
    if val is None:
        return "null"
    return str(val)

def arb_coerce(val, target_type):
    if isinstance(val, ArbValue):
        py = val.py()
    else:
        py = val
    if target_type == "int":
        return ArbInt(int(py))
    if target_type == "float":
        return ArbFloat(float(py))
    if target_type == "string":
        return ArbString(arb_to_string(val))
    if target_type == "boolean":
        return ArbBool(arb_truthy(val))
    if target_type == "list":
        if isinstance(val, ArbList):
            return val
        if isinstance(val, ArbMap):
            return ArbList(val.values())
        if isinstance(py, list):
            return ArbList([to_arb_value(v) for v in py])
        return ArbList([val])
    if target_type == "map":
        if isinstance(val, ArbMap):
            return val
        if isinstance(py, dict):
            return ArbMap([(k, to_arb_value(v)) for k, v in py.items()])
        raise ArbPlusError(f"Cannot coerce to map: value is not a map/dict")
    if target_type == "arb":
        if isinstance(val, ArbArb):
            return val
        if isinstance(py, list):
            arb = ArbArb()
            for item in py:
                if isinstance(item, ArbValue):
                    tname = item.type_name
                    arb.add(tname if tname in ARB_TAG_MAP else "raw", item.py())
                else:
                    arb.add("raw", item)
            return arb
        return val
    if target_type == "null":
        return ArbNull()
    return val

def _oklch_to_rgb(l, c, h):
    """Convert OKLCH to RGB. Returns (r, g, b) as 0-255 ints."""
    import math
    h_rad = math.radians(h)
    a = c * math.cos(h_rad)
    b = c * math.sin(h_rad)
    l_ = l + 0.3963377774 * a + 0.2158037573 * b
    m_ = l - 0.1055613458 * a - 0.0638541728 * b
    s_ = l - 0.0894841775 * a - 1.2914855480 * b
    l_cubed = l_ ** 3
    m_cubed = m_ ** 3
    s_cubed = s_ ** 3
    r_lin = 4.0767416621 * l_cubed - 3.3077115913 * m_cubed + 0.2309699292 * s_cubed
    g_lin = -1.2684380046 * l_cubed + 2.6097574011 * m_cubed - 0.3413193965 * s_cubed
    b_lin = -0.0041960863 * l_cubed - 0.7034186147 * m_cubed + 1.7076147010 * s_cubed
    def linear_to_srgb(v):
        if v <= 0: return 0
        if v >= 1: return 255
        return int(round((1.055 * (v ** (1/2.4)) - 0.055) * 255))
    return (linear_to_srgb(r_lin), linear_to_srgb(g_lin), linear_to_srgb(b_lin))

def _parse_color_value(name):
    """Parse a color string: named, #hex, rgb(r,g,b), or oklch(l,c,h)."""
    if not isinstance(name, str):
        return None
    named = {
        "black": (0,0,0), "red": (205,0,0), "green": (0,205,0), "yellow": (205,205,0),
        "blue": (0,0,238), "magenta": (205,0,205), "cyan": (0,205,205), "white": (229,229,229),
        "bright_black": (127,127,127), "bright_red": (255,85,85), "bright_green": (85,255,85),
        "bright_yellow": (255,255,85), "bright_blue": (85,85,255), "bright_magenta": (255,85,255),
        "bright_cyan": (85,255,255), "bright_white": (255,255,255),
    }
    if name in named:
        return named[name]
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
            l, c, h = float(parts[0].strip()), float(parts[1].strip()), float(parts[2].strip())
            return _oklch_to_rgb(l, c, h)
        except (ValueError, IndexError):
            return None
    return None

def color_name_to_ansi(name, is_bg=False):
    """Convert a color name, hex, rgb(), or oklch() to ANSI code string."""
    basic_named = {
        "black": "30", "red": "31", "green": "32", "yellow": "33",
        "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
        "bright_black": "90", "bright_red": "91", "bright_green": "92",
        "bright_yellow": "93", "bright_blue": "94", "bright_magenta": "95",
        "bright_cyan": "96", "bright_white": "97",
    }
    if name in basic_named:
        code = basic_named[name]
        if is_bg:
            return str(int(code) + 10)
        return code
    rgb = _parse_color_value(name)
    if rgb:
        r, g, b = rgb
        if is_bg:
            return f"48;2;{r};{g};{b}"
        return f"38;2;{r};{g};{b}"
    return ""

# =============================================================================
# ERROR TYPES
# =============================================================================


