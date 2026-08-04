## 00 -- 00_header.py -- header / imports
#!/usr/bin/env python3
"""
ArbPlus Language Interpreter
"A Really Bad Programming Language"

A single-file Python interpreter for the ArbPlus language.
Supports: metadata, declarations, overrides, functions, shell escapes,
inline C, typed variables, arb containers, file I/O, directory ops,
conditionals, loops, colored I/O, OS globals, and extensions.
"""

import sys
import os
import re
import textwrap
import subprocess
import time
import struct
import base64
import json
import datetime
import platform
import shutil
import ctypes
import importlib.util
import urllib.request
import urllib.error
from typing import Any, Optional as Opt
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# DATA TYPE DEFINITIONS
# =============================================================================


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


## 02 -- 02_errors.py -- exception classes
class ArbPlusError(Exception):
    pass

class ArbError(Exception):
    pass

class CatchableError(Exception):
    """Catchable error for try/catch - carries a message string."""
    def __init__(self, message):
        self.message = message
        super().__init__(message)

class BreakException(Exception):
    pass

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class ExitException(Exception):
    def __init__(self, code=0):
        self.code = code

# =============================================================================
# LEXER AND TOKENIZER
# =============================================================================

#token.marker

## 03 -- 03_lexer.py -- TokenType / Token / Lexer
class TokenType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NULL = "NULL"
    IDENT = "IDENT"
    KEYWORD = "KEYWORD"
    SEMI = "SEMI"
    GT = "GT"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    COMMA = "COMMA"
    COLON = "COLON"
    DOT = "DOT"
    ASSIGN = "ASSIGN"
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"
    CARET = "CARET"
    EXCLAM = "EXCLAM"
    CONCAT = "CONCAT"
    SWAP = "SWAP"
    EQ = "EQ"
    NEQ = "NEQ"
    LT = "LT"
    LE = "LE"
    GE = "GE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    QUESTION = "QUESTION"
    META = "META"
    USE = "USE"
    IMPORT = "IMPORT"
    DASHDASH = "DASHDASH"
    ARB_LIT = "ARB_LIT"
    C_BLOCK = "C_BLOCK"
    CMD_BLOCK = "CMD_BLOCK"
    PS_BLOCK = "PS_BLOCK"
    PY_BLOCK = "PY_BLOCK"
    INTERP_STRING = "INTERP_STRING"
    MAP_LIT = "MAP_LIT"
    NEWLINE = "NEWLINE"
    EOF = "EOF"
    CTRL = "CTRL"
    ALT = "ALT"

#keywords.marker
KEYWORDS = {
    "if", "elif", "else", "for", "while", "break", "return",
    "exit", "quit", "end", "not", "const", "let", "true", "false",
    "in", "to", "step",
    "repeat", "until", "switch", "case", "default",
    "try", "catch", "finally", "del", "null",
}

@dataclass
class Token:
    type: TokenType
    value: str
    line: int = 0
    col: int = 0

class Lexer:
    def __init__(self, source):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1
        self.tokens = []

    def peek(self, offset=0):
        p = self.pos + offset
        if p < len(self.source):
            return self.source[p]
        return '\0'

    def advance(self):
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.col = 1
        else:
            self.col += 1
        return ch

    def tokenize(self):
        while self.pos < len(self.source):
            ch = self.peek()

            if ch in ' \t\r':
                self.advance()
                continue

            if ch == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, self.col))
                self.advance()
                continue

            # Single-line Comments
            if ch == '/' and self.peek(1) == '/':
                # Makes sure that comments are unable to be terminated via ; || >
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
                continue
            if ch == '/' and self.peek(1) == '*':
                self.advance()
                self.advance()
                while self.pos < len(self.source):
                    if self.peek() == '*' and self.peek(1) == '/':
                        self.advance()
                        self.advance()
                        break
                    self.advance()
                continue

            # Statement terminators
            if ch == ';':
                self.tokens.append(Token(TokenType.SEMI, ';', self.line, self.col))
                self.advance()
                continue
            if ch == '>' and self.peek(1) != '=':
                self.tokens.append(Token(TokenType.GT, '>', self.line, self.col))
                self.advance()
                continue

            # Special directives
            if ch == '#':
                if self.source[self.pos:self.pos+5] == '#meta':
                    for _ in range(5): self.advance()
                    self.tokens.append(Token(TokenType.META, '#meta', self.line, self.col))
                    continue
                if self.source[self.pos:self.pos+4] == '#use':
                    for _ in range(4): self.advance()
                    self.tokens.append(Token(TokenType.USE, '#use', self.line, self.col))
                    continue
                if self.source[self.pos:self.pos+7] == '#import':
                    for _ in range(7): self.advance()
                    self.tokens.append(Token(TokenType.IMPORT, '#import', self.line, self.col))
                    continue
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
                continue

            if ch == '-' and self.peek(1) == '-':
                self.advance()
                self.advance()
                start = self.pos
                while self.pos < len(self.source) and self.peek().isalpha():
                    self.advance()
                word = self.source[start:self.pos]
                self.tokens.append(Token(TokenType.DASHDASH, '--' + word, self.line, self.col))
                continue

            # Block markers - capture raw text for shell/C blocks
            if ch == 'c' and self.peek(1) == '{':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.C_BLOCK, 'c{', self.line, self.col))
                # Read code until matching '}'
                code = self.read_raw_block()
                self.tokens.append(Token(TokenType.STRING, code, self.line, self.col))
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                continue
            if ch == 'c' and self.peek(1) == 'm' and self.peek(2) == 'd' and self.peek(3) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.CMD_BLOCK, 'cmd{', self.line, self.col))
                code = self.read_raw_block()
                self.tokens.append(Token(TokenType.STRING, code, self.line, self.col))
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                continue
            if ch == 'p' and self.peek(1) == 's' and self.peek(2) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.PS_BLOCK, 'ps{', self.line, self.col))
                code = self.read_raw_block()
                self.tokens.append(Token(TokenType.STRING, code, self.line, self.col))
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                continue
            if ch == 'p' and self.peek(1) == 'y' and self.peek(2) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.PY_BLOCK, 'py{', self.line, self.col))
                code = self.read_raw_block()
                self.tokens.append(Token(TokenType.STRING, code, self.line, self.col))
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, self.col))
                continue
            if ch == 'a' and self.peek(1) == 'r' and self.peek(2) == 'b' and self.peek(3) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.ARB_LIT, 'arb{', self.line, self.col))
                continue
            if ch == 'm' and self.peek(1) == 'a' and self.peek(2) == 'p' and self.peek(3) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.MAP_LIT, 'map{', self.line, self.col))
                continue

            # Raw strings: r"..." or r'...' (no escape processing)
            if ch == 'r' and self.peek(1) in ('"', "'") and (self.pos == 0 or not self.source[self.pos-1].isalnum() and self.source[self.pos-1] != '_'):
                self.advance()  # skip 'r'
                quote = self.advance()
                self.read_raw_string(quote)
                continue

            # Strings
            if ch == '"' or ch == "'":
                self.read_string(ch)
                continue

            # Numbers
            if ch.isdigit():
                self.read_number()
                continue

            # Identifiers
            if ch.isalpha() or ch == '_':
                self.read_identifier()
                continue

            # Multi-char operators
            if ch == '.' and self.peek(1) == '.':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.CONCAT, '..', self.line, self.col))
                continue
            if ch == '<' and self.peek(1) == '>':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.SWAP, '<>', self.line, self.col))
                continue
            if ch == '=' and self.peek(1) == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.EQ, '==', self.line, self.col))
                continue
            if ch == '!' and self.peek(1) == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.NEQ, '!=', self.line, self.col))
                continue
            if ch == '<' and self.peek(1) == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.LE, '<=', self.line, self.col))
                continue
            if ch == '<':
                self.advance()
                self.tokens.append(Token(TokenType.LT, '<', self.line, self.col))
                continue
            if ch == '>' and self.peek(1) == '=':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.GE, '>=', self.line, self.col))
                continue
            if ch == '&' and self.peek(1) == '&':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.AND, '&&', self.line, self.col))
                continue
            if ch == '|' and self.peek(1) == '|':
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.OR, '||', self.line, self.col))
                continue

            # Single-char tokens
            single_map = {
                '=': TokenType.ASSIGN, '+': TokenType.PLUS, '-': TokenType.MINUS,
                '*': TokenType.STAR, '/': TokenType.SLASH, '%': TokenType.PERCENT,
                '^': TokenType.CARET, '{': TokenType.LBRACE, '}': TokenType.RBRACE,
                '(': TokenType.LPAREN, ')': TokenType.RPAREN, '[': TokenType.LBRACKET,
                ']': TokenType.RBRACKET, ',': TokenType.COMMA, ':': TokenType.COLON,
                '.': TokenType.DOT, '?': TokenType.QUESTION,
                '!': TokenType.EXCLAM,
            }
            if ch in single_map:
                self.tokens.append(Token(single_map[ch], ch, self.line, self.col))
                self.advance()
                continue

            raise ArbPlusError(f"Lexer error: Unexpected character '{ch}' at line {self.line}, col {self.col}")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens

    def read_string(self, quote):
        self.advance()
        result = []
        has_interp = False
        while self.pos < len(self.source) and self.peek() != quote:
            ch = self.peek()
            if ch == '\\':
                self.advance()
                esc = self.advance()
                if esc == 'n': result.append('\n')
                elif esc == 't': result.append('\t')
                elif esc == 'r': result.append('\r')
                elif esc == '\\': result.append('\\')
                elif esc == quote: result.append(quote)
                elif esc == '0': result.append('\0')
                else: result.append(esc)
            elif ch == '$' and self.peek(1) == '{':
                has_interp = True
                # Read the interpolation expression as-is (including ${ and })
                result.append('${')
                self.advance()  # $
                self.advance()  # {
                depth = 1
                while self.pos < len(self.source) and depth > 0:
                    c = self.peek()
                    if c == '{': depth += 1
                    elif c == '}': 
                        depth -= 1
                        if depth == 0:
                            result.append('}')
                            self.advance()
                            break
                    result.append(self.advance())
            else:
                result.append(self.advance())
        if self.pos >= len(self.source):
            raise ArbPlusError(f"Lexer error: unterminated string at line {self.line}")
        self.advance()
        raw = ''.join(result)
        if has_interp:
            self.tokens.append(Token(TokenType.INTERP_STRING, raw, self.line, self.col))
        else:
            self.tokens.append(Token(TokenType.STRING, raw, self.line, self.col))

    def read_raw_string(self, quote):
        """Read a raw string literal - no escape processing, keeps backslashes as-is."""
        result = []
        has_interp = False
        while self.pos < len(self.source) and self.peek() != quote:
            ch = self.peek()
            if ch == '$' and self.peek(1) == '{':
                has_interp = True
                result.append('${')
                self.advance()
                self.advance()
                depth = 1
                while self.pos < len(self.source) and depth > 0:
                    c = self.peek()
                    if c == '{': depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            result.append('}')
                            self.advance()
                            break
                    result.append(self.advance())
            else:
                result.append(self.advance())
        if self.pos >= len(self.source):
            raise ArbPlusError(f"Lexer error: unterminated raw string at line {self.line}")
        self.advance()
        raw = ''.join(result)
        if has_interp:
            self.tokens.append(Token(TokenType.INTERP_STRING, raw, self.line, self.col))
        else:
            self.tokens.append(Token(TokenType.STRING, raw, self.line, self.col))

    def read_number(self):
        start = self.pos
        is_float = False
        if self.peek() == '0' and self.peek(1) in ('x', 'X'):
            self.advance()
            self.advance()
            while self.pos < len(self.source) and self.peek() in '0123456789abcdefABCDEF':
                self.advance()
            hex_str = self.source[start:self.pos]
            self.tokens.append(Token(TokenType.INT, str(int(hex_str, 16)), self.line, self.col))
            return
        while self.pos < len(self.source) and self.peek().isdigit():
            self.advance()
        if self.peek() == '.' and self.peek(1).isdigit():
            is_float = True
            self.advance()
            while self.pos < len(self.source) and self.peek().isdigit():
                self.advance()
        num_str = self.source[start:self.pos]
        if is_float:
            self.tokens.append(Token(TokenType.FLOAT, num_str, self.line, self.col))
        else:
            self.tokens.append(Token(TokenType.INT, num_str, self.line, self.col))

    def read_raw_block(self):
        """Read raw text until matching closing brace, tracking depth."""
        depth = 1
        chars = []
        while self.pos < len(self.source) and depth > 0:
            ch = self.peek()
            if ch == '{':
                depth += 1
                chars.append(ch)
                self.advance()
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    self.advance()
                    break
                chars.append(ch)
                self.advance()
            else:
                chars.append(ch)
                self.advance()
        return ''.join(chars).strip()

    def read_identifier(self):
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        word = self.source[start:self.pos]
        if word == "true":
            self.tokens.append(Token(TokenType.TRUE, word, self.line, self.col))
        elif word == "false":
            self.tokens.append(Token(TokenType.FALSE, word, self.line, self.col))
        elif word == "null":
            self.tokens.append(Token(TokenType.NULL, word, self.line, self.col))
        elif word == "not":
            self.tokens.append(Token(TokenType.NOT, word, self.line, self.col))
        elif word == "and":
            self.tokens.append(Token(TokenType.AND, word, self.line, self.col))
        elif word == "or":
            self.tokens.append(Token(TokenType.OR, word, self.line, self.col))
        elif word in KEYWORDS:
            self.tokens.append(Token(TokenType.KEYWORD, word, self.line, self.col))
        else:
            self.tokens.append(Token(TokenType.IDENT, word, self.line, self.col))




def _arb_equals(a, b):
    """Deep equality check for ArbValues."""
    if isinstance(a, ArbValue) and isinstance(b, ArbValue):
        return a.py() == b.py()
    if isinstance(a, ArbValue):
        return a.py() == b
    if isinstance(b, ArbValue):
        return a == b.py()
    return a == b

# =============================================================================
# SECTION 4: AST NODES
# =============================================================================

@dataclass

## 04 -- 04_ast_nodes.py -- AST node classes
class MetaNode:
    entries: dict = field(default_factory=dict)

@dataclass
class DeclNode:
    uses: list = field(default_factory=list)
    imports: list = field(default_factory=list)

@dataclass
class OverrideNode:
    base_name: str = ""
    new_name: str = ""
    fixed_args: list = None  # For argument-aware --OV: fixed args baked in
    fixed_kwargs: dict = None  # Fixed kwargs baked in

@dataclass
class OverrideSwapNode:
    """--OV funcA <> funcB — completely swap two functions."""
    func_a: str = ""
    func_b: str = ""

@dataclass
class AutoNode:
    text: Any = None

@dataclass
class FuncDefNode:
    role: str = ""
    name: str = ""
    params: list = field(default_factory=list)
    body: list = field(default_factory=list)
    return_type: str = ""

@dataclass
class ProgramNode:
    metadata: MetaNode = None
    declarations: DeclNode = None
    overrides: list = field(default_factory=list)
    functions: dict = field(default_factory=dict)
    body: list = field(default_factory=list)

@dataclass
class AssignNode:
    name: str = ""
    value: Any = None
    is_const: bool = False
    type_hint: str = ""

@dataclass
class IfNode:
    conditions: list = field(default_factory=list)
    else_body: list = field(default_factory=list)

@dataclass
class ForNode:
    var_name: str = ""
    start: Any = None
    end: Any = None
    step: Any = None
    body: list = field(default_factory=list)
    iterable: Any = None

@dataclass
class WhileNode:
    condition: Any = None
    body: list = field(default_factory=list)

@dataclass
class BreakNode:
    label: str = ""

@dataclass
class ReturnNode:
    value: Any = None

@dataclass
class ExitNode:
    code: Any = None

@dataclass
class ExprStmtNode:
    expr: Any = None

@dataclass
class CBlockNode:
    code: str = ""
    file_ref: str = ""  # $!pathVar if loading from file

@dataclass
class BinOpNode:
    op: str = ""
    left: Any = None
    right: Any = None

@dataclass
class UnaryOpNode:
    op: str = ""
    operand: Any = None

@dataclass
class LiteralNode:
    value: Any = None

@dataclass
class VarNode:
    name: str = ""

@dataclass
class CallNode:
    name: str = ""
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)

@dataclass
class IndexNode:
    target: Any = None
    index: Any = None

@dataclass
class MemberNode:
    target: Any = None
    member: str = ""

@dataclass
class TypeCastNode:
    """Addition 15: .type() casting on any expression"""
    target: Any = None
    type_arg: Any = None

@dataclass
class OverrideDefaultsNode:
    """Inline --OV defaults for changing colors mid-script"""
    defaults: dict = None

@dataclass
class TernaryNode:
    cond: Any = None
    then_val: Any = None
    else_val: Any = None

@dataclass
class ArbLitNode:
    elements: list = field(default_factory=list)

@dataclass
class ListNode:
    elements: list = field(default_factory=list)

@dataclass
class SwapNode:
    left: str = ""
    right: str = ""

@dataclass
class ShellBlockNode:
    shell_type: str = ""
    code: str = ""
    file_ref: str = ""  # $!pathVar if loading from file

@dataclass
class PyBlockNode:
    code: str = ""
    file_ref: str = ""  # $!pathVar if loading from file

@dataclass
class StringInterpNode:
    """Interpolated string - evaluates ${expr} inside the string at runtime."""
    parts: list = field(default_factory=list)  # list of (is_expr, content) tuples

@dataclass
class RepeatNode:
    """repeat { body } until (condition) - runs body at least once."""
    body: list = field(default_factory=list)
    condition: Any = None

@dataclass
class TryNode:
    """try { } catch (err) { } [finally { }]"""
    try_body: list = field(default_factory=list)
    catch_var: str = ""
    catch_body: list = field(default_factory=list)
    finally_body: list = field(default_factory=list)

@dataclass
class SwitchNode:
    """switch (val) { case A: { } case B: { } default: { } }"""
    value: Any = None
    cases: list = field(default_factory=list)  # list of (value_expr, body)
    default_body: list = field(default_factory=list)

@dataclass
class MapLitNode:
    """map{ "key": value, ... }"""
    pairs: list = field(default_factory=list)  # list of (key_expr, value_expr)

@dataclass
class MapAssignNode:
    """map["key"] = value"""
    target: Any = None
    key: Any = None
    value: Any = None

@dataclass
class DelNode:
    """del(variableName) - deletes a variable from scope."""
    var_name: str = ""

@dataclass
class CleanNode:
    """--clean; or --clean stop; or --clean restart; - manual GC trigger."""
    mode: str = "collect"  # "collect", "stop", "restart", "count"

@dataclass
class DelegateReturnNode:
    """--F FuncName(Args) - delegate return to another function."""
    func_name: str = ""
    args: list = None
    kwargs: dict = None

@dataclass
class IncDecNode:
    """i++ or k-- shorthand."""
    var_name: str = ""
    op: str = ""  # "++" or "--"

@dataclass
class ForwardDeclNode:
    """let [name]; — forward declaration without value."""
    name: str = ""

# =============================================================================
# SECTION 5: PARSER
# =============================================================================


## 05 -- 05_parser.py -- Parser
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset=0):
        p = self.pos + offset
        if p < len(self.tokens):
            return self.tokens[p]
        return self.tokens[-1]

    def advance(self):
        tok = self.tokens[self.pos]
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return tok

    def expect(self, ttype):
        tok = self.peek()
        if tok.type != ttype:
            raise ArbPlusError(f"Parse error: expected {ttype.name} but got {tok.type.name} ('{tok.value}') at line {tok.line}")
        return self.advance()

    def skip_newlines(self):
        while self.peek().type == TokenType.NEWLINE:
            self.advance()

    def skip_terminators(self):
        while self.peek().type in (TokenType.SEMI, TokenType.NEWLINE):
            self.advance()

    def at(self, ttype):
        return self.peek().type == ttype

    def at_keyword(self, kw):
        return self.peek().type == TokenType.KEYWORD and self.peek().value == kw

    def parse(self):
        program = ProgramNode()
        program.metadata = MetaNode()
        program.declarations = DeclNode()
        program.body = []

        self.skip_newlines()

        if self.at(TokenType.META):
            self.parse_metadata(program)

        self.skip_terminators()

        while self.peek().type in (TokenType.USE, TokenType.IMPORT):
            if self.at(TokenType.USE):
                self.advance()
                name = self.expect(TokenType.IDENT).value
                program.declarations.uses.append(name)
                self.skip_terminators()
            elif self.at(TokenType.IMPORT):
                self.advance()
                name = self.expect(TokenType.IDENT).value
                program.declarations.imports.append(name)
                self.skip_terminators()

        self.skip_newlines()

        # Addition 30: --ErrOV flag at top level (before any --OV)
        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--err.ov':
            self.advance()
            # true is tokenized as TokenType.TRUE, not IDENT
            if self.peek().type in (TokenType.IDENT, TokenType.TRUE):
                val = self.advance().value
                if val in ('true', True):
                    program.metadata.entries["_err_ov"] = True
            self.skip_terminators()
            self.skip_newlines()

        # Addition: --ext.ov, --mod.ov, --chd.ov flags (Set-7)
        for flag_name in ('--ext.ov', '--mod.ov', '--chd.ov'):
            while self.peek().type == TokenType.DASHDASH and self.peek().value == flag_name:
                self.advance()
                if self.peek().type in (TokenType.IDENT, TokenType.TRUE):
                    val = self.advance().value
                    if val in ('true', True):
                        program.metadata.entries["_" + flag_name.replace("--", "").replace(".", "_")] = True
                self.skip_terminators()
                self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--OV':
            self.advance()
            base = self.expect(TokenType.IDENT).value
            if base == "defaults":
                # --OV defaults(fg, bg, b) [val1, val2, val3]
                # or --OV defaults(fg, bg, b) (fg: cyan, bg: black, b: bright)
                self.expect(TokenType.LPAREN)
                keys = []
                while not self.at(TokenType.RPAREN):
                    keys.append(self.expect(TokenType.IDENT).value)
                    if self.at(TokenType.COMMA): self.advance()
                self.expect(TokenType.RPAREN)
                # Support both [val1, val2] and (key: val, ...) syntax
                if self.at(TokenType.LBRACKET):
                    self.advance()
                    vals = []
                    while not self.at(TokenType.RBRACKET):
                        tok = self.advance()
                        vals.append(tok.value)
                        if self.at(TokenType.COMMA): self.advance()
                    self.expect(TokenType.RBRACKET)
                elif self.at(TokenType.LPAREN):
                    self.advance()
                    vals = []
                    while not self.at(TokenType.RPAREN):
                        if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
                            self.advance()  # skip key
                            self.advance()  # skip colon
                            vals.append(self.advance().value)
                        else:
                            vals.append(self.advance().value)
                        if self.at(TokenType.COMMA): self.advance()
                    self.expect(TokenType.RPAREN)
                else:
                    vals = []
                # Store as a special override
                program.overrides.append(OverrideNode("defaults", ""))
                program.metadata.entries["_ov_defaults"] = dict(zip(keys, vals))
            elif self.at(TokenType.SWAP):
                # --OV funcA <> funcB — complete swap
                self.advance()  # consume <>
                other = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideSwapNode(func_a=base, func_b=other))
            elif self.at(TokenType.LPAREN):
                # --OV base(args) new — argument-aware override with fixed args
                self.advance()  # consume (
                fixed_args = []
                while not self.at(TokenType.RPAREN):
                    fixed_args.append(self.parse_expr())
                    if self.at(TokenType.COMMA): self.advance()
                self.expect(TokenType.RPAREN)
                new = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideNode(base_name=base, new_name=new,
                                                    fixed_args=fixed_args, fixed_kwargs=None))
            else:
                new = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideNode(base, new))
            self.skip_terminators()

        self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--auto':
            auto_stmt = self.parse_auto_flag()
            program.body.append(auto_stmt)
            self.skip_terminators()
            self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--Function':
            func = self.parse_function_def()
            program.functions[func.name] = func
            self.skip_terminators()
            self.skip_newlines()

        body = self.parse_block_until([TokenType.EOF])
        program.body.extend(body)
        return program

    def parse_metadata(self, program):
        self.expect(TokenType.META)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_terminators()
        while not self.at(TokenType.RBRACE) and not self.at(TokenType.EOF):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break
            key = self.expect(TokenType.IDENT).value
            self.expect(TokenType.COLON)
            # Read value tokens until terminator
            val_parts = []
            while self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
                tok = self.advance()
                if tok.type == TokenType.STRING:
                    val_parts.append(tok.value)
                else:
                    val_parts.append(tok.value)
            val = ' '.join(val_parts) if len(val_parts) > 1 else (val_parts[0] if val_parts else '')
            # Try to convert to number if possible
            try:
                if '.' in val:
                    val = float(val)
                else:
                    val = int(val)
            except (ValueError, TypeError):
                pass
            program.metadata.entries[key] = val
            self.skip_terminators()
        self.expect(TokenType.RBRACE)

    def parse_auto_flag(self):
        self.advance()  # --auto
        text = None
        if self.at(TokenType.LPAREN):
            self.advance()
            if not self.at(TokenType.RPAREN):
                text = self.parse_expr()
            self.expect(TokenType.RPAREN)
        elif self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
            text = self.parse_expr()
        return AutoNode(text=text)

    def parse_function_def(self):
        self.advance()  # --Function
        role = self.expect(TokenType.IDENT).value
        self.expect(TokenType.DOT)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params = []
        while not self.at(TokenType.RPAREN):
            pname = self.expect(TokenType.IDENT).value
            ptype = ""
            if self.at(TokenType.COLON):
                self.advance()
                ptype = self.expect(TokenType.IDENT).value
            params.append((pname, ptype))
            if self.at(TokenType.COMMA):
                self.advance()
        self.expect(TokenType.RPAREN)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        self.skip_terminators()
        body = self.parse_block_until([TokenType.RBRACE])
        self.expect(TokenType.RBRACE)
        return FuncDefNode(role=role, name=name, params=params, body=body)

    def parse_block_until(self, terminators):
        statements = []
        self.skip_terminators()
        while self.peek().type not in terminators and not self.at(TokenType.EOF):
            # Handle inline --OV defaults (Addition 7)
            # Addition 30: --ErrOV true; flag
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--ErrOV':
                self.advance()
                if self.peek().type == TokenType.IDENT:
                    val = self.advance().value
                    if val == 'true':
                        self.err_ov_enabled = True
                self.skip_terminators()
                continue
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--OV':
                self.advance()
                base = self.expect(TokenType.IDENT).value
                if base == "defaults":
                    self.expect(TokenType.LPAREN)
                    keys = []
                    while not self.at(TokenType.RPAREN):
                        keys.append(self.expect(TokenType.IDENT).value)
                        if self.at(TokenType.COMMA): self.advance()
                    self.expect(TokenType.RPAREN)
                    # Allow both [val1, val2] and (fg: color, bg: color) syntax
                    if self.at(TokenType.LBRACKET):
                        self.advance()
                        vals = []
                        while not self.at(TokenType.RBRACKET):
                            tok = self.advance()
                            vals.append(tok.value)
                            if self.at(TokenType.COMMA): self.advance()
                        self.expect(TokenType.RBRACKET)
                    elif self.at(TokenType.LPAREN):
                        self.advance()
                        vals = []
                        while not self.at(TokenType.RPAREN):
                            if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
                                self.advance()  # skip key
                                self.advance()  # skip colon
                                vals.append(self.advance().value)
                            else:
                                vals.append(self.advance().value)
                            if self.at(TokenType.COMMA): self.advance()
                        self.expect(TokenType.RPAREN)
                    else:
                        vals = []
                    # Create an inline override statement
                    stmt = OverrideDefaultsNode(defaults=dict(zip(keys, vals)))
                    statements.append(stmt)
                elif self.at(TokenType.SWAP):
                    # --OV funcA <> funcB — complete swap
                    self.advance()  # consume <>
                    other = self.expect(TokenType.IDENT).value
                    statements.append(OverrideSwapNode(func_a=base, func_b=other))
                elif self.at(TokenType.LPAREN):
                    # --OV base(args) new — argument-aware override with fixed args
                    self.advance()  # consume (
                    fixed_args = []
                    while not self.at(TokenType.RPAREN):
                        fixed_args.append(self.parse_expr())
                        if self.at(TokenType.COMMA): self.advance()
                    self.expect(TokenType.RPAREN)
                    new = self.expect(TokenType.IDENT).value
                    statements.append(OverrideNode(base_name=base, new_name=new,
                                                   fixed_args=fixed_args, fixed_kwargs=None))
                else:
                    new = self.expect(TokenType.IDENT).value
                    statements.append(OverrideNode(base, new))
                self.skip_terminators()
                continue
            # Handle in-file auto mode flag
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--auto':
                statements.append(self.parse_auto_flag())
                self.skip_terminators()
                continue
            # Handle --clean; (Addition 24)
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--clean':
                self.advance()
                mode = "collect"
                if self.peek().type == TokenType.IDENT:
                    mode = self.advance().value
                self.skip_terminators()
                statements.append(CleanNode(mode=mode))
                continue
            # Handle --F FuncName(Args) (Addition 25)
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--F':
                self.advance()
                func_name = self.expect(TokenType.IDENT).value
                # Support role.name dotted syntax
                if self.at(TokenType.DOT):
                    self.advance()
                    name_part = self.expect(TokenType.IDENT).value
                    func_name = func_name + "." + name_part
                args = []
                kwargs = {}
                if self.at(TokenType.LPAREN):
                    self.advance()
                    while not self.at(TokenType.RPAREN):
                        if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
                            kname = self.advance().value
                            self.advance()  # skip colon
                            kexpr = self.parse_expr()
                            kwargs[kname] = kexpr
                        else:
                            args.append(self.parse_expr())
                        if self.at(TokenType.COMMA):
                            self.advance()
                    self.expect(TokenType.RPAREN)
                self.skip_terminators()
                statements.append(DelegateReturnNode(func_name=func_name, args=args, kwargs=kwargs))
                continue
            stmt = self.parse_statement()
            if stmt is not None:
                statements.append(stmt)
            self.skip_terminators()
        return statements

    def parse_statement(self):
        self.skip_newlines()
        tok = self.peek()

        if tok.type == TokenType.KEYWORD and tok.value in ("const", "let"):
            return self.parse_var_decl()

        if tok.type == TokenType.KEYWORD and tok.value == "if":
            return self.parse_if()

        if tok.type == TokenType.KEYWORD and tok.value == "for":
            return self.parse_for()

        if tok.type == TokenType.KEYWORD and tok.value == "while":
            return self.parse_while()

        if tok.type == TokenType.KEYWORD and tok.value == "repeat":
            return self.parse_repeat()

        if tok.type == TokenType.KEYWORD and tok.value == "switch":
            return self.parse_switch()

        if tok.type == TokenType.KEYWORD and tok.value == "try":
            return self.parse_try()

        if tok.type == TokenType.KEYWORD and tok.value == "break":
            self.advance()
            label = ""
            if self.at(TokenType.IDENT):
                label = self.advance().value
            return BreakNode(label=label)

        if tok.type == TokenType.KEYWORD and tok.value == "return":
            self.advance()
            # bare return; or return> or return at end of block
            if self.peek().type in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
                return ReturnNode(value=None)
            # return() with empty parens = bare return
            if self.peek().type == TokenType.LPAREN and self.peek(1).type == TokenType.RPAREN:
                self.advance()  # consume (
                self.advance()  # consume )
                return ReturnNode(value=None)
            val = self.parse_expr()
            return ReturnNode(value=val)

        if tok.type == TokenType.KEYWORD and tok.value in ("exit", "quit"):
            self.advance()
            code = None
            if self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
                code = self.parse_expr()
            return ExitNode(code=code)

        if tok.type == TokenType.KEYWORD and tok.value == "end":
            self.advance()
            return None

        if tok.type == TokenType.KEYWORD and tok.value == "del":
            self.advance()
            # del can be: del varName  OR  del(varName)
            if self.at(TokenType.LPAREN):
                self.advance()
                name = self.expect(TokenType.IDENT).value
                self.expect(TokenType.RPAREN)
            else:
                name = self.expect(TokenType.IDENT).value
            return DelNode(var_name=name)

        if tok.type == TokenType.C_BLOCK:
            return self.parse_c_block()

        if tok.type == TokenType.CMD_BLOCK:
            return self.parse_shell_block('cmd')

        if tok.type == TokenType.PS_BLOCK:
            return self.parse_shell_block('ps')

        if tok.type == TokenType.PY_BLOCK:
            return self.parse_py_block()

        if tok.type == TokenType.ARB_LIT:
            expr = self.parse_arb_literal()
            return ExprStmtNode(expr=expr)

        return self.parse_expr_statement()

    def parse_var_decl(self):
        kw = self.advance().value
        is_const = (kw == "const")
        # Forward declaration: let [name]; — no value assigned yet
        if self.at(TokenType.LBRACKET):
            self.advance()  # consume [
            # Accept IDENT or keyword tokens (null, true, false) as type names
            if self.peek().type == TokenType.IDENT:
                name = self.advance().value
            elif self.peek().type in (TokenType.NULL, TokenType.TRUE, TokenType.FALSE):
                name = self.advance().value
            else:
                raise ArbPlusError(f"Parse error: expected type name but got {self.peek().type} ('{self.peek().value}') at line {self.peek().line}")
            # Check if this is a typed declaration: let [int] name = value
            if self.at(TokenType.RBRACKET):
                self.advance()  # consume ] — forward declaration: let [name];
                return ForwardDeclNode(name=name)
            # else: the IDENT after [ is a type name, not the variable name
            type_hint = name  # e.g. "int", "string", "float", etc.
            # null is also valid as a type hint
            if type_hint == "null" or type_hint == "Null":
                type_hint = "null"
            self.expect(TokenType.RBRACKET)  # consume ]
            name = self.expect(TokenType.IDENT).value
            self.expect(TokenType.ASSIGN)
            value = self.parse_expr()
            return AssignNode(name=name, value=value, is_const=is_const, type_hint=type_hint)
        name = self.expect(TokenType.IDENT).value
        type_hint = ""
        if self.at(TokenType.COLON):
            self.advance()
            type_hint = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN)
        value = self.parse_expr()
        return AssignNode(name=name, value=value, is_const=is_const, type_hint=type_hint)

    def parse_if(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        cond = self.parse_expr()
        self.expect(TokenType.RPAREN)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        body = self.parse_block_until([TokenType.RBRACE])
        self.expect(TokenType.RBRACE)
        conditions = [(cond, body)]
        else_body = []
        while True:
            self.skip_terminators()
            if self.at_keyword("elif"):
                self.advance()
                self.expect(TokenType.LPAREN)
                cond = self.parse_expr()
                self.expect(TokenType.RPAREN)
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                body = self.parse_block_until([TokenType.RBRACE])
                self.expect(TokenType.RBRACE)
                conditions.append((cond, body))
            elif self.at_keyword("else"):
                self.advance()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                else_body = self.parse_block_until([TokenType.RBRACE])
                self.expect(TokenType.RBRACE)
                break
            else:
                break
        return IfNode(conditions=conditions, else_body=else_body)

    def parse_for(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        var_name = self.expect(TokenType.IDENT).value
        if self.at_keyword("in") or (self.peek().type == TokenType.IDENT and self.peek().value == "in"):
            self.advance()
            iterable = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            return ForNode(var_name=var_name, body=body, iterable=iterable)
        elif self.at(TokenType.ASSIGN):
            self.advance()
            start = self.parse_expr()
            if (self.peek().type == TokenType.IDENT and self.peek().value == "to") or self.at_keyword("to"):
                self.advance()
            end = self.parse_expr()
            step = None
            if (self.peek().type == TokenType.IDENT and self.peek().value == "step") or self.at_keyword("step"):
                self.advance()
                step = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            return ForNode(var_name=var_name, start=start, end=end, step=step, body=body)
        elif self.at(TokenType.LT):
            # for (i < N) — iterate from 0 to N-1
            self.advance()
            end = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            # start=0, end=N, step=1 — variable goes 0..N-1
            return ForNode(var_name=var_name, start=LiteralNode(ArbInt(0)),
                         end=end, step=LiteralNode(ArbInt(1)), body=body)
        elif self.at(TokenType.LE):
            # for (i <= N) — iterate from 0 to N inclusive
            self.advance()
            end = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            # start=0, end=N+1, step=1 — variable goes 0..N
            return ForNode(var_name=var_name, start=LiteralNode(ArbInt(0)),
                         end=end, step=LiteralNode(ArbInt(1)), body=body)
        else:
            raise ArbPlusError(f"Parse error: expected 'in', '=', '<', or '<=' in for loop at line {self.peek().line}")

    def parse_while(self):
        self.advance()
        self.expect(TokenType.LPAREN)
        cond = self.parse_expr()
        self.expect(TokenType.RPAREN)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        body = self.parse_block_until([TokenType.RBRACE])
        self.expect(TokenType.RBRACE)
        return WhileNode(condition=cond, body=body)

    def parse_repeat(self):
        self.advance()  # repeat
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        body = self.parse_block_until([TokenType.RBRACE])
        self.expect(TokenType.RBRACE)
        self.skip_terminators()
        self.skip_newlines()
        # Expect 'until' keyword
        if not self.at_keyword("until"):
            raise ArbPlusError(f"Parse error: expected 'until' after repeat block at line {self.peek().line}")
        self.advance()
        self.expect(TokenType.LPAREN)
        cond = self.parse_expr()
        self.expect(TokenType.RPAREN)
        return RepeatNode(body=body, condition=cond)

    def parse_switch(self):
        self.advance()  # switch
        self.expect(TokenType.LPAREN)
        value = self.parse_expr()
        self.expect(TokenType.RPAREN)
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        cases = []
        default_body = []
        while not self.at(TokenType.RBRACE) and not self.at(TokenType.EOF):
            self.skip_newlines()
            if self.at_keyword("case"):
                self.advance()
                case_val = self.parse_expr()
                if self.at(TokenType.COLON):
                    self.advance()
                self.skip_terminators()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                case_body = self.parse_block_until([TokenType.RBRACE])
                self.expect(TokenType.RBRACE)
                cases.append((case_val, case_body))
            elif self.at_keyword("default"):
                self.advance()
                if self.at(TokenType.COLON):
                    self.advance()
                self.skip_terminators()
                self.skip_newlines()
                self.expect(TokenType.LBRACE)
                default_body = self.parse_block_until([TokenType.RBRACE])
                self.expect(TokenType.RBRACE)
            else:
                raise ArbPlusError(f"Parse error: expected 'case' or 'default' in switch at line {self.peek().line}")
            self.skip_terminators()
        self.expect(TokenType.RBRACE)
        return SwitchNode(value=value, cases=cases, default_body=default_body)

    def parse_try(self):
        self.advance()  # try
        self.skip_newlines()
        self.expect(TokenType.LBRACE)
        try_body = self.parse_block_until([TokenType.RBRACE])
        self.expect(TokenType.RBRACE)
        self.skip_terminators()
        self.skip_newlines()
        catch_var = ""
        catch_body = []
        finally_body = []
        if self.at_keyword("catch"):
            self.advance()
            self.expect(TokenType.LPAREN)
            catch_var = self.expect(TokenType.IDENT).value
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            catch_body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            self.skip_terminators()
            self.skip_newlines()
        if self.at_keyword("finally"):
            self.advance()
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            finally_body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
        return TryNode(try_body=try_body, catch_var=catch_var, catch_body=catch_body, finally_body=finally_body)

    def parse_c_block(self):
        self.advance()  # c{
        # Next token is the raw code as a STRING
        if self.at(TokenType.STRING):
            code = self.advance().value
        else:
            code = ''
        if self.at(TokenType.RBRACE):
            self.advance()
        # Check for $!fileRef pattern (Addition 27)
        file_ref = ""
        stripped = code.strip()
        if stripped.startswith('$!'):
            file_ref = stripped[2:].strip()
            code = ''
        return CBlockNode(code=code, file_ref=file_ref)

    def parse_shell_block(self, shell_type):
        self.advance()  # cmd{ or ps{
        if self.at(TokenType.STRING):
            code = self.advance().value
        else:
            code = ''
        if self.at(TokenType.RBRACE):
            self.advance()
        # Check for $!fileRef pattern (Addition 27)
        file_ref = ""
        stripped = code.strip()
        if stripped.startswith('$!'):
            file_ref = stripped[2:].strip()
            code = ''
        return ShellBlockNode(shell_type=shell_type, code=code, file_ref=file_ref)

    def parse_py_block(self):
        self.advance()  # py{
        if self.at(TokenType.STRING):
            code = self.advance().value
        else:
            code = ''
        if self.at(TokenType.RBRACE):
            self.advance()
        # Check for $!fileRef pattern
        file_ref = ""
        stripped = code.strip()
        if stripped.startswith('$!'):
            file_ref = stripped[2:].strip()
            code = ''  # code will be loaded at execution time
        return PyBlockNode(code=code, file_ref=file_ref)

    def parse_expr_statement(self):
        # Check for var++/var-- shorthand
        if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.PLUS and self.peek(2).type == TokenType.PLUS:
            var_name = self.advance().value
            self.advance()  # +
            self.advance()  # +
            return IncDecNode(var_name=var_name, op="++")
        # DASHDASH token with value "--" (no keyword) following an IDENT
        if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.DASHDASH and self.peek(1).value == "--":
            var_name = self.advance().value
            self.advance()  # --
            return IncDecNode(var_name=var_name, op="--")
        expr = self.parse_expr()
        if self.at(TokenType.ASSIGN) and isinstance(expr, VarNode):
            self.advance()
            value = self.parse_expr()
            return AssignNode(name=expr.name, value=value)
        if self.at(TokenType.ASSIGN) and isinstance(expr, IndexNode):
            # map["key"] = value or list[n] = value
            self.advance()
            value = self.parse_expr()
            return MapAssignNode(target=expr.target, key=expr.index, value=value)
        if self.at(TokenType.SWAP):
            self.advance()
            right = self.parse_expr()
            if isinstance(expr, VarNode) and isinstance(right, VarNode):
                return SwapNode(left=expr.name, right=right.name)
            raise ArbPlusError("Swap requires two variable names")
        return ExprStmtNode(expr=expr)

    def parse_expr(self):
        return self.parse_ternary()

    def parse_ternary(self):
        cond = self.parse_or()
        if self.at(TokenType.QUESTION):
            self.advance()
            then_val = self.parse_ternary()
            if self.at(TokenType.COLON):
                self.advance()
            else_val = self.parse_ternary()
            return TernaryNode(cond=cond, then_val=then_val, else_val=else_val)
        return cond

    def parse_or(self):
        left = self.parse_and()
        while self.at(TokenType.OR):
            self.advance()
            right = self.parse_and()
            left = BinOpNode(op="||", left=left, right=right)
        return left

    def parse_and(self):
        left = self.parse_not()
        while self.at(TokenType.AND):
            self.advance()
            right = self.parse_not()
            left = BinOpNode(op="&&", left=left, right=right)
        return left

    def parse_not(self):
        if self.at(TokenType.NOT):
            self.advance()
            operand = self.parse_not()
            return UnaryOpNode(op="not", operand=operand)
        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_concat()
        while self.peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LE, TokenType.GE, TokenType.GT):
            op = self.advance().value
            right = self.parse_concat()
            left = BinOpNode(op=op, left=left, right=right)
        return left

    def parse_concat(self):
        left = self.parse_add()
        while self.at(TokenType.CONCAT):
            self.advance()
            right = self.parse_add()
            left = BinOpNode(op="..", left=left, right=right)
        return left

    def parse_add(self):
        left = self.parse_mul()
        while self.peek().type in (TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_mul()
            left = BinOpNode(op=op, left=left, right=right)
        return left

    def parse_mul(self):
        left = self.parse_unary()
        while self.peek().type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT, TokenType.CARET):
            op = self.advance().value
            right = self.parse_unary()
            left = BinOpNode(op=op, left=left, right=right)
        return left

    def parse_unary(self):
        if self.at(TokenType.MINUS):
            self.advance()
            operand = self.parse_unary()
            return UnaryOpNode(op="-", operand=operand)
        if self.at(TokenType.PLUS):
            self.advance()
            return self.parse_unary()
        return self.parse_postfix()

    def parse_postfix(self):
        expr = self.parse_primary()
        while True:
            if self.at(TokenType.LBRACKET):
                self.advance()
                index = self.parse_expr()
                self.expect(TokenType.RBRACKET)
                expr = IndexNode(target=expr, index=index)
            elif self.at(TokenType.DOT):
                self.advance()
                # Allow keywords as member names (e.g. dir.del, open.url)
                if self.at(TokenType.IDENT):
                    member = self.advance().value
                elif self.at(TokenType.KEYWORD):
                    member = self.advance().value
                else:
                    self.raise_error(f"Expected identifier after '.', got {self.peek().type}")
                if self.at(TokenType.LPAREN):
                    self.advance()
                    args = []
                    kwargs = {}
                    while not self.at(TokenType.RPAREN):
                        if self._try_parse_flag_arg(kwargs):
                            pass
                        elif self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
                            arg_name = self.advance().value
                            self.advance()
                            kwargs[arg_name] = self.parse_kwarg_value()
                        else:
                            args.append(self.parse_expr())
                        if self.at(TokenType.COMMA):
                            self.advance()
                    self.expect(TokenType.RPAREN)
                    if member == "type" and len(args) == 1:
                        # Climate's .type() switching
                        expr = TypeCastNode(target=expr, type_arg=args[0])
                    elif isinstance(expr, VarNode):
                        expr = CallNode(name=f"{expr.name}.{member}", args=args, kwargs=kwargs)
                    elif isinstance(expr, MemberNode):
                        expr = CallNode(name=f"{expr.target}.{expr.member}.{member}", args=args, kwargs=kwargs)
                    else:
                        expr = CallNode(name=member, args=args, kwargs=kwargs)
                else:
                    expr = MemberNode(target=expr, member=member)
            elif self.at(TokenType.LPAREN) and isinstance(expr, VarNode):
                self.advance()
                args = []
                kwargs = {}
                while not self.at(TokenType.RPAREN):
                    if self._try_parse_flag_arg(kwargs):
                        pass
                    elif self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
                        arg_name = self.advance().value
                        self.advance()
                        kwargs[arg_name] = self.parse_kwarg_value()
                    else:
                        args.append(self.parse_expr())
                    if self.at(TokenType.COMMA):
                        self.advance()
                self.expect(TokenType.RPAREN)
                expr = CallNode(name=expr.name, args=args, kwargs=kwargs)
            else:
                break
        return expr

    def _try_parse_flag_arg(self, kwargs):
        """Check for -w or -e flags in function call arguments. Returns True if consumed."""
        if self.peek().type == TokenType.MINUS and self.peek(1).type == TokenType.IDENT:
            flag = self.peek(1).value
            if flag == "w":
                self.advance()  # consume -
                self.advance()  # consume w
                kwargs["_warn_flag"] = LiteralNode(value=ArbBool(True))
                return True
            elif flag == "e":
                self.advance()  # consume -
                self.advance()  # consume e
                kwargs["_err_flag"] = LiteralNode(value=ArbBool(True))
                return True
        return False

    def parse_primary(self):
        tok = self.peek()
        if tok.type == TokenType.INT:
            self.advance()
            return LiteralNode(value=ArbInt(int(tok.value)))
        if tok.type == TokenType.FLOAT:
            self.advance()
            return LiteralNode(value=ArbFloat(float(tok.value)))
        if tok.type == TokenType.STRING:
            self.advance()
            return LiteralNode(value=ArbString(tok.value))
        if tok.type == TokenType.INTERP_STRING:
            self.advance()
            return self.parse_interp_string(tok.value)
        if tok.type == TokenType.MAP_LIT:
            return self.parse_map_literal()
        if tok.type == TokenType.TRUE:
            self.advance()
            return LiteralNode(value=ArbBool(True))
        if tok.type == TokenType.FALSE:
            self.advance()
            return LiteralNode(value=ArbBool(False))
        if tok.type == TokenType.NULL:
            self.advance()
            return LiteralNode(value=ArbNull())
        if tok.type == TokenType.IDENT:
            self.advance()
            return VarNode(name=tok.value)
        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return expr
        if tok.type == TokenType.LBRACKET:
            return self.parse_list_literal()
        if tok.type == TokenType.ARB_LIT:
            return self.parse_arb_literal()
        if tok.type == TokenType.MINUS:
            self.advance()
            operand = self.parse_primary()
            return UnaryOpNode(op="-", operand=operand)
        raise ArbPlusError(f"Parse error: Unexpected token {tok.type.name} ('{tok.value}') at line {tok.line}")

    def parse_kwarg_value(self):
        """Parse a named argument value. Bare identifiers become VarNodes — at eval time,
        undefined names fall back to string literals (for color names like cyan, red, etc.)."""
        tok = self.peek()
        if tok.type == TokenType.IDENT:
            # Check if it's followed by ( or . — if so, it's a function call or member access
            if self.peek(1).type in (TokenType.LPAREN, TokenType.DOT, TokenType.LBRACKET):
                return self.parse_expr()
            # Bare identifier — treat as VarNode, eval will resolve to string if undefined
            self.advance()
            return VarNode(name=tok.value)
        return self.parse_expr()

    def parse_list_literal(self):
        self.expect(TokenType.LBRACKET)
        elements = []
        while not self.at(TokenType.RBRACKET):
            elements.append(self.parse_expr())
            if self.at(TokenType.COMMA):
                self.advance()
        self.expect(TokenType.RBRACKET)
        return ListNode(elements=elements)

    def parse_arb_literal(self):
        self.expect(TokenType.ARB_LIT)
        self.skip_newlines()
        elements = []
        while not self.at(TokenType.RBRACE):
            tag_tok = self.peek()
            if tag_tok.type == TokenType.INT:
                self.advance()
                tag_int = int(tag_tok.value)
                tag_name = ARB_TAG_REVERSE.get(tag_int, "raw")
            else:
                raise ArbPlusError(f"Parse error: expected hex tag in arb literal at line {tag_tok.line}")
            self.expect(TokenType.LPAREN)
            value_expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            elements.append((tag_int, tag_name, value_expr))
            if self.at(TokenType.COMMA):
                self.advance()
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return ArbLitNode(elements=elements)


    def parse_interp_string(self, raw):
        """Parse an interpolated string like "Hello ${name}!" into StringInterpNode."""
        parts = []
        i = 0
        while i < len(raw):
            if raw[i:i+2] == '${':
                depth = 1
                j = i + 2
                while j < len(raw) and depth > 0:
                    if raw[j] == '{': depth += 1
                    elif raw[j] == '}': depth -= 1
                    if depth == 0: break
                    j += 1
                expr_str = raw[i+2:j]
                try:
                    sub_lexer = Lexer(expr_str)
                    sub_tokens = sub_lexer.tokenize()
                    sub_parser = Parser(sub_tokens)
                    expr = sub_parser.parse_expr()
                    parts.append((True, expr))
                except Exception:
                    parts.append((False, '${' + expr_str + '}'))
                i = j + 1
            else:
                lit_start = i
                while i < len(raw) and raw[i:i+2] != '${':
                    i += 1
                parts.append((False, raw[lit_start:i]))
        return StringInterpNode(parts=parts)

    def parse_map_literal(self):
        self.expect(TokenType.MAP_LIT)
        pairs = []
        while not self.at(TokenType.RBRACE) and not self.at(TokenType.EOF):
            self.skip_newlines()
            if self.at(TokenType.RBRACE):
                break
            if self.at(TokenType.STRING):
                key_expr = LiteralNode(value=ArbString(self.advance().value))
            elif self.at(TokenType.IDENT):
                key_expr = LiteralNode(value=ArbString(self.advance().value))
            else:
                key_expr = self.parse_primary()
            self.expect(TokenType.COLON)
            value_expr = self.parse_expr()
            pairs.append((key_expr, value_expr))
            if self.at(TokenType.COMMA):
                self.advance()
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return MapLitNode(pairs=pairs)


# =============================================================================
# ENVIRONMENT AND CLIENT
# =============================================================================


## 06 -- 06_environment.py -- Environment
class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise ArbPlusError(f"Undefined variable: {name}")

    def set(self, name, value, is_const=False):
        if name in self.consts:
            raise ArbPlusError(f"Cannot reassign const variable: {name}")
        if is_const:
            self.consts.add(name)
        self.vars[name] = value

    def set_existing(self, name, value):
        if name in self.vars:
            if name in self.consts:
                raise ArbPlusError(f"Cannot reassign const variable: {name}")
            self.vars[name] = value
            return True
        if self.parent:
            return self.parent.set_existing(name, value)
        return False

    def declare(self, name, value, is_const=False, type_hint=""):
        if is_const:
            self.consts.add(name)
        if type_hint:
            value = arb_coerce(value, type_hint)
        self.vars[name] = value

    def has(self, name):
        if name in self.vars:
            return True
        if self.parent:
            return self.parent.has(name)
        return False

    def has_local(self, name):
        """Check if variable exists in THIS scope only (not parent)."""
        return name in self.vars

    def delete(self, name):
        """Delete a variable from THIS scope only."""
        if name in self.consts:
            self.consts.discard(name)
        if name in self.vars:
            del self.vars[name]
        else:
            raise ArbPlusError(f"Cannot delete variable '{name}': not found in this scope")


# =============================================================================
# ARBPLUS EVALUATOR
# =============================================================================


## 07 -- 07_interp_core.py -- Interpreter core: init/run/execute/eval/call
class Interpreter:
    def __init__(self, script_path="."):
        if script_path != ".":
            self.script_path = os.path.dirname(os.path.abspath(script_path))
        else:
            self.script_path = os.getcwd()
        self.global_env = Environment()
        self.functions = {}
        self.overrides = {}
        self.override_fixed_args = {}  # For argument-aware --OV
        self.builtins = {}
        self.extensions = {}
        self.ext_hooks = {}
        self.declared_shells = set()
        self.declared_imports = set()
        self.metadata = {}
        self.default_colors = {}
        self.err_ov_enabled = False  # Climate
        self.script_args = []
        self.imported_modules = {}
        self._importing = set()
        self.auto_mode = False
        self.auto_input_text = ""
        self._in_repeat_until = False
        self._setup_builtins()

    def run(self, program):
        self.metadata = program.metadata.entries if program.metadata else {}
        if not self.metadata:
            self._print_warning("No #meta block found — running with defaults")
        if program.declarations:
            self.declared_shells = set(program.declarations.uses)
            self.declared_imports = set(program.declarations.imports)
            # Process imports - load .arb module files
            for imp_name in program.declarations.imports:
                self._import_module(imp_name, self.global_env)
        # Read --ErrOV flag
        if program.metadata.entries.get("_err_ov"):
            self.err_ov_enabled = True
        ext_ov = program.metadata.entries.get("_ext_ov", False)
        mod_ov = program.metadata.entries.get("_mod_ov", False)
        chd_ov = program.metadata.entries.get("_chd_ov", False)
        for ov in program.overrides:
            if ov.base_name == "defaults":
                defaults = program.metadata.entries.get("_ov_defaults", {})
                for k, v in defaults.items():
                    # Gate warning/error colors
                    if k in ("warn_fg", "warn_bg", "err_fg", "err_bg") and not self.err_ov_enabled:
                        self._print_warning(f"--OV for {k} ignored: --ErrOV true; not set")
                        continue
                    self.default_colors[k] = v
            elif isinstance(ov, OverrideSwapNode):
                # Handle swap overrides at load time
                pass  # Swaps are handled when executed as statements
            else:
                # Check gating flags for extension/module/child overrides
                target = ov.new_name if ov.fixed_args is None else ov.new_name
                if target in self.extensions and not ext_ov:
                    raise CatchableError(f"Cannot override extension function '{target}' without --ext.ov true;")
                if target in self.imported_modules and not mod_ov:
                    raise CatchableError(f"Cannot override module function '{target}' without --mod.ov true;")
                # child script overrides
                if hasattr(self, '_child_funcs') and target in self._child_funcs and not chd_ov:
                    raise CatchableError(f"Cannot override child script function '{target}' without --chd.ov true;")
                if ov.fixed_args is not None:
                    self.overrides[ov.base_name] = ov.new_name
                    self.override_fixed_args[ov.new_name] = ov.fixed_args
                else:
                    self.overrides[ov.base_name] = ov.new_name
        for name, func in program.functions.items():
            self.functions[name] = func
        try:
            for stmt in program.body:
                self.execute(stmt, self.global_env)
        except ExitException as e:
            return e.code
        return 0

    def execute(self, node, env):
        if node is None:
            return

        if isinstance(node, AssignNode):
            value = self.eval(node.value, env)
            if node.is_const or node.type_hint:
                env.declare(node.name, value, is_const=node.is_const, type_hint=node.type_hint)
            else:
                if env.has(node.name):
                    env.set_existing(node.name, value)
                else:
                    env.declare(node.name, value)

        elif isinstance(node, IfNode):
            for cond, body in node.conditions:
                if arb_truthy(self.eval(cond, env)):
                    for stmt in body:
                        self.execute(stmt, env)
                    return
            for stmt in node.else_body:
                self.execute(stmt, env)

        elif isinstance(node, ForNode):
            if node.iterable is not None:
                iterable_val = self.eval(node.iterable, env)
                items = iterable_val.py() if isinstance(iterable_val, ArbValue) else iterable_val
                for item in items:
                    env.declare(node.var_name, to_arb_value(item))
                    try:
                        for stmt in node.body:
                            self.execute(stmt, env)
                    except BreakException:
                        break
            else:
                start_val = int(self.eval(node.start, env).py())
                end_val = int(self.eval(node.end, env).py())
                step_val = 1
                if node.step:
                    step_val = int(self.eval(node.step, env).py())
                i = start_val
                while (step_val > 0 and i <= end_val) or (step_val < 0 and i >= end_val):
                    env.declare(node.var_name, ArbInt(i))
                    try:
                        for stmt in node.body:
                            self.execute(stmt, env)
                    except BreakException:
                        break
                    i += step_val

        elif isinstance(node, WhileNode):
            while arb_truthy(self.eval(node.condition, env)):
                try:
                    for stmt in node.body:
                        self.execute(stmt, env)
                except BreakException:
                    break

        elif isinstance(node, BreakNode):
            raise BreakException()

        elif isinstance(node, ReturnNode):
            if node.value is None:
                raise ReturnException(ArbNull())
            val = self.eval(node.value, env)
            raise ReturnException(val)

        elif isinstance(node, ExitNode):
            code = 0
            if node.code:
                code = int(self.eval(node.code, env).py())
            raise ExitException(code)

        elif isinstance(node, ExprStmtNode):
            self.eval(node.expr, env)

        elif isinstance(node, SwapNode):
            left_val = env.get(node.left)
            right_val = env.get(node.right)
            env.set_existing(node.left, right_val)
            env.set_existing(node.right, left_val)

        elif isinstance(node, CBlockNode):
            self.execute_c_block(node, env)

        elif isinstance(node, ShellBlockNode):
            self.execute_shell_block(node, env)
        elif isinstance(node, PyBlockNode):
            self.execute_py_block(node, env)
        elif isinstance(node, ForwardDeclNode):
            # Forward declaration: declare with null value
            env.declare(node.name, ArbNull())

        elif isinstance(node, AutoNode):
            # --auto "text" — enable auto input mode with the given text
            self.auto_mode = True
            if node.text is not None:
                val = self.eval(node.text, env) if hasattr(node.text, '__class__') and 'Node' in type(node.text).__name__ else node.text
                self.auto_input_text = arb_to_string(val) if isinstance(val, ArbValue) else str(val)
            else:
                self.auto_input_text = ""
        elif isinstance(node, IncDecNode):
            if not env.has(node.var_name):
                raise ArbPlusError(f"Cannot {node.op} undefined variable: {node.var_name}")
            val = env.get(node.var_name)
            if isinstance(val, ArbString):
                num = float(val.val) if '.' in val.val else int(val.val)
            elif isinstance(val, ArbInt):
                num = val.val
            elif isinstance(val, ArbFloat):
                num = val.val
            else:
                raise ArbPlusError(f"Cannot {node.op} non-numeric variable: {node.var_name}")
            if node.op == "++":
                num += 1
            else:
                num -= 1
            if isinstance(num, float):
                env.set_existing(node.var_name, ArbFloat(num))
            else:
                env.set_existing(node.var_name, ArbInt(num))

        elif isinstance(node, RepeatNode):
            self._in_repeat_until = True
            try:
                while True:
                    try:
                        for stmt in node.body:
                            self.execute(stmt, env)
                    except BreakException:
                        break
                    if arb_truthy(self.eval(node.condition, env)):
                        break
            finally:
                self._in_repeat_until = False

        elif isinstance(node, TryNode):
            try:
                for stmt in node.try_body:
                    self.execute(stmt, env)
            except (ArbPlusError, CatchableError) as e:
                if node.catch_var:
                    catch_env = Environment(env)
                    catch_env.declare(node.catch_var, ArbString(str(e)))
                    for stmt in node.catch_body:
                        self.execute(stmt, catch_env)
                else:
                    raise
            finally:
                for stmt in node.finally_body:
                    self.execute(stmt, env)

        elif isinstance(node, SwitchNode):
            switch_val = self.eval(node.value, env)
            matched = False
            for case_expr, case_body in node.cases:
                case_val = self.eval(case_expr, env)
                if switch_val.py() == case_val.py():
                    for stmt in case_body:
                        self.execute(stmt, env)
                    matched = True
                    break
            if not matched:
                for stmt in node.default_body:
                    self.execute(stmt, env)

        elif isinstance(node, MapAssignNode):
            target = self.eval(node.target, env)
            key = self.eval(node.key, env)
            value = self.eval(node.value, env)
            if isinstance(target, ArbMap):
                target.set(arb_to_string(key), value)
            elif isinstance(target, ArbList):
                idx = int(key.py())
                if 0 <= idx < len(target.val):
                    target.val[idx] = value
            else:
                raise ArbPlusError(f"Cannot assign to index on {target.type_name}")

        elif isinstance(node, OverrideDefaultsNode):
            for k, v in node.defaults.items():
                # Warning/error colors gated by --ErrOV
                if k in ("warn_fg", "warn_bg", "err_fg", "err_bg"):
                    if not self.err_ov_enabled:
                        self._print_warning(f"--OV for {k} ignored: --ErrOV true; not set")
                        continue
                self.default_colors[k] = v

        elif isinstance(node, OverrideNode):
            if node.fixed_args is not None:
                # Argument-aware override: store the fixed args alongside the name mapping
                self.overrides[node.base_name] = node.new_name
                self.override_fixed_args[node.new_name] = node.fixed_args
            else:
                self.overrides[node.base_name] = node.new_name

        elif isinstance(node, OverrideSwapNode):
            # --OV funcA <> funcB — completely swap two functions
            cross_category = False
            # Swap builtins (both in builtins)
            if node.func_a in self.builtins and node.func_b in self.builtins:
                self.builtins[node.func_a], self.builtins[node.func_b] = self.builtins[node.func_b], self.builtins[node.func_a]
            # Swap user functions (both in functions)
            elif node.func_a in self.functions and node.func_b in self.functions:
                self.functions[node.func_a], self.functions[node.func_b] = self.functions[node.func_b], self.functions[node.func_a]
            # Swap extensions (both in extensions)
            elif node.func_a in self.extensions and node.func_b in self.extensions:
                self.extensions[node.func_a], self.extensions[node.func_b] = self.extensions[node.func_b], self.extensions[node.func_a]
            else:
                # Cross-category swap (e.g. builtin <-> user function)
                cross_category = True
                fa = node.func_a
                fb = node.func_b
                # Resolve role-prefixed user function names
                for candidate in [fa, fb]:
                    if "." not in candidate:
                        for fname in self.functions:
                            if fname.endswith("." + candidate):
                                if candidate == fa:
                                    fa = fname
                                else:
                                    fb = fname
                                break
                # Create bidirectional override mappings
                # overrides[base] = new_name means calling new_name invokes base
                self.overrides[fa] = fb  # calling fb invokes fa
                self.overrides[fb] = fa  # calling fa invokes fb
            # For same-category swaps, also update existing override mappings
            if not cross_category:
                a_to_b = None
                b_to_a = None
                for base, new_name in list(self.overrides.items()):
                    if new_name == node.func_a:
                        a_to_b = base
                    if new_name == node.func_b:
                        b_to_a = base
                if a_to_b:
                    self.overrides[a_to_b] = node.func_b
                if b_to_a:
                    self.overrides[b_to_a] = node.func_a

        elif isinstance(node, DelNode):
            if not env.has_local(node.var_name):
                raise ArbPlusError(f"Cannot delete variable '{node.var_name}': not declared in this scope")
            env.delete(node.var_name)

        elif isinstance(node, CleanNode):
            import gc as _gc
            if node.mode == "stop":
                self._gc_enabled = False
            elif node.mode == "restart":
                self._gc_enabled = True
                _gc.collect()
            elif node.mode == "count":
                collected = _gc.collect()
                # Silent operation, but we store the count internally
                self._last_gc_count = collected
            else:
                # Default: collect
                if getattr(self, '_gc_enabled', True):
                    _gc.collect()

        elif isinstance(node, DelegateReturnNode):
            # --F: delegate return to another function
            arg_vals = [self.eval(a, env) for a in node.args]
            kw_vals = {}
            for k, v in node.kwargs.items():
                kw_vals[k] = self.eval(v, env)
            # Look up the function by name
            func_name = node.func_name
            # Check overrides first
            for base, new_name in self.overrides.items():
                if func_name == new_name:
                    func_name = base
                    break
            if func_name not in self.functions:
                # Try stripping role prefix
                if "." in func_name:
                    func_name = func_name.split(".")[-1]
            if func_name not in self.functions:
                raise ArbPlusError(f"Function '{node.func_name}' not defined for --F delegation")
            result = self.call_user_function(func_name, arg_vals, kw_vals, env)
            raise ReturnException(result)

        else:
            raise ArbPlusError(f"Unknown statement node: {type(node).__name__}")

    def eval(self, node, env):
        if isinstance(node, LiteralNode):
            return node.value

        if isinstance(node, VarNode):
            if env.has(node.name):
                return env.get(node.name)
            if node.name in self.builtins:
                return self.call_builtin(node.name, [], {}, env)
            if node.name in self.functions:
                return self.call_user_function(node.name, [], {}, env)
            # Fallback: undefined identifiers become string literals
            # (common in scripting languages for enum-like values)
            return ArbString(node.name)

        if isinstance(node, BinOpNode):
            return self.eval_binop(node, env)

        if isinstance(node, UnaryOpNode):
            operand = self.eval(node.operand, env)
            if node.op == "-":
                py = operand.py()
                if isinstance(py, (int, float)):
                    return ArbInt(-py) if isinstance(py, int) else ArbFloat(-py)
                raise ArbPlusError("Cannot negate non-numeric value")
            if node.op == "not":
                return ArbBool(not arb_truthy(operand))
            raise ArbPlusError(f"Unknown unary op: {node.op}")

        if isinstance(node, CallNode):
            return self.eval_call(node, env)

        if isinstance(node, IndexNode):
            target = self.eval(node.target, env)
            index = self.eval(node.index, env)
            if isinstance(target, ArbMap):
                key = arb_to_string(index)
                val = target.get(key)
                if val is not None:
                    return val
                return ArbString("")  # missing key returns empty string
            idx = int(index.py())
            if isinstance(target, ArbArb):
                return to_arb_value(target.get_decoded(idx))
            items = target.py()
            if idx < 0:
                idx += len(items)
            if 0 <= idx < len(items):
                item = items[idx]
                return item if isinstance(item, ArbValue) else to_arb_value(item)
            raise ArbPlusError(f"Index {idx} out of bounds (len={len(items)})")

        if isinstance(node, TypeCastNode):
            # .type() casting on any expression
            target_val = self.eval(node.target, env)
            type_arg = arb_to_string(self.eval(node.type_arg, env))
            if type_arg == "int":
                py = target_val.py()
                if isinstance(py, str) and not py.lstrip('-').isdigit():
                    raise ArbPlusError(f"Cannot cast '{py}' to int")
                return ArbInt(int(py))
            elif type_arg == "float":
                py = target_val.py()
                if isinstance(py, str):
                    try: float(py)
                    except ValueError: raise ArbPlusError(f"Cannot cast '{py}' to float")
                return ArbFloat(float(py))
            elif type_arg == "string":
                return ArbString(arb_to_string(target_val))
            elif type_arg == "boolean":
                return ArbBool(arb_truthy(target_val))
            else:
                raise ArbPlusError(f"Unknown type for .type(): {type_arg}")

        if isinstance(node, MemberNode):
            # Handle .type member (returns type name as string)
            if node.member == "type":
                target_val = self.eval(node.target, env)
                # If it's a map with a "type" key, return that value instead
                if isinstance(target_val, ArbMap) and target_val.get("type") is not None:
                    return target_val.get("type")
                return ArbString(target_val.type_name if isinstance(target_val, ArbValue) else "unknown")
            if isinstance(node.target, VarNode):
                tn = node.target.name
                if tn == "locale":
                    return self.eval_locale_member(node.member, env)
                if tn == "os":
                    return self.eval_os_member(node.member, env)
            target_val = self.eval(node.target, env)
            if isinstance(target_val, ArbMap):
                val = target_val.get(node.member)
                if val is not None:
                    return val
                return ArbString("")  # missing key returns empty string
            raise ArbPlusError(f"Cannot access member '{node.member}' on {target_val.type_name}")

        if isinstance(node, TernaryNode):
            if arb_truthy(self.eval(node.cond, env)):
                return self.eval(node.then_val, env)
            return self.eval(node.else_val, env)

        if isinstance(node, ArbLitNode):
            arb = ArbArb()
            for tag_int, tag_name, value_expr in node.elements:
                val = self.eval(value_expr, env)
                arb.add(tag_name, val.py())
            return arb

        if isinstance(node, ListNode):
            elements = [self.eval(e, env) for e in node.elements]
            return ArbList(elements)

        if isinstance(node, StringInterpNode):
            parts = []
            for is_expr, content in node.parts:
                if is_expr:
                    # Check if it's a VarNode for an undefined variable
                    if isinstance(content, VarNode) and not env.has(content.name) and content.name not in self.builtins and content.name not in self.functions:
                        parts.append("")
                    else:
                        try:
                            val = self.eval(content, env)
                            parts.append(arb_to_string(val))
                        except ArbPlusError:
                            parts.append("")
                else:
                    parts.append(content)
            result = ''.join(parts)
            return ArbString(result)

        if isinstance(node, MapLitNode):
            pairs = []
            for key_expr, val_expr in node.pairs:
                key = arb_to_string(self.eval(key_expr, env))
                val = self.eval(val_expr, env)
                pairs.append((key, val))
            return ArbMap(pairs)

        raise ArbPlusError(f"Unknown expression node: {type(node).__name__}")

    def eval_binop(self, node, env):
        op = node.op
        if op == "&&":
            left = self.eval(node.left, env)
            if not arb_truthy(left):
                return ArbBool(False)
            return ArbBool(arb_truthy(self.eval(node.right, env)))
        if op == "||":
            left = self.eval(node.left, env)
            if arb_truthy(left):
                return ArbBool(True)
            return ArbBool(arb_truthy(self.eval(node.right, env)))

        left = self.eval(node.left, env)
        right = self.eval(node.right, env)

        lv = left.py()
        rv = right.py()
        # Handle null comparison: null == null is true
        if isinstance(left, ArbValue) and left.type_name == "null":
            if isinstance(right, ArbValue) and right.type_name == "null":
                if op == "==": return ArbBool(True)
                if op == "!=": return ArbBool(False)
            else:
                if op == "==": return ArbBool(False)
                if op == "!=": return ArbBool(True)
        if isinstance(right, ArbValue) and right.type_name == "null":
            if op == "==": return ArbBool(False)
            if op == "!=": return ArbBool(True)
        # Cross-type comparison: coerce to comparable types
        if type(lv) != type(rv):
            # If one is string and other is number, compare as strings
            if isinstance(lv, str) or isinstance(rv, str):
                lv = arb_to_string(left)
                rv = arb_to_string(right)
            # If one is float and other is int, Python handles it
        if op == "==": return ArbBool(lv == rv)
        if op == "!=": return ArbBool(lv != rv)
        if op == "<": return ArbBool(lv < rv)
        if op == "<=": return ArbBool(lv <= rv)
        if op == ">": return ArbBool(lv > rv)
        if op == ">=": return ArbBool(lv >= rv)
        if op == "..": return ArbString(arb_to_string(left) + arb_to_string(right))

        if op == "+":
            if isinstance(lv, str) or isinstance(rv, str):
                return ArbString(arb_to_string(left) + arb_to_string(right))
            if isinstance(lv, float) or isinstance(rv, float):
                return ArbFloat(lv + rv)
            return ArbInt(lv + rv)
        if op == "-":
            if isinstance(lv, float) or isinstance(rv, float):
                return ArbFloat(lv - rv)
            return ArbInt(lv - rv)
        if op == "*":
            if isinstance(lv, str) and isinstance(rv, int):
                return ArbString(lv * rv)
            if isinstance(lv, float) or isinstance(rv, float):
                return ArbFloat(lv * rv)
            return ArbInt(lv * rv)
        if op == "/":
            if rv == 0: raise ArbPlusError("Division by zero")
            return ArbFloat(lv / rv)
        if op == "%":
            if rv == 0: raise ArbPlusError("Modulo by zero")
            return ArbInt(lv % rv)
        if op == "^":
            if isinstance(lv, float) or isinstance(rv, float) or rv < 0:
                return ArbFloat(lv ** rv)
            return ArbInt(lv ** rv)
        raise ArbPlusError(f"Unknown operator: {op}")

    def eval_call(self, node, env):
        name = node.name
        
        # Handle .type() calls varName.type(typeName)
        if ".type" in name and name.endswith(".type"):
            base_name = name[:-5]  # remove ".type"
            if base_name in self.builtins or base_name in self.functions:
                pass  # let it fall through to normal handling
            else:
                # Evaluate the variable, then cast to the requested type
                target_val = self.eval(VarNode(name=base_name), env) if env.has(base_name) else self.eval(VarNode(name=base_name), env)
                type_arg = arb_to_string(self.eval(node.args[0], env)) if node.args else "string"
                try:
                    if type_arg == "int":
                        py = target_val.py()
                        if isinstance(py, str) and not py.lstrip('-').isdigit():
                            raise ArbPlusError(f"Cannot cast '{py}' to int")
                        return ArbInt(int(py))
                    elif type_arg == "float":
                        py = target_val.py()
                        if isinstance(py, str):
                            try: float(py)
                            except ValueError: raise ArbPlusError(f"Cannot cast '{py}' to float")
                        return ArbFloat(float(py))
                    elif type_arg == "string":
                        return ArbString(arb_to_string(target_val))
                    elif type_arg == "boolean":
                        return ArbBool(arb_truthy(target_val))
                    else:
                        raise ArbPlusError(f"Unknown type for .type(): {type_arg}")
                except ArbPlusError:
                    raise
                except Exception as e:
                    raise ArbPlusError(f"Type cast error: {e}")
        
        # Handle .type() on arbitrary expressions (e.g. (expr).type(string))
        # Also handle member calls on ArbColoredString, fetch results, etc.

        # Override: --OV BaseName NewName means calling NewName invokes BaseName
        for base, new_name in self.overrides.items():
            if name == new_name:
                name = base
                # If this is an argument-aware override, prepend fixed args
                if name in self.override_fixed_args and self.override_fixed_args[name]:
                    fixed = [self.eval(a, env) for a in self.override_fixed_args[name]]
                    args = fixed + [self.eval(a, env) for a in node.args]
                else:
                    args = [self.eval(a, env) for a in node.args]
                kwargs = {k: self.eval(v, env) for k, v in node.kwargs.items()}
                break
        else:
            args = [self.eval(a, env) for a in node.args]
            kwargs = {k: self.eval(v, env) for k, v in node.kwargs.items()}

        if name in self.functions:
            return self.call_user_function(name, args, kwargs, env)
        # For locally-defined functions, try stripping role prefix
        if "." in name:
            func_name = name.split(".")[-1]
            if func_name in self.functions:
                return self.call_user_function(func_name, args, kwargs, env)
        if name in self.builtins:
            return self.call_builtin(name, args, kwargs, env)
        if name in self.extensions:
            result = self.extensions[name](args, kwargs)
            return result if isinstance(result, ArbValue) else to_arb_value(result)
        if name.startswith("ext."):
            ext_name = name[4:]
            if ext_name in self.extensions:
                result = self.extensions[ext_name](args, kwargs)
                return result if isinstance(result, ArbValue) else to_arb_value(result)
        raise ArbPlusError(f"Unknown function: {name}")

    def call_user_function(self, name, args, kwargs, env):
        func = self.functions[name]
        func_env = Environment(self.global_env)
        for i, (pname, ptype) in enumerate(func.params):
            if i < len(args):
                val = args[i]
                if ptype:
                    val = arb_coerce(val, ptype)
                func_env.declare(pname, val)
            else:
                func_env.declare(pname, ArbString(""))
        try:
            for stmt in func.body:
                self.execute(stmt, func_env)
        except ReturnException as e:
            return e.value if e.value else ArbString("")
        return ArbString("")


## 08 -- 08_interp_blocks_and_builtins_a.py -- Interpreter: c/py/shell blocks + collection/math/string builtins
    def execute_c_block(self, node, env):
        compiler = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
        if not compiler:
            raise ArbPlusError("C block requires a C compiler (gcc/cc/clang) but none was found on PATH. "
                             "Install a C compiler to use c{ } blocks.")
        # Addition 27: load from file if $!pathVar was used
        if node.file_ref:
            path_var = node.file_ref
            if not env.has(path_var):
                raise ArbPlusError(f"c{{$!{path_var}}}: variable '{path_var}' is not defined")
            path = arb_to_string(env.get(path_var))
            full_path = self._resolve_path(path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                raise ArbPlusError(f"c{{$!{path_var}}}: file not found: {path}")
            with open(full_path, 'r') as f:
                node_code = f.read()
        else:
            node_code = node.code
        code = self._interpolate_vars(node_code, env)
        import tempfile
        # If the code already has its own main() function, don't wrap it
        has_main = bool(re.search(r'\bint\s+main\s*\(', code))
        with tempfile.NamedTemporaryFile(suffix='.c', mode='w', delete=False) as f:
            if has_main:
                f.write(code)
            else:
                f.write("#include <stdio.h>\nint main() {\n")
                f.write(code)
                f.write("\nreturn 0;\n}\n")
            c_file = f.name
        exe_file = c_file.replace('.c', '')
        try:
            result = subprocess.run([compiler, c_file, '-o', exe_file], capture_output=True, text=True)
            if result.returncode != 0:
                raise ArbPlusError(f"C compilation failed:\n{result.stderr}")
            result = subprocess.run([exe_file], capture_output=True, text=True)
            if result.stdout:
                print(result.stdout, end='')
        finally:
            for f in [c_file, exe_file]:
                if os.path.exists(f):
                    os.unlink(f)

    def execute_shell_block(self, node, env):
        # Addition 27: load from file if $!pathVar was used
        if node.file_ref:
            path_var = node.file_ref
            if not env.has(path_var):
                raise ArbPlusError(f"{node.shell_type}{{$!{path_var}}}: variable '{path_var}' is not defined")
            path = arb_to_string(env.get(path_var))
            full_path = self._resolve_path(path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                raise ArbPlusError(f"{node.shell_type}{{$!{path_var}}}: file not found: {path}")
            with open(full_path, 'r') as f:
                node_code = f.read()
        else:
            node_code = node.code
        code = self._interpolate_vars(node_code, env)
        if node.shell_type == 'cmd':
            if platform.system() != "Windows":
                result = subprocess.run(["sh", "-c", code], capture_output=True, text=True)
            else:
                # sh/cmd is correct, do not switch (I don't know why though)
                result = subprocess.run(["cmd", "/c", code], capture_output=True, text=True)
        elif node.shell_type == 'ps':
            ps = shutil.which("powershell") or shutil.which("pwsh")
            if not ps:
                result = subprocess.run(["sh", "-c", code], capture_output=True, text=True)
            else:
                result = subprocess.run([ps, "-Command", code], capture_output=True, text=True)
        else:
            result = subprocess.run(["sh", "-c", code], capture_output=True, text=True)
        output = result.stdout.strip()
        if output:
            print(output)
        return ArbString(output)

    def execute_py_block(self, node, env):
        # Addition 27: load from file if $!pathVar was used
        if node.file_ref:
            path_var = node.file_ref
            if not env.has(path_var):
                raise ArbPlusError(f"py{{$!{path_var}}}: variable '{path_var}' is not defined")
            path_val = env.get(path_var)
            path = arb_to_string(path_val)
            full_path = self._resolve_path(path)
            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                raise ArbPlusError(f"py{{$!{path_var}}}: file not found: {path}")
            with open(full_path, 'r') as f:
                code = f.read()
        else:
            code = node.code

        # Fix indentation: read_raw_block().strip() removes leading whitespace
        # from the first line only, causing indentation mismatch. Re-indent.
        lines = code.split('\n')
        if len(lines) > 1:
            # Find min indentation from non-first lines that aren't empty
            min_indent = 999
            for line in lines[1:]:
                if line.strip():
                    stripped = len(line) - len(line.lstrip())
                    min_indent = min(min_indent, stripped)
            if min_indent > 0 and min_indent < 999:
                # Add the missing indent to the first line
                lines[0] = ' ' * min_indent + lines[0]
                # Remove common indent from all lines
                lines = [l[min_indent:] if len(l) >= min_indent else l for l in lines]
        code = '\n'.join(lines)
        code = self._interpolate_vars(code, env)

        # Enforce standard-library-only restriction
        self._check_py_imports(code)

        # Build Python namespace from ArbPlus variables
        py_ns = {'__builtins__': __builtins__}
        scope = env
        while scope:
            for name, val in scope.vars.items():
                if name not in py_ns:
                    py_ns[name] = self._arb_to_py(val)
            scope = scope.parent

        # Execute
        old_stdout = sys.stdout
        captured = []
        class CaptureStdout:
            def write(self, text):
                captured.append(text)
            def flush(self):
                pass
        sys.stdout = CaptureStdout()
        result_val = None
        try:
            exec(code, py_ns)
        except Exception as e:
            sys.stdout = old_stdout
            raise ArbPlusError(f"py{{ }} block error: {e}")
        finally:
            sys.stdout = old_stdout

        # Print captured stdout
        output = ''.join(captured)
        if output:
            print(output, end='')

        # Sync variables back from Python namespace to ArbPlus
        scope = env
        while scope:
            for name in list(scope.vars.keys()):
                if name in py_ns:
                    scope.vars[name] = self._py_to_arb(py_ns[name])
            scope = scope.parent

        # Return last expression result if there's a 'result' variable
        if 'result' in py_ns:
            return self._py_to_arb(py_ns['result'])
        return ArbString(output)

    _STDLIB_MODULES = {
        'math', 'json', 're', 'datetime', 'os', 'sys', 'random',
        'string', 'collections', 'itertools', 'functools', 'typing',
        'io', 'pathlib', 'hashlib', 'base64', 'binascii', 'struct',
        'abc', 'argparse', 'csv', 'textwrap', 'shutil', 'tempfile',
        'time', 'calendar', 'decimal', 'fractions', 'statistics',
        'bisect', 'heapq', 'queue', 'enum', 'dataclasses', 'copy',
        'pprint', 'traceback', 'warnings', 'logging', 'sqlite3',
        'xml', 'html', 'urllib', 'socket', 'select', 'signal',
        'codecs', 'unicodedata', 'stringprep', 'difflib', 'inspect',
        'ast', 'dis', 'compileall', 'tokenize', 'keyword', 'operator',
        'numbers', 'contextlib', 'glob', 'fnmatch', 'linecache',
        'mailbox', 'mimetypes', 'plistlib', 'secrets', 'uuid',
        'weakref', 'types', 'array', 'mmap', 'ctypes',
        'multiprocessing', 'threading', 'concurrent',
        'unittest', 'doctest', 'test',
    }

    def _check_py_imports(self, code):
        """Scan py{} block for import statements and reject third-party packages."""
        import_lines = []
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                import_lines.append(stripped)

        for line in import_lines:
            if line.startswith('import '):
                modules = line[7:].split(',')
                for m in modules:
                    mod = m.strip().split('.')[0]
                    if mod not in self._STDLIB_MODULES:
                        raise ArbPlusError(f"py{{ }} block: third-party import '{mod}' is not allowed. "
                                          f"Only Python standard-library modules may be used in py{{ }} blocks. "
                                          f"Use a proper ArbPlus extension for third-party packages.")
            elif line.startswith('from '):
                mod = line[5:].split(' ')[0].split('.')[0]
                if mod not in self._STDLIB_MODULES:
                    raise ArbPlusError(f"py{{ }} block: third-party import '{mod}' is not allowed. "
                                      f"Only Python standard-library modules may be used in py{{ }} blocks. "
                                      f"Use a proper ArbPlus extension for third-party packages.")

    def _arb_to_py(self, val):
        """Convert ArbPlus value to native Python value."""
        if isinstance(val, ArbNull):
            return None
        if isinstance(val, ArbInt):
            return val.val
        if isinstance(val, ArbFloat):
            return val.val
        if isinstance(val, ArbString):
            return val.val
        if isinstance(val, ArbBool):
            return val.val
        if isinstance(val, ArbList):
            return [self._arb_to_py(v) for v in val.val]
        if isinstance(val, ArbMap):
            return {k: self._arb_to_py(v) for k, v in val.val}
        if isinstance(val, ArbValue):
            return {'type': val.type_name, 'val': val.val}
        return str(val)

    def _py_to_arb(self, val):
        """Convert native Python value to ArbPlus value."""
        if val is None:
            return ArbNull()
        if isinstance(val, bool):
            return ArbBool(val)
        if isinstance(val, int):
            return ArbInt(val)
        if isinstance(val, float):
            return ArbFloat(val)
        if isinstance(val, str):
            return ArbString(val)
        if isinstance(val, list):
            return ArbList([self._py_to_arb(v) for v in val])
        if isinstance(val, dict):
            return ArbMap([(k, self._py_to_arb(v)) for k, v in val.items()])
        return ArbString(str(val))


    # ── List operations (Addition 48) ──────────────────────────────
    def _b_append(self, args, kwargs, env):
        """append(list, item) — add item to end of list (mutates and returns list)."""
        if not args:
            raise ArbPlusError("append() requires a list and an item")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("append() first argument must be a list")
        for item in args[1:]:
            lst.val.append(item)
        return lst

    def _b_prepend(self, args, kwargs, env):
        """prepend(list, item) — add item to beginning of list (mutates and returns list)."""
        if not args:
            raise ArbPlusError("prepend() requires a list and an item")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("prepend() first argument must be a list")
        for item in reversed(args[1:]):
            lst.val.insert(0, item)
        return lst

    def _b_insert(self, args, kwargs, env):
        """insert(list, index, item) — insert item at index (mutates and returns list)."""
        if len(args) < 3:
            raise ArbPlusError("insert() requires a list, index, and item")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("insert() first argument must be a list")
        idx = int(args[1].py())
        if idx < 0:
            idx = max(0, len(lst.val) + idx)
        lst.val.insert(idx, args[2])
        return lst

    def _b_removeAt(self, args, kwargs, env):
        """removeAt(list, index) — remove and return item at index."""
        if len(args) < 2:
            raise ArbPlusError("removeAt() requires a list and an index")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("removeAt() first argument must be a list")
        idx = int(args[1].py())
        if idx < 0:
            idx = len(lst.val) + idx
        if idx < 0 or idx >= len(lst.val):
            raise ArbPlusError(f"removeAt() index {idx} out of range (0-{len(lst.val)-1})")
        removed = lst.val.pop(idx)
        return removed

    def _b_pop(self, args, kwargs, env):
        """pop(list) — remove and return last item from list."""
        if not args:
            raise ArbPlusError("pop() requires a list")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("pop() first argument must be a list")
        if not lst.val:
            raise ArbPlusError("pop() list is empty")
        return lst.val.pop()

    def _b_shift(self, args, kwargs, env):
        """shift(list) — remove and return first item from list."""
        if not args:
            raise ArbPlusError("shift() requires a list")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("shift() first argument must be a list")
        if not lst.val:
            raise ArbPlusError("shift() list is empty")
        return lst.val.pop(0)

    def _b_reverse(self, args, kwargs, env):
        """reverse(list|string) — reverse a list or string."""
        if not args:
            raise ArbPlusError("reverse() requires a list or string")
        v = args[0]
        if isinstance(v, ArbList):
            return ArbList(list(reversed(v.val)))
        return ArbString(arb_to_string(v)[::-1])

    def _b_sort(self, args, kwargs, env):
        """sort(list) — return a sorted copy of the list."""
        if not args:
            raise ArbPlusError("sort() requires a list")
        v = args[0]
        if isinstance(v, ArbList):
            try:
                sorted_vals = sorted(v.val, key=lambda x: x.py() if isinstance(x, ArbValue) else x)
            except TypeError:
                sorted_vals = sorted(v.val, key=lambda x: arb_to_string(x))
            return ArbList(sorted_vals)
        raise ArbPlusError("sort() first argument must be a list")

    def _b_indexOf(self, args, kwargs, env):
        """indexOf(list|string, item) — return index of first match, or -1."""
        if len(args) < 2:
            raise ArbPlusError("indexOf() requires a collection and an item")
        coll = args[0]
        target = args[1]
        if isinstance(coll, ArbList):
            for i, item in enumerate(coll.val):
                if _arb_equals(item, target):
                    return ArbInt(i)
            return ArbInt(-1)
        s = arb_to_string(coll)
        t = arb_to_string(target)
        idx = s.find(t)
        return ArbInt(idx)

    def _b_includes(self, args, kwargs, env):
        """includes(list|string, item) — check if collection contains item."""
        if len(args) < 2:
            raise ArbPlusError("includes() requires a collection and an item")
        coll = args[0]
        target = args[1]
        if isinstance(coll, ArbList):
            for item in coll.val:
                if _arb_equals(item, target):
                    return ArbBool(True)
            return ArbBool(False)
        return ArbBool(arb_to_string(target) in arb_to_string(coll))

    def _b_slice(self, args, kwargs, env):
        """slice(list|string, start, end) — return a slice from start to end (exclusive)."""
        if len(args) < 2:
            raise ArbPlusError("slice() requires a collection and a start index")
        coll = args[0]
        start = int(args[1].py()) if len(args) > 1 else 0
        end = int(args[2].py()) if len(args) > 2 else None
        if isinstance(coll, ArbList):
            return ArbList(coll.val[start:end])
        s = arb_to_string(coll)
        return ArbString(s[start:end])

    def _b_flatten(self, args, kwargs, env):
        """flatten(list) — flatten one level of nesting."""
        if not args:
            raise ArbPlusError("flatten() requires a list")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("flatten() first argument must be a list")
        result = []
        for item in lst.val:
            if isinstance(item, ArbList):
                result.extend(item.val)
            else:
                result.append(item)
        return ArbList(result)

    def _b_range(self, args, kwargs, env):
        """range(n) or range(start, end, step) — generate a list of integers."""
        if not args:
            raise ArbPlusError("range() requires at least one argument")
        if len(args) == 1:
            n = int(args[0].py())
            return ArbList([ArbInt(i) for i in range(max(0, n))])
        start = int(args[0].py())
        end = int(args[1].py())
        step = int(args[2].py()) if len(args) > 2 else 1
        return ArbList([ArbInt(i) for i in range(start, end, step)])

    def _b_foreach(self, args, kwargs, env):
        """foreach(list, fn) — call fn(item, index) for each item. fn is a string name."""
        if len(args) < 2:
            raise ArbPlusError("foreach() requires a list and a function name")
        lst = args[0]
        if not isinstance(lst, ArbList):
            raise ArbPlusError("foreach() first argument must be a list")
        fn_name = arb_to_string(args[1])
        for i, item in enumerate(lst.val):
            self.call_user_function(fn_name, [item, ArbInt(i)], {}, env)
        return lst

    # ── Math operations (Addition 48) ───────────────────────────────
    def _b_abs(self, args, kwargs, env):
        """abs(n) — absolute value."""
        if not args:
            raise ArbPlusError("abs() requires a number")
        v = args[0].py()
        if isinstance(v, int):
            return ArbInt(abs(v))
        return ArbFloat(abs(float(v)))

    def _b_round(self, args, kwargs, env):
        """round(n, decimals: 0) — round a number to optional decimal places."""
        if not args:
            raise ArbPlusError("round() requires a number")
        v = float(args[0].py())
        decimals = int(kwargs.get("decimals", ArbInt(0)).py()) if "decimals" in kwargs else 0
        if decimals <= 0:
            return ArbInt(round(v))
        return ArbFloat(round(v, decimals))

    def _b_floor(self, args, kwargs, env):
        """floor(n) — round down to nearest integer."""
        if not args:
            raise ArbPlusError("floor() requires a number")
        return ArbInt(int(float(args[0].py()) // 1))

    def _b_ceil(self, args, kwargs, env):
        """ceil(n) — round up to nearest integer."""
        if not args:
            raise ArbPlusError("ceil() requires a number")
        import math
        return ArbInt(math.ceil(float(args[0].py())))

    def _b_min(self, args, kwargs, env):
        """min(a, b, ...) or min(list) — return the minimum value."""
        if not args:
            raise ArbPlusError("min() requires at least one argument")
        if len(args) == 1 and isinstance(args[0], ArbList):
            vals = [a.py() for a in args[0].val]
        else:
            vals = [a.py() for a in args]
        if not vals:
            raise ArbPlusError("min() of empty collection")
        result = min(vals)
        if isinstance(result, int):
            return ArbInt(result)
        return ArbFloat(result)

    def _b_max(self, args, kwargs, env):
        """max(a, b, ...) or max(list) — return the maximum value."""
        if not args:
            raise ArbPlusError("max() requires at least one argument")
        if len(args) == 1 and isinstance(args[0], ArbList):
            vals = [a.py() for a in args[0].val]
        else:
            vals = [a.py() for a in args]
        if not vals:
            raise ArbPlusError("max() of empty collection")
        result = max(vals)
        if isinstance(result, int):
            return ArbInt(result)
        return ArbFloat(result)

    def _b_sum(self, args, kwargs, env):
        """sum(list) — sum all numeric elements."""
        if not args:
            raise ArbPlusError("sum() requires a list")
        lst = args[0]
        if isinstance(lst, ArbList):
            vals = [a.py() for a in lst.val]
        else:
            vals = [lst.py()]
        if not vals:
            return ArbInt(0)
        result = sum(vals)
        if isinstance(result, int):
            return ArbInt(result)
        return ArbFloat(result)

    def _b_clamp(self, args, kwargs, env):
        """clamp(n, min, max) — constrain n to [min, max] range."""
        if len(args) < 3:
            raise ArbPlusError("clamp() requires value, min, and max")
        v = float(args[0].py())
        lo = float(args[1].py())
        hi = float(args[2].py())
        result = max(lo, min(v, hi))
        if isinstance(args[0].py(), int):
            return ArbInt(int(result))
        return ArbFloat(result)

    # ── String operations (Addition 48) ─────────────────────────────
    def _b_repeat(self, args, kwargs, env):
        """repeat(str, n) — repeat string n times."""
        if len(args) < 2:
            raise ArbPlusError("repeat() requires a string and a count")
        s = arb_to_string(args[0])
        n = int(args[1].py())
        return ArbString(s * max(0, n))

    def _b_startsWith(self, args, kwargs, env):
        """startsWith(str, prefix) — check if string starts with prefix."""
        if len(args) < 2:
            raise ArbPlusError("startsWith() requires a string and a prefix")
        return ArbBool(arb_to_string(args[0]).startswith(arb_to_string(args[1])))

    def _b_endsWith(self, args, kwargs, env):
        """endsWith(str, suffix) — check if string ends with suffix."""
        if len(args) < 2:
            raise ArbPlusError("endsWith() requires a string and a suffix")
        return ArbBool(arb_to_string(args[0]).endswith(arb_to_string(args[1])))

    def _b_capitalize(self, args, kwargs, env):
        """capitalize(str) — capitalize first letter, lowercase rest."""
        if not args:
            raise ArbPlusError("capitalize() requires a string")
        s = arb_to_string(args[0])
        return ArbString(s[:1].upper() + s[1:].lower() if s else s)

    def _b_titleCase(self, args, kwargs, env):
        """titleCase(str) — capitalize first letter of each word."""
        if not args:
            raise ArbPlusError("titleCase() requires a string")
        return ArbString(arb_to_string(args[0]).title())

    def _b_padLeft(self, args, kwargs, env):
        """padLeft(str, len, char: " ") — pad string on left to given length."""
        if len(args) < 2:
            raise ArbPlusError("padLeft() requires a string and a length")
        s = arb_to_string(args[0])
        n = int(args[1].py())
        ch = arb_to_string(args[2]) if len(args) > 2 else " "
        if len(s) >= n:
            return ArbString(s)
        return ArbString(ch[0] * (n - len(s)) + s)

    def _b_padRight(self, args, kwargs, env):
        """padRight(str, len, char: " ") — pad string on right to given length."""
        if len(args) < 2:
            raise ArbPlusError("padRight() requires a string and a length")
        s = arb_to_string(args[0])
        n = int(args[1].py())
        ch = arb_to_string(args[2]) if len(args) > 2 else " "
        if len(s) >= n:
            return ArbString(s)
        return ArbString(s + ch[0] * (n - len(s)))

    def _b_replaceAt(self, args, kwargs, env):
        """replaceAt(str, index, replacement) — replace character at index with new string."""
        if len(args) < 3:
            raise ArbPlusError("replaceAt() requires a string, index, and replacement")
        s = arb_to_string(args[0])
        idx = int(args[1].py())
        repl = arb_to_string(args[2])
        if idx < 0:
            idx = len(s) + idx
        if idx < 0 or idx >= len(s):
            raise ArbPlusError(f"replaceAt() index {idx} out of range")
        return ArbString(s[:idx] + repl + s[idx+1:])

    def _b_format(self, args, kwargs, env):
        """format(template, ...args) — replace {0}, {1}, ... in template with args."""
        if not args:
            raise ArbPlusError("format() requires a template string")
        template = arb_to_string(args[0])
        rest = args[1:]
        for i, a in enumerate(rest):
            template = template.replace("{" + str(i) + "}", arb_to_string(a))
        return ArbString(template)

    def _b_charCodeAt(self, args, kwargs, env):
        """charCodeAt(str, index) — return Unicode code point of character at index."""
        if len(args) < 2:
            raise ArbPlusError("charCodeAt() requires a string and an index")
        s = arb_to_string(args[0])
        idx = int(args[1].py())
        if idx < 0 or idx >= len(s):
            raise ArbPlusError(f"charCodeAt() index {idx} out of range")
        return ArbInt(ord(s[idx]))

    def _b_fromChar(self, args, kwargs, env):
        """fromChar(code) — convert Unicode code point to a single-character string."""
        if not args:
            raise ArbPlusError("fromChar() requires a code point")
        return ArbString(chr(int(args[0].py())))

    def _resolve_path(self, path):
        """Resolve a file path using ./ and ../ relative rules."""
        if os.path.isabs(path):
            return path
        base = getattr(self, 'script_path', os.getcwd())
        return os.path.normpath(os.path.join(base, path))

    def _interpolate_vars(self, text, env):
        def replacer(match):
            var_name = match.group(1)
            if env.has(var_name):
                return arb_to_string(env.get(var_name))
            return match.group(0)
        return re.sub(r'\$\{(\w+)\}', replacer, text)


    # =====================================================================
    # BUILT-IN FUNCTIONS
    # =====================================================================

    def _setup_builtins(self):
        self.builtins = {
            "add": self._b_add, "sub": self._b_sub, "mul": self._b_mul,
            "div": self._b_div, "mod": self._b_mod, "pow": self._b_pow,
            "concat": self._b_concat, "len": self._b_len,
            "upper": self._b_upper, "lower": self._b_lower, "trim": self._b_trim,
            "split": self._b_split, "join": self._b_join, "substr": self._b_substr,
            "replace": self._b_replace, "contains": self._b_contains,
            "print": self._b_print, "input": self._b_input,
            "swap": self._b_swap,
            "toInt": self._b_toint, "toFloat": self._b_tofloat,
            "toString": self._b_tostring, "toBool": self._b_tobool,
            "typeof": self._b_typeof,
            "file": self._b_file, "file.read": self._b_readfile, "file.exist": self._b_fileexists,
            "file.write": self._b_writefile, "file.build": self._b_buildfile,
            "encodeImage": self._b_encode_image, "decodeImage": self._b_decode_image,
            "openMedia": self._b_open_media, "openBrowser": self._b_open_browser,
            "addr": self._b_addr, "txtRC": self._b_txtrc,
            "addr.hex": self._b_addr_hex, "addr.binary": self._b_addr_binary,
            "addr.meta": self._b_addr_meta,
            "dir.list": self._b_dir_list, "dir.name": self._b_dir_name,
            "dir.make": self._b_dir_make, "dir.del": self._b_dir_del,
            "snap.time": self._b_snap_time, "count.time": self._b_count_time,
            "var": self._b_var,
            "wait": self._b_wait, "cs": self._b_cs,
            "locale.prf": self._b_locale_prf, "locale.check": self._b_locale_check,
            "locale.alt": self._b_locale_alt, "locale.cur": self._b_locale_cur,
            "os.Battery": self._b_battery, "os.Network": self._b_network,
            "os.Screen": self._b_screen, "os.CS": self._b_cs,
            "os.Name": self._b_os_name, "os.Version": self._b_os_version,
            # Lowercase aliases for backward compat
            "os.battery": self._b_battery, "os.network": self._b_network,
            "os.screen": self._b_screen,
            "os.name": self._b_os_name, "os.version": self._b_os_version,
            "loadExt": self._b_load_ext,
            "random": self._b_random, "randInt": self._b_randint,
            "random.seed": self._b_random_seed,
            "bindKey": self._b_bindkey,
            "open.url": self._b_open_url, "open.app": self._b_open_app,
            "args": self._b_args, "env": self._b_env,
            "map": self._b_map,
            "keys": self._b_keys, "values": self._b_values,
            "has": self._b_has,
            "match": self._b_match,
            "fetch.url": self._b_fetch_url,
            "del": self._b_del,
            "color": self._b_color,
            # For already opened tabs
            "open.page": self._b_open_page,
            "extMeta": self._b_ext_meta,
            "meta": self._b_meta,
            "run.arb": self._b_run_arb,
            "dl.url": self._b_dl_url,
            # Aliases for convenience naming used in examples
            "writeFile": self._b_writefile,
            "buildFile": self._b_buildfile,
            "readFile": self._b_readfile,
            "fileExists": self._b_fileexists,
            # Addition 48 — List operations
            "append": self._b_append,
            "prepend": self._b_prepend,
            "insert": self._b_insert,
            "removeAt": self._b_removeAt,
            "pop": self._b_pop,
            "shift": self._b_shift,
            "reverse": self._b_reverse,
            "sort": self._b_sort,
            "indexOf": self._b_indexOf,
            "includes": self._b_includes,
            "slice": self._b_slice,
            "flatten": self._b_flatten,
            "range": self._b_range,
            "foreach": self._b_foreach,
            # Addition 48 — Math operations
            "abs": self._b_abs,
            "round": self._b_round,
            "floor": self._b_floor,
            "ceil": self._b_ceil,
            "min": self._b_min,
            "max": self._b_max,
            "sum": self._b_sum,
            "clamp": self._b_clamp,
            # Addition 48 — String operations
            "replicate": self._b_repeat,
            "startsWith": self._b_startsWith,
            "endsWith": self._b_endsWith,
            "capitalize": self._b_capitalize,
            "titleCase": self._b_titleCase,
            "padLeft": self._b_padLeft,
            "padRight": self._b_padRight,
            "replaceAt": self._b_replaceAt,
            "format": self._b_format,
            "charCodeAt": self._b_charCodeAt,
            "fromChar": self._b_fromChar,
        }


## 09 -- 09_interp_builtins_b.py -- Interpreter: more builtins + builtin dispatch table
    def _b_random(self, args, kwargs, env):
        import random as _random
        if not hasattr(self, '_rng'):
            self._rng = _random.Random()
        return ArbFloat(self._rng.random())

    def _b_randint(self, args, kwargs, env):
        import random as _random
        if not hasattr(self, '_rng'):
            self._rng = _random.Random()
        lo = int(args[0].py())
        hi = int(args[1].py())
        return ArbInt(self._rng.randint(lo, hi))

    def _b_random_seed(self, args, kwargs, env):
        import random as _random
        seed = int(args[0].py())
        self._rng = _random.Random(seed)
        return ArbBool(True)

    # Addition 2: Key bindings (simplified - stores bindings, no event loop)
    def _b_bindkey(self, args, kwargs, env):
        """bindKey("KEY", "funcName") — register a key binding.
        Works both inside repeat/until loops AND as a standalone statement.
        When used standalone, it registers the binding and returns true.
        The binding is checked during repeat/until loops and also via
        KeyboardInterrupt/SignalHandler outside loops.
        """
        if not hasattr(self, '_key_bindings'):
            self._key_bindings = {}
        key = arb_to_string(args[0]).upper()
        func_name = arb_to_string(args[1])
        self._key_bindings[key] = func_name
        
        # For standalone use outside repeat/until: install signal handlers
        in_loop = getattr(self, '_in_repeat_until', False)
        if not in_loop:
            import signal
            try:
                # Map common key bindings to signals
                if key in ("CTRL+C", "^C"):
                    # Install handler that calls the function or exits
                    def sigint_handler(signum, frame):
                        if func_name in ("quit", "exit"):
                            raise ExitException(0)
                        elif func_name in self.functions:
                            self.call_user_function(func_name, [], {}, env)
                        elif func_name in self.builtins:
                            self.call_builtin(func_name, [], {}, env)
                        # Re-raise as KeyboardInterrupt if function doesn't exit
                        raise KeyboardInterrupt()
                    signal.signal(signal.SIGINT, sigint_handler)
                elif key in ("CTRL+Z", "^Z"):
                    # Don't override SIGTSTP by default, just register
                    pass
                # Register keyboard hook via threading for other keys
                self._install_key_listener(key, func_name, env)
            except (OSError, ValueError):
                pass  # Not in main thread or signal not available
        
        return ArbBool(True)

    def _make_signal_handler(self, func_name, env):
        def handler(signum, frame):
            if func_name == "quit" or func_name == "exit":
                raise ExitException(0)
            elif func_name in self.functions:
                self.call_user_function(func_name, [], {}, env)
            elif func_name in self.builtins:
                self.call_builtin(func_name, [], {}, env)
        return handler

    def _install_key_listener(self, key, func_name, env):
        """Install a keyboard listener for standalone bindKey outside loops."""
        try:
            # Try to use keyboard library if available
            import keyboard
            def callback():
                if func_name == "quit" or func_name == "exit":
                    raise ExitException(0)
                elif func_name in self.functions:
                    self.call_user_function(func_name, [], {}, env)
                elif func_name in self.builtins:
                    self.call_builtin(func_name, [], {}, env)
            keyboard.add_hotkey(key.lower().replace("ctrl+", "ctrl+"), callback)
        except ImportError:
            pass  # keyboard library not available — binding still registered

    # Addition 2: open.url and open.app
    def _b_open_url(self, args, kwargs, env):
        url = arb_to_string(args[0])
        url = self._interpolate_vars(url, env)
        # Handle javascript: URIs (Addition 18)
        if url.startswith("javascript:"):
            target = kwargs.get("target")
            if target is None:
                raise ArbPlusError("javascript: URIs require a target handle")
            return ArbBool(True)  # No-op in headless mode
        # Determine URL type
        url_type = "web"
        if url.startswith("localhost") or url.startswith("127.") or "localhost:" in url:
            url_type = "localhost"
        elif url.startswith("file:") or url.startswith(".") or url.startswith("/"):
            url_type = "file"
        # Generate a handle
        if not hasattr(self, '_page_handles'):
            self._page_handles = {}
            self._next_handle = 1
        handle = self._next_handle
        self._next_handle += 1
        self._page_handles[handle] = {"url": url, "type": url_type}
        # Try to open (no-op in headless)
        try:
            self._open_with_default(url)
        except Exception:
            pass
        return ArbInt(handle)

    def _b_open_app(self, args, kwargs, env):
        app_name = arb_to_string(args[0])
        app_args = arb_to_string(kwargs.get("args", ArbString(""))) if "args" in kwargs else ""
        adr = arb_to_string(kwargs.get("adr", ArbString(""))) if "adr" in kwargs else ""
        s = platform.system()
        
        # Android support via adb
        if adr:
            if not shutil.which("adb"):
                raise ArbPlusError("open.app: 'adr' requires adb (Android Debug Bridge) to be installed and in PATH")
            try:
                # Check if a device is connected
                devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                device_lines = [l for l in devices.stdout.strip().split('\n') if l and "device" in l and "List" not in l]
                if not device_lines:
                    raise ArbPlusError("open.app: No Android device connected or authorized (check: adb devices)")
                
                # Determine if adr is a bare package name or full intent string
                if adr.startswith("am start"):
                    # Full intent string
                    cmd = ["adb", "shell", adr]
                else:
                    # Bare package name — launch default activity
                    cmd = ["adb", "shell", "monkey", "-p", adr, "-c", "android.intent.category.LAUNCHER", "1"]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode != 0 and "No activities found" in result.stderr:
                    raise ArbPlusError(f"open.app: Package '{adr}' not found on device")
                if result.returncode != 0:
                    raise ArbPlusError(f"open.app: adb launch failed: {result.stderr.strip()}")
                return ArbBool(True)
            except subprocess.TimeoutExpired:
                raise ArbPlusError("open.app: adb timed out — is the device responding?")
            except ArbPlusError:
                raise
            except Exception as e:
                raise ArbPlusError(f"open.app: {e}")
        
        try:
            if s == "Windows":
                if app_args:
                    subprocess.Popen([app_name, app_args], shell=True)
                else:
                    subprocess.Popen([app_name], shell=True)
            elif s == "Darwin":
                if app_args:
                    subprocess.Popen(["open", "-a", app_name, app_args])
                else:
                    subprocess.Popen(["open", "-a", app_name])
            else:
                if app_args:
                    subprocess.Popen([app_name, app_args])
                else:
                    subprocess.Popen([app_name])
            return ArbBool(True)
        except FileNotFoundError:
            raise ArbPlusError(f"Application not found: {app_name}")

    # Addition 12: Command-line arguments and environment variables
    def _b_args(self, args, kwargs, env):
        if not args:
            return ArbList([ArbString(a) for a in self.script_args])
        idx = int(args[0].py())
        if idx < 0 or idx >= len(self.script_args):
            return ArbString("")
        return ArbString(self.script_args[idx])

    def _b_env(self, args, kwargs, env):
        name = arb_to_string(args[0])
        val = os.environ.get(name, "")
        return ArbString(val)

    # Addition 7: Map helper functions
    def _b_map(self, args, kwargs, env):
        if not args:
            return ArbMap([])
        return args[0]

    def _b_keys(self, args, kwargs, env):
        m = args[0]
        if isinstance(m, ArbMap):
            return ArbList([ArbString(k) for k, v in m.val])
        raise ArbPlusError("keys() requires a map argument")

    def _b_values(self, args, kwargs, env):
        m = args[0]
        if isinstance(m, ArbMap):
            return ArbList([v for k, v in m.val])
        raise ArbPlusError("values() requires a map argument")

    def _b_has(self, args, kwargs, env):
        m = args[0]
        key = arb_to_string(args[1])
        if isinstance(m, ArbMap):
            return ArbBool(m.has(key))
        raise ArbPlusError("has() requires a map as first argument")


    def call_builtin(self, name, args, kwargs, env):
        func = self.builtins[name]
        if name in self.ext_hooks:
            for hook in self.ext_hooks[name]:
                result = hook(args, kwargs, func)
                if result is not None:
                    return result
        return func(args, kwargs, env)

    def _b_add(self, args, kwargs, env):
        if not args: return ArbInt(0)
        r = args[0].py()
        for a in args[1:]: r += a.py()
        return to_arb_value(r)

    def _b_sub(self, args, kwargs, env):
        if len(args) < 2: raise ArbPlusError("sub requires at least 2 arguments")
        return to_arb_value(args[0].py() - args[1].py())

    def _b_mul(self, args, kwargs, env):
        if not args: return ArbInt(1)
        r = args[0].py()
        for a in args[1:]: r *= a.py()
        return to_arb_value(r)

    def _b_div(self, args, kwargs, env):
        if len(args) < 2: raise ArbPlusError("div requires at least 2 arguments")
        if args[1].py() == 0: raise ArbPlusError("Division by zero")
        return ArbFloat(args[0].py() / args[1].py())

    def _b_mod(self, args, kwargs, env):
        if len(args) < 2: raise ArbPlusError("mod requires at least 2 arguments")
        if args[1].py() == 0: raise ArbPlusError("Modulo by zero")
        return ArbInt(args[0].py() % args[1].py())

    def _b_pow(self, args, kwargs, env):
        if len(args) < 2: raise ArbPlusError("pow requires at least 2 arguments")
        return ArbFloat(args[0].py() ** args[1].py())

    def _b_concat(self, args, kwargs, env):
        return ArbString("".join(arb_to_string(a) for a in args))

    def _b_len(self, args, kwargs, env):
        if not args: return ArbInt(0)
        v = args[0]
        if isinstance(v, ArbValue):
            if v.type_name == "arb":
                return ArbInt(len(v))
            return ArbInt(len(v.py()))
        return ArbInt(len(v))

    def _b_upper(self, args, kwargs, env):
        return ArbString(arb_to_string(args[0]).upper())

    def _b_lower(self, args, kwargs, env):
        return ArbString(arb_to_string(args[0]).lower())

    def _b_trim(self, args, kwargs, env):
        return ArbString(arb_to_string(args[0]).strip())

    def _b_split(self, args, kwargs, env):
        s = arb_to_string(args[0])
        d = arb_to_string(args[1]) if len(args) > 1 else " "
        if d == "":
            return ArbList([ArbString(c) for c in s])
        return ArbList([ArbString(p) for p in s.split(d)])

    def _b_join(self, args, kwargs, env):
        lst = args[0].py()
        d = arb_to_string(args[1]) if len(args) > 1 else ""
        return ArbString(d.join(arb_to_string(e) for e in lst))

    def _b_substr(self, args, kwargs, env):
        s = arb_to_string(args[0])
        start = int(args[1].py())
        if len(args) > 2:
            return ArbString(s[start:int(args[2].py())])
        return ArbString(s[start:])

    def _b_replace(self, args, kwargs, env):
        """replace(str, old/pattern, replacement [, regex: true])
        Without regex: simple string replacement.
        With regex: true kwarg: regex pattern replacement with backreferences.
        """
        s = arb_to_string(args[0])
        old_pat = arb_to_string(args[1])
        new_str = arb_to_string(args[2])
        use_regex = kwargs.get("regex") is not None and arb_truthy(kwargs["regex"])
        if use_regex:
            try:
                return ArbString(re.sub(old_pat, new_str, s))
            except re.error as e:
                raise ArbPlusError(f"Invalid regex in replace(): {e}")
        return ArbString(s.replace(old_pat, new_str))

    def _b_contains(self, args, kwargs, env):
        return ArbBool(arb_to_string(args[1]) in arb_to_string(args[0]))

    def _b_print(self, args, kwargs, env):
        # Check for -w and -e flags (Set-7)
        warn_flag = kwargs.pop("_warn_flag", False)
        err_flag = kwargs.pop("_err_flag", False)
        
        # Handle colored segments (_b_color)
        has_colored = any(isinstance(a, ArbColoredString) for a in args)
        if has_colored:
            segments = []
            for a in args:
                if isinstance(a, ArbColoredString):
                    segments.append(a.to_ansi_string(self.default_colors))
                else:
                    # Plain string falls back to defaults
                    text = arb_to_string(a)
                    # /n already processed at lexer time
                    pass  # text already has /n converted
                    if self.default_colors:
                        codes = []
                        b = self.default_colors.get("b", "normal")
                        if b == "dim": codes.append("2")
                        elif b == "bright": codes.append("1")
                        elif b == "normal": codes.append("22")
                        fg = self.default_colors.get("fg")
                        bg = self.default_colors.get("bg")
                        if fg: codes.append(color_name_to_ansi(fg, is_bg=False))
                        if bg: codes.append(color_name_to_ansi(bg, is_bg=True))
                        if codes:
                            segments.append(f"\033[{';'.join(codes)}m{text}\033[0m")
                        else:
                            segments.append(text)
                    else:
                        segments.append(text)
            output = " ".join(segments)
        else:
            text = " ".join(arb_to_string(a) for a in args)
            # /n already processed at lexer time
            output = text
        # Apply -w / -e flags (these override default fg unless explicit fg is given)
        if warn_flag or err_flag:
            warn_fg = self.default_colors.get("warn_fg", "yellow")
            err_fg = self.default_colors.get("err_fg", "red")
            # If --ErrOV is enabled, the overridden colors are in default_colors
            # If not, the defaults are yellow/red
            if err_flag:
                fg = kwargs.get("fg", err_fg)
            else:
                fg = kwargs.get("fg", warn_fg)
            bg = kwargs.get("bg")
            b = kwargs.get("b")
            output = self._colorize(output, fg, bg, b)
        elif not has_colored:
            # Apply color kwargs for non-segmented calls
            fg = kwargs.get("fg")
            bg = kwargs.get("bg")
            b = kwargs.get("b")
            if fg or bg or b:
                output = self._colorize(output, fg, bg, b)
        print(output)
        return ArbString("")

    def _b_input(self, args, kwargs, env):
        prompt = arb_to_string(args[0]) if args else ""
        # /n already processed at lexer time
        fg = kwargs.get("fg")
        bg = kwargs.get("bg")
        b = kwargs.get("b")
        if fg or bg or b:
            prompt = self._colorize(prompt, fg, bg, b)
        if self.auto_mode:
            return ArbString(self.auto_input_text)
        try:
            result = input(prompt)
        except EOFError:
            result = ""
        return ArbString(result)

    def _colorize(self, text, fg=None, bg=None, b=None):
        BRIGHT_MAP = {
            "dim": "2", "normal": "22", "bright": "1",
        }
        # Apply default overrides first
        if fg is None and "fg" in self.default_colors:
            fg = self.default_colors["fg"]
        if bg is None and "bg" in self.default_colors:
            bg = self.default_colors["bg"]
        if b is None and "b" in self.default_colors:
            b = self.default_colors["b"]
        codes = []
        if b:
            bv = arb_to_string(b) if isinstance(b, ArbValue) else b
            if bv in BRIGHT_MAP: codes.append(BRIGHT_MAP[bv])
        if fg:
            f = arb_to_string(fg) if isinstance(fg, ArbValue) else fg
            ansi = color_name_to_ansi(f, is_bg=False)
            if ansi: codes.append(ansi)
        if bg:
            bgv = arb_to_string(bg) if isinstance(bg, ArbValue) else bg
            ansi = color_name_to_ansi(bgv, is_bg=True)
            if ansi: codes.append(ansi)
        if codes:
            return f"\033[{';'.join(codes)}m{text}\033[0m"
        return text

    def _print_warning(self, msg):
        """Addition 30: Print a warning in yellow (or overridden warn_fg color)."""
        fg = self.default_colors.get("warn_fg", "yellow")
        print(self._colorize(f"Warning: {msg}", fg=fg))

    def _print_error(self, msg):
        """Addition 30: Print an error in red (or overridden err_fg color)."""
        fg = self.default_colors.get("err_fg", "red")
        print(self._colorize(f"Error: {msg}", fg=fg))

    def _b_swap(self, args, kwargs, env):
        raise ArbPlusError("swap() must be used as: a <> b")

    def _b_toint(self, args, kwargs, env): return ArbInt(int(args[0].py()))
    def _b_tofloat(self, args, kwargs, env): return ArbFloat(float(args[0].py()))
    def _b_tostring(self, args, kwargs, env): return ArbString(arb_to_string(args[0]))
    def _b_tobool(self, args, kwargs, env): return ArbBool(arb_truthy(args[0]))
    def _b_typeof(self, args, kwargs, env): return ArbString(args[0].type_name if isinstance(args[0], ArbValue) else "unknown")


## 10 -- 10_interp_file_dir_time.py -- Interpreter: file/dir/addr/txtRC/time/locale builtins
    def _b_readfile(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        if not os.path.exists(path): raise ArbPlusError(f"File not found: {path}")
        if os.path.isdir(path): raise ArbPlusError(f"Path is a directory: {path}")
        if not os.access(path, os.R_OK): raise ArbPlusError(f"File not readable: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        env.declare("__last_read", ArbString(content))
        return ArbString(content)

    def _b_fileexists(self, args, kwargs, env):
        return ArbBool(os.path.exists(self._resolve_path(arb_to_string(args[0]))) and os.path.isfile(self._resolve_path(arb_to_string(args[0]))))

    def _b_writefile(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        content = arb_to_string(args[1])
        mode = arb_to_string(kwargs.get("mode", ArbString("overwrite"))) if "mode" in kwargs else "overwrite"
        if mode == "error" and os.path.exists(path):
            raise ArbPlusError(f"File already exists: {path}")
        d = os.path.dirname(path)
        if d: os.makedirs(d, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return ArbBool(True)

    def _b_buildfile(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        content = arb_to_string(args[1])
        if os.path.exists(path):
            base, ext = os.path.splitext(path)
            i = 1
            while os.path.exists(f"{base}_{i}{ext}"): i += 1
            path = f"{base}_{i}{ext}"
        d = os.path.dirname(path)
        if d: os.makedirs(d, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return ArbString(path)

    def _b_file(self, args, kwargs, env):
        """Addition 36: Create a file-reference value.
        file("path/to/file.txt") returns an ArbFileRef that carries
        the resolved path and can be used with readFile, fileExists, addr.hex, etc.
        """
        if not args:
            raise ArbPlusError("file() requires a file path argument")
        raw_path = arb_to_string(args[0])
        resolved = self._resolve_path(raw_path)
        return ArbFile(resolved)


    def _b_encode_image(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        if not os.path.exists(path): raise ArbPlusError(f"Image file not found: {path}")
        with open(path, 'rb') as f:
            data = f.read()
        b64 = base64.b64encode(data).decode()
        arb = ArbArb()
        arb.add("image", b64)
        return arb

    def _b_decode_image(self, args, kwargs, env):
        arb_val = args[0]
        if not isinstance(arb_val, ArbArb): raise ArbPlusError("decodeImage requires an arb value")
        for tag_name, tag_byte, hex_bytes, decoded in arb_val.val:
            if tag_name == "image":
                out_path = self._resolve_path(arb_to_string(args[1])) if len(args) > 1 else "decoded_image.png"
                data = base64.b64decode(decoded)
                with open(out_path, 'wb') as f:
                    f.write(data)
                return ArbString(out_path)
        raise ArbPlusError("No image tag found in arb value")

    def _b_open_media(self, args, kwargs, env):
        path = arb_to_string(args[0])
        
        # Android: open from termux data directory
        if shutil.which("adb"):
            try:
                devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                device_lines = [l for l in devices.stdout.strip().split('\n') if l and "device" in l and "List" not in l]
                if device_lines:
                    # On Android/Termux, resolve from the termux data directory
                    if not os.path.isabs(path):
                        termux_dir = os.environ.get("HOME", "/data/data/com.termux/files/home")
                        resolved = os.path.join(termux_dir, path)
                    else:
                        resolved = path
                    if not os.path.exists(resolved):
                        raise ArbPlusError(f"File not found: {resolved}")
                    self._open_with_default(resolved)
                    return ArbBool(True)
            except ArbPlusError:
                raise
            except Exception:
                pass
        
        resolved = self._resolve_path(path)
        if not os.path.exists(resolved): raise ArbPlusError(f"File not found: {resolved}")
        self._open_with_default(resolved)
        return ArbBool(True)

    def _b_open_browser(self, args, kwargs, env):
        self._open_with_default(arb_to_string(args[0]))
        return ArbBool(True)

    def _open_with_default(self, path_or_url):
        s = platform.system()
        if s == "Windows": os.startfile(path_or_url)
        elif s == "Darwin": subprocess.run(["open", path_or_url])
        else: subprocess.run(["xdg-open", path_or_url])

    def _b_addr(self, args, kwargs, env):
        if not args: return ArbString("")
        return args[0]

    def _b_addr_hex(self, args, kwargs, env):
        val = args[0].py()
        if isinstance(val, int):
            return ArbString(f"0x{val:X}")
        return ArbString(arb_to_string(args[0]))

    def _b_addr_binary(self, args, kwargs, env):
        val = args[0].py()
        if isinstance(val, int):
            return ArbString(f"0b{val:b}")
        return ArbString(arb_to_string(args[0]))

    def _b_addr_meta(self, args, kwargs, env):
        return ArbString(f"[metadata: {arb_to_string(args[0])}]")

    def _b_txtrc(self, args, kwargs, env):
        """txtRC(row, col, data) - row/column access on any string data (Addition 21).
        Works on file reads, fetch.url results, or any string/arb value.
        1-based indexing.
        """
        row = int(args[0].py())
        col = int(args[1].py())
        # Data can be a string, ArbString, ArbMap (fetch result), etc.
        if len(args) > 2:
            data_val = args[2]
            # If it's a fetch result (map with "body" key), extract body
            if isinstance(data_val, ArbMap):
                body = data_val.get("body")
                if body is not None:
                    data = arb_to_string(body)
                else:
                    data = arb_to_string(data_val)
            else:
                data = arb_to_string(data_val)
        else:
            raise ArbPlusError("txtRC() requires 3 arguments: row, col, data")
        
        lines = data.strip().split('\n')
        if row < 1 or row > len(lines):
            raise ArbPlusError(f"txtRC row {row} out of bounds (lines={len(lines)})")
        line = lines[row - 1]
        # Auto-detect delimiter
        if '\t' in line:
            cols = line.split('\t')
        elif ',' in line:
            cols = line.split(',')
        elif ';' in line:
            cols = line.split(';')
        else:
            cols = line.split()
        if col < 1 or col > len(cols):
            raise ArbPlusError(f"txtRC column {col} out of bounds (cols={len(cols)})")
        return ArbString(cols[col - 1].strip())
    def _b_dir_list(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        filter_type = arb_to_string(args[1]).lower() if len(args) > 1 else ""
        if not os.path.isdir(path): raise ArbPlusError(f"Directory not found: {path}")
        entries = sorted(os.listdir(path))
        result = []
        for entry in entries:
            full = os.path.join(path, entry)
            if filter_type == "files" and not os.path.isfile(full): continue
            if filter_type == "folders" and not os.path.isdir(full): continue
            result.append(ArbString(entry))
        return ArbList(result)

    def _b_dir_name(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        new_name = arb_to_string(args[1])
        if not os.path.isdir(path): raise ArbPlusError(f"Directory not found: {path}")
        parent = os.path.dirname(path)
        new_path = os.path.join(parent, new_name)
        if os.path.exists(new_path): raise ArbPlusError(f"Target already exists: {new_path}")
        os.rename(path, new_path)
        return ArbBool(True)

    def _b_dir_make(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        files_str = arb_to_string(args[1]) if len(args) > 1 else ""
        os.makedirs(path, exist_ok=True)
        if files_str:
            for fname in files_str.split(';'):
                fname = fname.strip()
                if fname:
                    with open(os.path.join(path, fname), 'w') as f:
                        f.write("")
        return ArbBool(True)

    def _b_dir_del(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        if not os.path.exists(path): raise ArbPlusError(f"Path not found: {path}")
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return ArbBool(True)

    def _b_snap_time(self, args, kwargs, env):
        """snap.time(Year, Month, Day, Hour, Minute, Second, Millisecond)
        Presence-based: pass string names or kwargs for the components you want.
        Returns raw value(s), not Key=val.
        snap.time() → full timestamp.
        snap.time("minute") → "37"
        snap.time(minute: true) → "37"
        snap.time("hour", "minute") → "14 37"
        """
        now = datetime.datetime.now()
        if not args and not kwargs:
            return ArbString(now.strftime("%Y-%m-%d %H:%M:%S"))
        
        components = {
            "year": now.year, "month": now.month, "day": now.day,
            "hour": now.hour, "minute": now.minute, "second": now.second,
            "millisecond": now.microsecond // 1000,
            "ms": now.microsecond // 1000,
        }
        param_order = ["year", "month", "day", "hour", "minute", "second", "millisecond"]
        requested = []
        for i, arg in enumerate(args):
            # If arg is a string matching a component name, use it
            sval = arb_to_string(arg).lower()
            if sval in components:
                requested.append(components[sval])
            elif i < len(param_order):
                # Positional: position determines component
                requested.append(components[param_order[i]])
        for k, v in kwargs.items():
            kl = k.lower()
            if kl in components:
                requested.append(components[kl])
        
        if not requested:
            return ArbString(now.strftime("%Y-%m-%d %H:%M:%S"))
        if len(requested) == 1:
            return ArbString(str(requested[0]))
        return ArbString(" ".join(str(r) for r in requested))

    def _b_count_time(self, args, kwargs, env):
        """count.time(Hour, Minute, Second, Millisecond)
        Presence-based: pass string names or kwargs for the components you want.
        Returns raw value(s), not Key=val.
        count.time() → "HH:MM:SS.mmm". count.time("minute") → "30"
        Special kwargs: live: true, MS: <interval> for live clock mode.
        """
        now = datetime.datetime.now()
        
        # Check for live mode
        live = False
        interval_ms = 1000
        if "live" in kwargs:
            live = arb_to_string(kwargs["live"]).lower() in ("true", "1", "yes")
        if "MS" in kwargs and live:
            v = kwargs["MS"]
            interval_ms = int(v.py()) if hasattr(v, 'py') else int(v)
        
        if live:
            try:
                while True:
                    t = datetime.datetime.now()
                    print(f"\r{t.strftime('%H:%M:%S.%f')[:-3]}", end='', flush=True)
                    time.sleep(interval_ms / 1000.0)
            except KeyboardInterrupt:
                print()
                return ArbString("stopped")
        
        if not args and not kwargs:
            return ArbString(now.strftime("%H:%M:%S.%f")[:-3])
        
        components = {
            "year": now.year, "month": now.month, "day": now.day,
            "hour": now.hour, "minute": now.minute, "second": now.second,
            "millisecond": now.microsecond // 1000,
            "ms": now.microsecond // 1000,
        }
        param_order = ["hour", "minute", "second", "millisecond"]
        requested = []
        for i, arg in enumerate(args):
            sval = arb_to_string(arg).lower()
            if sval in components:
                requested.append(components[sval])
            elif i < len(param_order):
                requested.append(components[param_order[i]])
        for k, v in kwargs.items():
            if k == "live" or k == "MS":
                continue
            kl = k.lower()
            if kl in components:
                requested.append(components[kl])
        
        if not requested:
            return ArbString(now.strftime("%H:%M:%S.%f")[:-3])
        if len(requested) == 1:
            return ArbString(str(requested[0]))
        return ArbString(" ".join(str(r) for r in requested))

    def _b_var(self, args, kwargs, env):
        """var(variable_name) — resolve a variable by name, usable where strings expect quoted args."""
        if not args:
            raise ArbPlusError("var() requires a variable name argument")
        var_name = arb_to_string(args[0])
        if not env.has(var_name):
            raise ArbPlusError(f"var(): variable '{var_name}' is not defined")
        return env.get(var_name)

    def _b_wait(self, args, kwargs, env):
        minutes = int(args[0].py()) if len(args) > 0 else 0
        seconds = int(args[1].py()) if len(args) > 1 else 0
        ms = int(args[2].py()) if len(args) > 2 else 0
        total = minutes * 60 + seconds + ms / 1000.0
        time.sleep(total)
        return ArbBool(True)

    def _b_cs(self, args, kwargs, env):
        is_dark = self._detect_dark_mode()
        if not args:
            return ArbString("dark" if is_dark else "light")
        target = arb_to_string(args[0]).lower()
        if target == "dark": return ArbBool(is_dark)
        if target == "light": return ArbBool(not is_dark)
        return ArbBool(False)

    def _detect_dark_mode(self):
        # Android detection via adb
        if shutil.which("adb"):
            try:
                devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                device_lines = [l for l in devices.stdout.strip().split('\n') if l and "device" in l and "List" not in l]
                if device_lines:
                    # Try multiple Android dark mode properties
                    # 1. ui_night_mode (older API)
                    result = subprocess.run(["adb", "shell", "settings", "get", "secure", "ui_night_mode"],
                                          capture_output=True, text=True, timeout=5)
                    mode = result.stdout.strip()
                    if mode == "2":
                        return True
                    elif mode == "1":
                        return False
                    # 2. Try system_ui_night_mode (newer API)
                    result = subprocess.run(["adb", "shell", "settings", "get", "system", "ui_night_mode"],
                                          capture_output=True, text=True, timeout=5)
                    mode = result.stdout.strip()
                    if mode == "2":
                        return True
                    elif mode == "1":
                        return False
                    # 3. Try cmd uimode night (Android 10+)
                    result = subprocess.run(["adb", "shell", "cmd", "uimode", "night"],
                                          capture_output=True, text=True, timeout=5)
                    output = result.stdout.strip().lower()
                    if "yes" in output:
                        return True
                    elif "no" in output:
                        return False
                    # 4. Try dumpsys to check current theme
                    result = subprocess.run(["adb", "shell", "dumpsys", "activity", "throttle"],
                                          capture_output=True, text=True, timeout=5)
                    if "isDarkTheme" in result.stdout:
                        return "true" in result.stdout.split("isDarkTheme")[1][:20].lower()
                    # Auto mode — check current time as fallback
                    hour = datetime.datetime.now().hour
                    return hour < 6 or hour >= 18
            except Exception:
                pass
        
        try:
            if platform.system() == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return val == 0
            elif platform.system() == "Darwin":
                result = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True)
                return "Dark" in result.stdout
        except Exception:
            pass
        return False

    def _b_locale_prf(self, args, kwargs, env): return ArbString(self._get_locale())
    def _b_locale_check(self, args, kwargs, env):
        target = arb_to_string(args[0]).lower()
        return ArbBool(target in self._get_locale().lower())
    def _b_locale_alt(self, args, kwargs, env): return ArbString("en-US, en-GB")
    def _b_locale_cur(self, args, kwargs, env): return ArbString(self._get_locale())

    def _get_locale(self):
        loc = os.environ.get('LANG', os.environ.get('LC_ALL', 'en_US.UTF-8'))
        return loc.split('.')[0]

    def _b_battery(self, args, kwargs, env):
        # Android support via adb
        if shutil.which("adb"):
            try:
                devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                device_lines = [l for l in devices.stdout.strip().split('\n') if l and "device" in l and "List" not in l]
                if device_lines:
                    # Get battery level via dumpsys
                    result = subprocess.run(["adb", "shell", "dumpsys", "battery"],
                                          capture_output=True, text=True, timeout=5)
                    for line in result.stdout.split('\n'):
                        if "level:" in line.lower():
                            level = line.split(":")[1].strip()
                            return ArbString(level + "%")
            except Exception:
                pass
        try:
            if platform.system() == "Linux":
                with open("/sys/class/power_supply/BAT0/capacity", 'r') as f:
                    return ArbString(f.read().strip() + "%")
        except Exception:
            pass
        return ArbString("unknown")

    def _b_network(self, args, kwargs, env):
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return ArbBool(True)
        except Exception:
            return ArbBool(False)

    def _b_screen(self, args, kwargs, env):
        # Android support via adb
        if shutil.which("adb"):
            try:
                devices = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                device_lines = [l for l in devices.stdout.strip().split('\n') if l and "device" in l and "List" not in l]
                if device_lines:
                    result = subprocess.run(["adb", "shell", "wm", "size"],
                                          capture_output=True, text=True, timeout=5)
                    for line in result.stdout.split('\n'):
                        if "Physical size" in line:
                            return ArbString(line.split(":")[1].strip())
            except Exception:
                pass
        try:
            if platform.system() == "Linux":
                result = subprocess.run(["xdpyinfo"], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if "dimensions" in line:
                        return ArbString(line.split(':')[1].strip().split()[0])
        except Exception:
            pass
        return ArbString("unknown")

    def _b_os_name(self, args, kwargs, env): return ArbString(platform.system())
    def _b_os_version(self, args, kwargs, env): return ArbString(platform.version())

    def eval_locale_member(self, member, env):
        if member == "prf": return ArbString(self._get_locale())
        if member == "cur": return ArbString(self._get_locale())
        if member == "alt": return ArbString("en-US, en-GB")
        raise ArbPlusError(f"Unknown locale member: {member}")

    def eval_os_member(self, member, env):
        ml = member.lower()
        if ml == "name": return ArbString(platform.system())
        if ml == "version": return ArbString(platform.version())
        if ml == "battery": return self._b_battery([], {}, env)
        if ml == "screen": return self._b_screen([], {}, env)
        if ml == "network": return self._b_network([], {}, env)
        if ml == "cs": return self._b_cs([], {}, env)
        raise ArbPlusError(f"Unknown os member: {member}")


## 11 -- 11_interp_ext_net.py -- Interpreter: extensions, imports, fetch/dl, meta builtins
    def _b_load_ext(self, args, kwargs, env):
        raw_path = arb_to_string(args[0])
        lang = arb_to_string(args[1]).lower() if len(args) > 1 else "python"
        path = self._resolve_path(raw_path)
        # Built-in extension search: if not found, check extensions/ directory
        # (like Python's built-in modules — loadExt("ext_gui_web", "python") works
        #  without specifying the full path)
        if not os.path.exists(path):
            # Try extensions/ directory relative to interpreter location
            interp_dir = os.path.dirname(os.path.abspath(__file__))
            ext_dir = os.path.join(interp_dir, "extensions")
            # Try with .py suffix
            for candidate in [
                os.path.join(ext_dir, raw_path + ".py"),
                os.path.join(ext_dir, raw_path),
                os.path.join(ext_dir, "ext_" + raw_path + ".py"),
                os.path.join(ext_dir, "ext_" + raw_path),
            ]:
                if os.path.exists(candidate):
                    path = candidate
                    break
        if not os.path.exists(path): raise ArbPlusError(f"Extension file not found: {path}")
        # Parse and store extension metadata (Addition 20)
        if not hasattr(self, 'ext_metadata'):
            self.ext_metadata = {}
        ext_name = os.path.splitext(os.path.basename(path))[0]
        meta = self._parse_ext_metadata(path, lang)
        if meta:
            self.ext_metadata[ext_name] = meta
            # Check for version mismatch with script dependencies
            dep_str = self.metadata.get("dependencies", "")
            if ext_name in str(dep_str):
                # Try to extract expected version
                dep_match = re.search(ext_name + r'\s+(\d+(?:\.\d+)*)', str(dep_str))
                if dep_match:
                    expected_ver = dep_match.group(1)
                    actual_ver = meta.get("version", "")
                    if actual_ver and actual_ver != expected_ver:
                        print(f"Warning: Extension '{ext_name}' version mismatch (expected {expected_ver}, got {actual_ver})")
        if lang == "python":
            spec = importlib.util.spec_from_file_location("arbplus_ext", path)
            if spec is None: raise ArbPlusError(f"Cannot load Python extension: {path}")
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, 'register'):
                mod.register(self)
            return ArbBool(True)
        elif lang in ("c", "c++", "cpp"):
            compiler = shutil.which("gcc") or shutil.which("cc") or shutil.which("clang")
            if not compiler:
                raise ArbPlusError("C/C++ extension requires a C compiler but none was found.")
            import tempfile
            suffix = '.c' if lang == 'c' else '.cpp'
            with tempfile.NamedTemporaryFile(suffix=suffix, mode='w', delete=False) as f:
                f.write(open(path).read())
                src = f.name
            lib = src.rsplit('.', 1)[0] + '.so'
            try:
                result = subprocess.run([compiler, '-shared', '-fPIC', src, '-o', lib], capture_output=True, text=True)
                if result.returncode != 0:
                    raise ArbPlusError(f"C/C++ extension compilation failed:\n{result.stderr}")
                ctypes.CDLL(lib).arbplus_register()
                return ArbBool(True)
            finally:
                for f in [src, lib]:
                    if os.path.exists(f): os.unlink(f)
        else:
            raise ArbPlusError(f"Unsupported extension language: {lang}")

    def register_extension(self, name, func):
        self.extensions[name] = func

    def register_hook(self, builtin_name, hook_func):
        if builtin_name not in self.ext_hooks:
            self.ext_hooks[builtin_name] = []
        self.ext_hooks[builtin_name].append(hook_func)

    def _import_module(self, mod_name, env):
        """Import a .arb module file and register its functions with a prefix."""
        if mod_name in self.imported_modules:
            return  # already imported
        if mod_name in self._importing:
            raise ArbPlusError(f"Circular import detected: {mod_name}")
        self._importing.add(mod_name)
        
        # Find the module file
        mod_path = mod_name
        if not mod_path.endswith('.arb'):
            mod_path = mod_name + '.arb'
        if not os.path.isabs(mod_path):
            mod_path = os.path.join(self.script_path, mod_path)
        if not os.path.exists(mod_path):
            # Not an .arb module - might be a Python extension loaded via loadExt
            self._importing.discard(mod_name)
            return
        
        with open(mod_path, 'r', encoding='utf-8') as f:
            source = f.read()
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        
        # Register functions with module prefix
        mod_funcs = {}
        for fname, func in program.functions.items():
            # Store as modname.funcname for prefixed calls
            prefixed_name = f"{mod_name}.{fname}"
            self.functions[prefixed_name] = func
            mod_funcs[fname] = func
        # Also store without prefix for potential direct access
        self.imported_modules[mod_name] = mod_funcs
        self._importing.discard(mod_name)


    # =====================================================================
    # Regex / Pattern Matching
    # =====================================================================

    def _b_match(self, args, kwargs, env):
        """match(str, pattern) -> map{ "matched": bool, "match": str, "groups": list }
        Uses Python re syntax (full regex).  Returns a map with match info.
        """
        if len(args) < 2:
            raise ArbPlusError("match() requires 2 arguments: string and pattern")
        text = arb_to_string(args[0])
        pattern = arb_to_string(args[1])
        try:
            m = re.search(pattern, text)
        except re.error as e:
            raise ArbPlusError(f"Invalid regex pattern '{pattern}': {e}")
        if m:
            groups = [ArbString(g) if g is not None else ArbString("") for g in m.groups()]
            return ArbMap([
                ("matched", ArbBool(True)),
                ("match", ArbString(m.group(0))),
                ("groups", ArbList(groups)),
                ("index", ArbInt(m.start())),
                ("end", ArbInt(m.end())),
            ])
        return ArbMap([
            ("matched", ArbBool(False)),
            ("match", ArbString("")),
            ("groups", ArbList([])),
        ])

    # =====================================================================
    # Network Fetching
    # =====================================================================

    def _b_fetch_url(self, args, kwargs, env):
        """fetch.url(url) -> map{ "status": int, "body": str, "headers": map, "ok": bool }
        Raises ArbPlusError on network failures (catchable via try/catch).
        """
        if not args:
            raise ArbPlusError("fetch.url() requires a URL argument")
        url = arb_to_string(args[0])
        timeout = 10
        if len(args) >= 2:
            timeout = int(args[1].py())
        if "timeout" in kwargs:
            timeout = int(kwargs["timeout"].py())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArbPlus/0.0.21"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            body = resp.read().decode('utf-8', errors='replace')
            status = resp.getcode()
            headers = []
            for k, v in resp.headers.items():
                headers.append((k, ArbString(v)))
            return ArbMap([
                ("status", ArbInt(status)),
                ("body", ArbString(body)),
                ("headers", ArbMap(headers)),
                ("ok", ArbBool(200 <= status < 300)),
            ])
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode('utf-8', errors='replace')
            except Exception:
                pass
            headers = []
            for k, v in (e.headers.items() if e.headers else []):
                headers.append((k, ArbString(v)))
            return ArbMap([
                ("status", ArbInt(e.code)),
                ("body", ArbString(body)),
                ("headers", ArbMap(headers)),
                ("ok", ArbBool(False)),
            ])
        except urllib.error.URLError as e:
            raise ArbPlusError(f"Network error fetching '{url}': {e.reason}")
        except Exception as e:
            raise ArbPlusError(f"Fetch error: {e}")

    # =====================================================================
    # Variable Deletion
    # =====================================================================

    def _b_del(self, args, kwargs, env):
        """del(varName) - deletes a variable from the current scope."""
        if not args:
            raise ArbPlusError("del() requires a variable name")
        # args[0] should be an ArbString with the variable name
        var_name = arb_to_string(args[0])
        if not env.has_local(var_name):
            # Check if it exists in parent scope
            if env.has(var_name):
                raise ArbPlusError(f"Cannot delete variable '{var_name}': not in current scope (it's in a parent scope)")
            raise ArbPlusError(f"Cannot delete variable '{var_name}': not declared")
        env.delete(var_name)
        return ArbBool(True)

    # =====================================================================
    # FIXME Colored Segments
    # =====================================================================

    def _b_color(self, args, kwargs, env):
        """color("text", fg: red, bg: black, b: bright) -> ArbColoredString
        Returns a colored string segment that carries styling alongside text.
        """
        if not args:
            raise ArbPlusError("color() requires text argument")
        text = arb_to_string(args[0])
        fg = arb_to_string(kwargs["fg"]) if "fg" in kwargs else None
        bg = arb_to_string(kwargs["bg"]) if "bg" in kwargs else None
        brightness = arb_to_string(kwargs["b"]) if "b" in kwargs else "normal"
        return ArbColoredString(text, fg=fg, bg=bg, brightness=brightness)

    # =====================================================================
    # ADDITION 19: PAGE HANDLES FOR open.url
    # =====================================================================

    def _b_open_page(self, args, kwargs, env):
        """open.page() -> list all handles; open.page(handle) -> info about a page."""
        if not args:
            if hasattr(self, '_page_handles') and self._page_handles:
                return ArbList([ArbInt(h) for h in self._page_handles.keys()])
            return ArbList([])
        try:
            handle = int(args[0].py())
        except (ValueError, TypeError):
            return ArbString("No pages opened")
        if hasattr(self, '_page_handles') and handle in self._page_handles:
            info = self._page_handles[handle]
            return ArbMap([
                ("handle", ArbInt(handle)),
                ("url", ArbString(info.get("url", ""))),
                ("type", ArbString(info.get("type", "web"))),
            ])
        raise ArbPlusError(f"No page found with handle {handle}")

    # =====================================================================
    # ADDITION 20: EXTENSION METADATA
    # =====================================================================

    def _b_meta(self, args, kwargs, env):
        """Addition 34: meta() returns all metadata as a map, meta(key) returns a field."""
        if len(args) == 0:
            return ArbMap([(k, ArbString(str(v)) if not isinstance(v, ArbValue) else v)
                           for k, v in self.metadata.items() if not k.startswith('_')])
        key = arb_to_string(args[0])
        if key in self.metadata:
            val = self.metadata[key]
            if isinstance(val, str): return ArbString(val)
            elif isinstance(val, int): return ArbInt(val)
            elif isinstance(val, float): return ArbFloat(val)
            elif isinstance(val, list): return ArbList([ArbString(str(v)) for v in val])
            elif isinstance(val, ArbValue): return val
            return ArbString(str(val))
        return ArbNull()

    def _b_ext_meta(self, args, kwargs, env):
        """extMeta("extension_name") -> map with metadata from the extension file."""
        if not args:
            # Return all extension metadata
            return ArbMap([(k, ArbMap([(mk, ArbString(str(mv))) for mk, mv in v.items()]))
                          for k, v in self.ext_metadata.items()]) if hasattr(self, 'ext_metadata') else ArbMap([])
        ext_name = arb_to_string(args[0])
        if hasattr(self, 'ext_metadata') and ext_name in self.ext_metadata:
            meta = self.ext_metadata[ext_name]
            return ArbMap([(k, ArbString(str(v))) for k, v in meta.items()])
        raise ArbPlusError(f"No metadata found for extension '{ext_name}'")

    def _parse_ext_metadata(self, path, lang):
        """Parse metadata from extension file comment blocks."""
        metadata = {}
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Look for @arbplus-meta annotations in comments
            # Format: name="value" pairs in comment blocks
            for match in re.finditer(r"""@arbplus-meta\s+(\w+)=["\x27]([^"\x27]*)["\x27]""", content):
                metadata[match.group(1)] = match.group(2)
            # Also check for sidecar .meta file
            meta_path = path.rsplit('.', 1)[0] + '.meta'
            if os.path.exists(meta_path):
                with open(meta_path, 'r') as f:
                    for line in f:
                        if '=' in line:
                            k, v = line.strip().split('=', 1)
                            metadata[k.strip()] = v.strip().strip('"\'')
        except Exception:
            pass
        return metadata

    # =====================================================================
    # Extended Page Opening
    # =====================================================================

    def _b_run_arb(self, args, kwargs, env):
        """run.arb("filename.arb", var1: val1, var2: val2) -> runs sub-script with passed variables.
        Variables arrive as pre-populated in the child script's global scope.
        Child script can return a value via return(), which run.arb returns to caller.
        Type information travels intact (ArbValue objects passed directly).
        """
        if not args:
            raise ArbError("run.arb() requires a filename argument")
        filename = arb_to_string(args[0])
        script_path = self._resolve_path(filename)
        if not os.path.exists(script_path):
            raise ArbPlusError(f"Script file not found: {script_path}")
        with open(script_path, 'r', encoding='utf-8') as f:
            source = f.read()
        # Create a new interpreter instance for the sub-script
        child = Interpreter()
        child.script_path = os.path.dirname(os.path.abspath(script_path))
        # Parse the child script
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        child_program = parser.parse()
        # Pre-populate child's global env with passed variables
        for kname, kval in kwargs.items():
            child.global_env.declare(kname, kval)
        # Register child's functions
        for fname, fdef in child_program.functions.items():
            child.functions[fname] = fdef
        # Run the child script
        try:
            for stmt in child_program.body:
                child.execute(stmt, child.global_env)
        except ReturnException as ret:
            return ret.value
        except ExitException:
            pass
        return ArbNull()

    def _b_dl_url(self, args, kwargs, env):
        """dl.url(url, path: "./downloads/", filename: "name.txt") -> downloads URL to disk.
        Returns the saved file path as a string.
        Filename determined from: explicit filename: kwarg, Content-Disposition header, or URL last segment.
        Failures surface as ArbPlusError (catchable via try/catch).
        """
        if not args:
            raise ArbPlusError("dl.url() requires a URL argument")
        url = arb_to_string(args[0])
        # Determine save path
        save_dir = self.script_path
        if "path" in kwargs:
            save_dir = self._resolve_path(arb_to_string(kwargs["path"]))
        # Determine filename
        filename = None
        if "filename" in kwargs:
            filename = arb_to_string(kwargs["filename"])
        timeout = 10
        # Positional timeout: dl.url(url, 5) — 2nd arg is timeout if numeric
        if len(args) >= 2 and isinstance(args[1], (ArbInt, ArbFloat)):
            timeout = int(args[1].py())
        if "timeout" in kwargs:
            timeout = int(kwargs["timeout"].py())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArbPlus/0.0.21"})
            resp = urllib.request.urlopen(req, timeout=timeout)
            content = resp.read()
            # Try Content-Disposition header for filename
            if not filename:
                cd = resp.headers.get("Content-Disposition", "")
                if "filename=" in cd:
                    # Extract filename from Content-Disposition
                    fn_part = cd.split("filename=")[-1].strip().strip('"').strip("'")
                    if fn_part:
                        filename = fn_part
            # Fall back to URL last segment
            if not filename:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path_seg = parsed.path.rstrip("/")
                if path_seg:
                    filename = os.path.basename(path_seg)
                if not filename:
                    filename = "download.bin"
            # Ensure directory exists
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, filename)
            with open(save_path, 'wb') as f:
                f.write(content)
            return ArbString(save_path)
        except urllib.error.HTTPError as e:
            raise ArbPlusError(f"dl.url() HTTP error: {e.code} {e.reason}")
        except urllib.error.URLError as e:
            raise ArbPlusError(f"dl.url() network error: {str(e.reason)}")
        except Exception as e:
            raise ArbPlusError(f"dl.url() error: {str(e)}")


    # ── List operations (Addition 48) ──────────────────────────────

## 12 -- 12_cli.py -- CLI entry point (run_file/main)
def _extract_auto_mode(argv):
    auto_mode = False
    auto_input_text = ""
    positional = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--auto":
            auto_mode = True
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                auto_input_text = argv[i + 1]
                i += 1
        elif arg.startswith("--auto="):
            auto_mode = True
            auto_input_text = arg.split("=", 1)[1]
        else:
            positional.append(arg)
        i += 1

    return auto_mode, auto_input_text, positional






def run_file(filepath, auto_mode=False, auto_input_text="", script_args=None):
    if not os.path.exists(filepath):
        print(f"Error: File not found: {filepath}")
        return 1
    with open(filepath, 'r', encoding='utf-8') as f:
        source = f.read()
    try:
        lexer = Lexer(source)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        program = parser.parse()
        interp = Interpreter(filepath)
        interp.auto_mode = auto_mode
        interp.auto_input_text = auto_input_text
        if script_args is not None:
            interp.script_args = script_args
        elif len(sys.argv) > 2:
            interp.script_args = sys.argv[2:]
        return interp.run(program)
    except ArbPlusError as e:
        try: interp._print_error(str(e))
        except: print(f"ArbPlus Error: {e}")
        return 1
    except ArbError as e:
        try: interp._print_error(str(e))
        except: print(f"Arb Error: {e}")
        return 1
    except ExitException as e:
        return e.code
    except Exception as e:
        try: interp._print_error(str(e))
        except: print(f"Runtime Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    auto_mode, auto_input_text, argv = _extract_auto_mode(sys.argv[1:])
    if not argv:
        print("Usage: arbplus <file.arb> [args...]")
        print("       ArbPlus Language Interpreter - CLimate (v0.0.21) ")
        print("       'A Really Bad Programming Language'")
        return 1
    code = run_file(argv[0], auto_mode=auto_mode, auto_input_text=auto_input_text, script_args=argv[1:])
    sys.exit(code)

if __name__ == "__main__":
    main()

