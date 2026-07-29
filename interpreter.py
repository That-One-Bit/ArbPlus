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
            return val.val
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

class ArbPlusError(Exception):
    pass

class ArbError(Exception):
    """Arb Language Error - Passed with bad Arb carrying"""
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
    GT_TERM = "GT_TERM"
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
                self.tokens.append(Token(TokenType.GT_TERM, '>', self.line, self.col))
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


# =============================================================================
# SECTION 4: AST NODES
# =============================================================================

@dataclass
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
        while self.peek().type in (TokenType.SEMI, TokenType.GT_TERM, TokenType.NEWLINE):
            self.advance()

    def at(self, ttype):
        return self.peek().type == ttype

    def at_keyword(self, kw):
        return self.peek().type == TokenType.KEYWORD and self.peek().value == kw

    def parse(self):
        program = ProgramNode()
        program.metadata = MetaNode()
        program.declarations = DeclNode()

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
            else:
                new = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideNode(base, new))
            self.skip_terminators()

        self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--Function':
            func = self.parse_function_def()
            program.functions[func.name] = func
            self.skip_terminators()
            self.skip_newlines()

        program.body = self.parse_block_until([TokenType.EOF])
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
            while self.peek().type not in (TokenType.SEMI, TokenType.GT_TERM, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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
                else:
                    new = self.expect(TokenType.IDENT).value
                    statements.append(OverrideNode(base, new))
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
            if self.peek().type in (TokenType.SEMI, TokenType.GT_TERM, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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
            if self.peek().type not in (TokenType.SEMI, TokenType.GT_TERM, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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
            name = self.expect(TokenType.IDENT).value
            self.expect(TokenType.RBRACKET)  # consume ]
            return ForwardDeclNode(name=name)
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
        else:
            raise ArbPlusError(f"Parse error: expected 'in' or '=' in for loop at line {self.peek().line}")

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
        while self.peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LE, TokenType.GE, TokenType.GT_TERM):
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
                        if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
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
                    if self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
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

class Interpreter:
    def __init__(self, script_path="."):
        if script_path != ".":
            self.script_path = os.path.dirname(os.path.abspath(script_path))
        else:
            self.script_path = os.getcwd()
        self.global_env = Environment()
        self.functions = {}
        self.overrides = {}
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
        for ov in program.overrides:
            if ov.base_name == "defaults":
                defaults = program.metadata.entries.get("_ov_defaults", {})
                for k, v in defaults.items():
                    # Gate warning/error colors
                    if k in ("warn_fg", "warn_bg", "err_fg", "err_bg") and not self.err_ov_enabled:
                        self._print_warning(f"--OV for {k} ignored: --ErrOV true; not set")
                        continue
                    self.default_colors[k] = v
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
            while True:
                try:
                    for stmt in node.body:
                        self.execute(stmt, env)
                except BreakException:
                    break
                if arb_truthy(self.eval(node.condition, env)):
                    break

        elif isinstance(node, TryNode):
            try:
                for stmt in node.try_body:
                    self.execute(stmt, env)
            except (ArbPlusError, CatchableError) as e:
                if node.catch_body:
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
            self.overrides[node.base_name] = node.new_name

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
                break
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


    def _process_newlines(self, text):
        """Convert /n to newline, //n to literal /n."""
        result = text.replace('//n', '\x00NEWLINE\x00')  # protect //n
        result = result.replace('/n', '\n')
        result = result.replace('\x00NEWLINE\x00', '/n')  # restore literal /n
        return result

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
        }

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
        if not hasattr(self, '_key_bindings'):
            self._key_bindings = {}
        key = arb_to_string(args[0])
        func_name = arb_to_string(args[1])
        self._key_bindings[key] = func_name
        return ArbBool(True)

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
        s = platform.system()
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
        # Handle colored string segments (Addition 17)
        has_colored = any(isinstance(a, ArbColoredString) for a in args)
        if has_colored:
            segments = []
            for a in args:
                if isinstance(a, ArbColoredString):
                    segments.append(a.to_ansi_string(self.default_colors))
                else:
                    # Plain string falls back to defaults
                    text = arb_to_string(a)
                    text = self._process_newlines(text)
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
            text = self._process_newlines(text)
            output = text
        # Apply color kwargs for non-segmented calls
        if not has_colored:
            fg = kwargs.get("fg")
            bg = kwargs.get("bg")
            b = kwargs.get("b")
            if fg or bg or b:
                output = self._colorize(output, fg, bg, b)
        print(output)
        return ArbString("")

    def _b_input(self, args, kwargs, env):
        prompt = arb_to_string(args[0]) if args else ""
        prompt = self._process_newlines(prompt)
        fg = kwargs.get("fg")
        bg = kwargs.get("bg")
        b = kwargs.get("b")
        if fg or bg or b:
            prompt = self._colorize(prompt, fg, bg, b)
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
        path = self._resolve_path(arb_to_string(args[0]))
        if not os.path.exists(path): raise ArbPlusError(f"File not found: {path}")
        self._open_with_default(path)
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
        now = datetime.datetime.now()
        if not args and not kwargs:
            return ArbString(now.strftime("%Y-%m-%d %H:%M:%S"))
        components = {
            "Year": now.year, "Month": now.month, "Day": now.day,
            "Hour": now.hour, "Minute": now.minute, "Second": now.second,
            "MS": now.microsecond // 1000,
        }
        parts = []
        for k, v in kwargs.items():
            if k in components: parts.append(f"{k}={components[k]}")
            else: parts.append(f"{k}={arb_to_string(v)}")
        return ArbString(", ".join(parts) if parts else now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])

    def _b_count_time(self, args, kwargs, env):
        now = datetime.datetime.now()
        if not args and not kwargs:
            return ArbString(now.strftime("%H:%M:%S.%f")[:-3])
        # Live count mode: count.time(live: true, MS: 1000) prints updated time every interval
        live = False
        interval_ms = 1000
        components = {
            "Year": now.year, "Month": now.month, "Day": now.day,
            "Hour": now.hour, "Minute": now.minute, "Second": now.second,
            "MS": now.microsecond // 1000,
        }
        for k, v in kwargs.items():
            if k == "live":
                live = (arb_to_string(v).lower() in ("true", "1", "yes"))
            elif k == "MS" and not any(kk in components for kk in kwargs if kk != "live" and kk != "MS"):
                interval_ms = int(v.py()) if hasattr(v, 'py') else int(v)
            elif k in components:
                pass  # handled below
        if live:
            # Live mode: print current time, then loop printing updates at interval
            # In a script context this blocks; the user can Ctrl-C
            try:
                while True:
                    t = datetime.datetime.now()
                    print(f"\r{t.strftime('%H:%M:%S.%f')[:-3]}", end='', flush=True)
                    time.sleep(interval_ms / 1000.0)
            except KeyboardInterrupt:
                print()
                return ArbString("stopped")
        parts = []
        for k, v in kwargs.items():
            if k in components: parts.append(f"{k}={components[k]}")
        return ArbString(", ".join(parts) if parts else now.strftime("%H:%M:%S.%f")[:-3])

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
        if member == "name": return ArbString(platform.system())
        if member == "version": return ArbString(platform.version())
        raise ArbPlusError(f"Unknown os member: {member}")

    def _b_load_ext(self, args, kwargs, env):
        path = self._resolve_path(arb_to_string(args[0]))
        lang = arb_to_string(args[1]).lower() if len(args) > 1 else "python"
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
    # ADDITION 13: REGEX / PATTERN MATCHING
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
    # ADDITION 14: NETWORK FETCH
    # =====================================================================

    def _b_fetch_url(self, args, kwargs, env):
        """fetch.url(url) -> map{ "status": int, "body": str, "headers": map, "ok": bool }
        Raises ArbPlusError on network failures (catchable via try/catch).
        """
        if not args:
            raise ArbPlusError("fetch.url() requires a URL argument")
        url = arb_to_string(args[0])
        timeout = 10
        if "timeout" in kwargs:
            timeout = int(kwargs["timeout"].py())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArbPlus/2.0"})
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
    # ADDITION 16: VARIABLE DELETION
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
    # ADDITION 17: COLORED SEGMENTS
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
    # ENHANCED open.url (Additions 18, 19)
    # =====================================================================

    def _b_run_arb(self, args, kwargs, env):
        """run.arb("filename.arb", var1: val1, var2: val2) -> runs sub-script with passed variables.
        Variables arrive as pre-populated in the child script's global scope.
        Child script can return a value via return(), which run.arb returns to caller.
        Type information travels intact (ArbValue objects passed directly).
        """
        if not args:
            raise ArbPlusError("run.arb() requires a filename argument")
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
        timeout = 30
        if "timeout" in kwargs:
            timeout = int(kwargs["timeout"].py())
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ArbPlus/2.0"})
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

    def _resolve_path(self, path):
        if os.path.isabs(path):
            return os.path.normpath(path)
        if path.startswith("./") or path.startswith("../") or path in (".", ".."):
            return os.path.normpath(os.path.join(self.script_path, path))
        return os.path.normpath(os.path.join(self.script_path, path))


# =============================================================================
# SECTION 8: ENTRY POINT
# =============================================================================

def run_file(filepath):
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
        if len(sys.argv) > 2:
            interp.script_args = sys.argv[2:]
        return interp.run(program)
    except ArbPlusError as e:
        try: interp._print_error(str(e))
        except: print(f"ArbPlus Error: {e}")
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
    if len(sys.argv) < 2:
        print("Usage: arbplus <file.arb> [args...]")
        print("       ArbPlus Language Interpreter - Climate (v0.0.21) ")
        print("       'A Really Bad Programming Language'")
        input("")
        return 1
    code = run_file(sys.argv[1])
    sys.exit(code)

if __name__ == "__main__":
    main()