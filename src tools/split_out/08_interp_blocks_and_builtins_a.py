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


