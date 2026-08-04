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


