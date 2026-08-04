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


