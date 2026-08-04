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

