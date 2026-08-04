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


