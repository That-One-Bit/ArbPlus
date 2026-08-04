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

