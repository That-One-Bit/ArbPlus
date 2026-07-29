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
from typing import Any, Optional as Opt
from dataclasses import dataclass, field
from enum import Enum

# =============================================================================
# SECTION 1: TYPE SYSTEM (Step 5)
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

class ArbString(ArbValue):
    def __init__(self, val):
        super().__init__(str(val), "string")

class ArbBool(ArbValue):
    def __init__(self, val):
        super().__init__(bool(val), "boolean")

class ArbArray(ArbValue):
    def __init__(self, elements, elem_type=None):
        super().__init__(elements, "array")
        self.elem_type = elem_type or (elements[0].type_name if elements else "int")
        self._size = len(elements)

class ArbList(ArbValue):
    def __init__(self, elements):
        super().__init__(elements, "list")

# --- arb type: tagged hex-encoded container ---
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
            raise ArbPlusError(f"arb index {index} out of bounds (len={len(self.val)})")
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
    return ArbString(str(val))

def arb_truthy(val):
    if isinstance(val, ArbValue):
        if val.type_name == "boolean":
            return bool(val.val)
        if val.type_name == "int":
            return val.val != 0
        if val.type_name == "float":
            return val.val != 0.0
        if val.type_name == "string":
            return len(val.val) > 0
        if val.type_name in ("array", "list", "arb"):
            return len(val.val) > 0
        return bool(val.val)
    return bool(val)

def arb_to_string(val):
    if isinstance(val, ArbValue):
        if val.type_name == "boolean":
            return "true" if val.val else "false"
        if val.type_name == "string":
            return val.val
        if val.type_name in ("array", "list"):
            return "[" + ", ".join(arb_to_string(e) for e in val.val) + "]"
        if val.type_name == "arb":
            parts = []
            for tag_name, tag_byte, hex_bytes, decoded in val.val:
                parts.append(f"0x{tag_byte:02X}({decoded})")
            return "arb{ " + ", ".join(parts) + " }"
        if val.type_name == "float":
            return str(val.val)
        return str(val.val)
    if isinstance(val, bool):
        return "true" if val else "false"
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

# =============================================================================
# SECTION 2: ERROR TYPES
# =============================================================================

class ArbPlusError(Exception):
    pass

class BreakException(Exception):
    pass

class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class ExitException(Exception):
    def __init__(self, code=0):
        self.code = code

# =============================================================================
# SECTION 3: LEXER
# =============================================================================

class TokenType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    TRUE = "TRUE"
    FALSE = "FALSE"
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
    NEWLINE = "NEWLINE"
    EOF = "EOF"

KEYWORDS = {
    "if", "elif", "else", "for", "while", "break", "return",
    "exit", "quit", "end", "not", "const", "let", "true", "false",
    "in", "to", "step",
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

            # Comments
            if ch == '/' and self.peek(1) == '/':
                while self.pos < len(self.source) and self.peek() not in (';', '>', '\n'):
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
                # Read raw code until matching }
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
            if ch == 'a' and self.peek(1) == 'r' and self.peek(2) == 'b' and self.peek(3) == '{':
                self.advance()
                self.advance()
                self.advance()
                self.advance()
                self.tokens.append(Token(TokenType.ARB_LIT, 'arb{', self.line, self.col))
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
            }
            if ch in single_map:
                self.tokens.append(Token(single_map[ch], ch, self.line, self.col))
                self.advance()
                continue

            raise ArbPlusError(f"Lexer error: unexpected character '{ch}' at line {self.line}, col {self.col}")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.col))
        return self.tokens

    def read_string(self, quote):
        self.advance()
        result = []
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
            else:
                result.append(self.advance())
        if self.pos >= len(self.source):
            raise ArbPlusError(f"Lexer error: unterminated string at line {self.line}")
        self.advance()
        self.tokens.append(Token(TokenType.STRING, ''.join(result), self.line, self.col))

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
        elif word == "not":
            self.tokens.append(Token(TokenType.NOT, word, self.line, self.col))
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

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--OV':
            self.advance()
            base = self.expect(TokenType.IDENT).value
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

        if tok.type == TokenType.KEYWORD and tok.value == "break":
            self.advance()
            label = ""
            if self.at(TokenType.IDENT):
                label = self.advance().value
            return BreakNode(label=label)

        if tok.type == TokenType.KEYWORD and tok.value == "return":
            self.advance()
            if self.peek().type in (TokenType.SEMI, TokenType.GT_TERM, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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

        if tok.type == TokenType.C_BLOCK:
            return self.parse_c_block()

        if tok.type == TokenType.CMD_BLOCK:
            return self.parse_shell_block('cmd')

        if tok.type == TokenType.PS_BLOCK:
            return self.parse_shell_block('ps')

        if tok.type == TokenType.ARB_LIT:
            expr = self.parse_arb_literal()
            return ExprStmtNode(expr=expr)

        return self.parse_expr_statement()

    def parse_var_decl(self):
        kw = self.advance().value
        is_const = (kw == "const")
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

    def parse_c_block(self):
        self.advance()  # c{
        # Next token is the raw code as a STRING
        if self.at(TokenType.STRING):
            code = self.advance().value
        else:
            code = ''
        if self.at(TokenType.RBRACE):
            self.advance()
        return CBlockNode(code=code)

    def parse_shell_block(self, shell_type):
        self.advance()  # cmd{ or ps{
        if self.at(TokenType.STRING):
            code = self.advance().value
        else:
            code = ''
        if self.at(TokenType.RBRACE):
            self.advance()
        return ShellBlockNode(shell_type=shell_type, code=code)

    def parse_expr_statement(self):
        expr = self.parse_expr()
        if self.at(TokenType.ASSIGN) and isinstance(expr, VarNode):
            self.advance()
            value = self.parse_expr()
            return AssignNode(name=expr.name, value=value)
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
                member = self.expect(TokenType.IDENT).value
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
                    if isinstance(expr, VarNode):
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
        if tok.type == TokenType.TRUE:
            self.advance()
            return LiteralNode(value=ArbBool(True))
        if tok.type == TokenType.FALSE:
            self.advance()
            return LiteralNode(value=ArbBool(False))
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
        raise ArbPlusError(f"Parse error: unexpected token {tok.type.name} ('{tok.value}') at line {tok.line}")

    def parse_kwarg_value(self):
        """Parse a named argument value. Bare identifiers are treated as strings (e.g. color names)."""
        tok = self.peek()
        if tok.type == TokenType.IDENT:
            self.advance()
            return LiteralNode(value=ArbString(tok.value))
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


# =============================================================================
# SECTION 6: ENVIRONMENT
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


# =============================================================================
# SECTION 7: INTERPRETER / EVALUATOR
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
        self._setup_builtins()

    def run(self, program):
        self.metadata = program.metadata.entries if program.metadata else {}
        if program.declarations:
            self.declared_shells = set(program.declarations.uses)
            self.declared_imports = set(program.declarations.imports)
        for ov in program.overrides:
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
            val = self.eval(node.value, env) if node.value else ArbString("")
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

        if isinstance(node, MemberNode):
            if isinstance(node.target, VarNode):
                tn = node.target.name
                if tn == "locale":
                    return self.eval_locale_member(node.member, env)
                if tn == "os":
                    return self.eval_os_member(node.member, env)
            target_val = self.eval(node.target, env)
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

        if op == "==": return ArbBool(left.py() == right.py())
        if op == "!=": return ArbBool(left.py() != right.py())
        if op == "<": return ArbBool(left.py() < right.py())
        if op == "<=": return ArbBool(left.py() <= right.py())
        if op == ">": return ArbBool(left.py() > right.py())
        if op == ">=": return ArbBool(left.py() >= right.py())
        if op == "..": return ArbString(arb_to_string(left) + arb_to_string(right))

        lv = left.py()
        rv = right.py()
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
        # Override: --OV BaseName NewName means calling NewName invokes BaseName
        for base, new_name in self.overrides.items():
            if name == new_name:
                name = base
                break
        args = [self.eval(a, env) for a in node.args]
        kwargs = {k: self.eval(v, env) for k, v in node.kwargs.items()}

        if name in self.functions:
            return self.call_user_function(name, args, kwargs, env)
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
        code = self._interpolate_vars(node.code, env)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.c', mode='w', delete=False) as f:
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
        code = self._interpolate_vars(node.code, env)
        if node.shell_type == 'cmd':
            if platform.system() != "Windows":
                result = subprocess.run(["sh", "-c", code], capture_output=True, text=True)
            else:
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
            "readFile": self._b_readfile, "fileExists": self._b_fileexists,
            "writeFile": self._b_writefile, "buildFile": self._b_buildfile,
            "encodeImage": self._b_encode_image, "decodeImage": self._b_decode_image,
            "openMedia": self._b_open_media, "openBrowser": self._b_open_browser,
            "addr": self._b_addr, "txtRC": self._b_txtrc,
            "addr.hex": self._b_addr_hex, "addr.binary": self._b_addr_binary,
            "addr.meta": self._b_addr_meta,
            "dir.list": self._b_dir_list, "dir.name": self._b_dir_name,
            "dir.make": self._b_dir_make, "dir.del": self._b_dir_del,
            "snap.time": self._b_snap_time, "count.time": self._b_count_time,
            "wait": self._b_wait, "cs": self._b_cs,
            "locale.prf": self._b_locale_prf, "locale.check": self._b_locale_check,
            "locale.alt": self._b_locale_alt, "locale.cur": self._b_locale_cur,
            "battery": self._b_battery, "network": self._b_network,
            "screen": self._b_screen,
            "os.name": self._b_os_name, "os.version": self._b_os_version,
            "loadExt": self._b_load_ext,
        }

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
        return ArbString(arb_to_string(args[0]).replace(arb_to_string(args[1]), arb_to_string(args[2])))

    def _b_contains(self, args, kwargs, env):
        return ArbBool(arb_to_string(args[1]) in arb_to_string(args[0]))

    def _b_print(self, args, kwargs, env):
        text = " ".join(arb_to_string(a) for a in args)
        fg = kwargs.get("fg")
        bg = kwargs.get("bg")
        if fg or bg:
            text = self._colorize(text, fg, bg)
        print(text)
        return ArbString("")

    def _b_input(self, args, kwargs, env):
        prompt = arb_to_string(args[0]) if args else ""
        fg = kwargs.get("fg")
        bg = kwargs.get("bg")
        if fg or bg:
            prompt = self._colorize(prompt, fg, bg)
        try:
            result = input(prompt)
        except EOFError:
            result = ""
        return ArbString(result)

    def _colorize(self, text, fg, bg):
        FG_MAP = {
            "black": "30", "red": "31", "green": "32", "yellow": "33",
            "blue": "34", "magenta": "35", "cyan": "36", "white": "37",
            "bright_black": "90", "bright_red": "91", "bright_green": "92",
            "bright_yellow": "93", "bright_blue": "94", "bright_magenta": "95",
            "bright_cyan": "96", "bright_white": "97",
        }
        BG_MAP = {
            "black": "40", "red": "41", "green": "42", "yellow": "43",
            "blue": "44", "magenta": "45", "cyan": "46", "white": "47",
        }
        codes = []
        if fg:
            f = arb_to_string(fg) if isinstance(fg, ArbValue) else fg
            if f in FG_MAP: codes.append(FG_MAP[f])
            elif f.startswith("#"):
                codes.append(f"38;2;{int(f[1:3],16)};{int(f[3:5],16)};{int(f[5:7],16)}")
        if bg:
            b = arb_to_string(bg) if isinstance(bg, ArbValue) else bg
            if b in BG_MAP: codes.append(BG_MAP[b])
            elif b.startswith("#"):
                codes.append(f"48;2;{int(b[1:3],16)};{int(b[3:5],16)};{int(b[5:7],16)}")
        if codes:
            return f"\033[{';'.join(codes)}m{text}\033[0m"
        return text

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
        row = int(args[0].py())
        col = int(args[1].py())
        if len(args) > 2:
            data = arb_to_string(args[2])
        elif env.has("__last_read"):
            data = arb_to_string(env.get("__last_read"))
        else:
            raise ArbPlusError("txtRC requires data or a prior readFile call")
        lines = data.strip().split('\n')
        if row < 1 or row > len(lines):
            raise ArbPlusError(f"txtRC row {row} out of bounds (1-{len(lines)})")
        line = lines[row - 1]
        if '\t' in line: cells = line.split('\t')
        elif ',' in line: cells = line.split(',')
        elif ';' in line: cells = line.split(';')
        else: cells = line.split()
        if col < 1 or col > len(cells):
            raise ArbPlusError(f"txtRC column {col} out of bounds (1-{len(cells)})")
        return ArbString(cells[col - 1].strip())

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
        if not os.path.exists(path): raise ArbPlusError(f"Directory not found: {path}")
        if not os.path.isdir(path): raise ArbPlusError(f"Not a directory: {path}")
        shutil.rmtree(path)
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
        components = {
            "Year": now.year, "Month": now.month, "Day": now.day,
            "Hour": now.hour, "Minute": now.minute, "Second": now.second,
            "MS": now.microsecond // 1000,
        }
        parts = []
        for k, v in kwargs.items():
            if k in components: parts.append(f"{k}={components[k]}")
        return ArbString(", ".join(parts) if parts else now.strftime("%H:%M:%S.%f")[:-3])

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
        return interp.run(program)
    except ArbPlusError as e:
        print(f"ArbPlus Error: {e}")
        return 1
    except ExitException as e:
        return e.code
    except Exception as e:
        print(f"Runtime Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def main():
    if len(sys.argv) < 2:
        print("Usage: arbplus <file.arb> [args...]")
        print("       ArbPlus Language Interpreter v1.0")
        print("       'A Really Bad Programming Language'")
        return 1
    code = run_file(sys.argv[1])
    sys.exit(code)

if __name__ == "__main__":
    main()
