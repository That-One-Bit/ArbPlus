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


