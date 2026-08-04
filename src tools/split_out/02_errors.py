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

