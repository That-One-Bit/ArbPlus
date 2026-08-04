## 05 -- 05_parser.py -- Parser
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
        while self.peek().type in (TokenType.SEMI, TokenType.NEWLINE):
            self.advance()

    def at(self, ttype):
        return self.peek().type == ttype

    def at_keyword(self, kw):
        return self.peek().type == TokenType.KEYWORD and self.peek().value == kw

    def parse(self):
        program = ProgramNode()
        program.metadata = MetaNode()
        program.declarations = DeclNode()
        program.body = []

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

        # Addition: --ext.ov, --mod.ov, --chd.ov flags (Set-7)
        for flag_name in ('--ext.ov', '--mod.ov', '--chd.ov'):
            while self.peek().type == TokenType.DASHDASH and self.peek().value == flag_name:
                self.advance()
                if self.peek().type in (TokenType.IDENT, TokenType.TRUE):
                    val = self.advance().value
                    if val in ('true', True):
                        program.metadata.entries["_" + flag_name.replace("--", "").replace(".", "_")] = True
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
            elif self.at(TokenType.SWAP):
                # --OV funcA <> funcB — complete swap
                self.advance()  # consume <>
                other = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideSwapNode(func_a=base, func_b=other))
            elif self.at(TokenType.LPAREN):
                # --OV base(args) new — argument-aware override with fixed args
                self.advance()  # consume (
                fixed_args = []
                while not self.at(TokenType.RPAREN):
                    fixed_args.append(self.parse_expr())
                    if self.at(TokenType.COMMA): self.advance()
                self.expect(TokenType.RPAREN)
                new = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideNode(base_name=base, new_name=new,
                                                    fixed_args=fixed_args, fixed_kwargs=None))
            else:
                new = self.expect(TokenType.IDENT).value
                program.overrides.append(OverrideNode(base, new))
            self.skip_terminators()

        self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--auto':
            auto_stmt = self.parse_auto_flag()
            program.body.append(auto_stmt)
            self.skip_terminators()
            self.skip_newlines()

        while self.peek().type == TokenType.DASHDASH and self.peek().value == '--Function':
            func = self.parse_function_def()
            program.functions[func.name] = func
            self.skip_terminators()
            self.skip_newlines()

        body = self.parse_block_until([TokenType.EOF])
        program.body.extend(body)
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
            while self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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

    def parse_auto_flag(self):
        self.advance()  # --auto
        text = None
        if self.at(TokenType.LPAREN):
            self.advance()
            if not self.at(TokenType.RPAREN):
                text = self.parse_expr()
            self.expect(TokenType.RPAREN)
        elif self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
            text = self.parse_expr()
        return AutoNode(text=text)

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
                elif self.at(TokenType.SWAP):
                    # --OV funcA <> funcB — complete swap
                    self.advance()  # consume <>
                    other = self.expect(TokenType.IDENT).value
                    statements.append(OverrideSwapNode(func_a=base, func_b=other))
                elif self.at(TokenType.LPAREN):
                    # --OV base(args) new — argument-aware override with fixed args
                    self.advance()  # consume (
                    fixed_args = []
                    while not self.at(TokenType.RPAREN):
                        fixed_args.append(self.parse_expr())
                        if self.at(TokenType.COMMA): self.advance()
                    self.expect(TokenType.RPAREN)
                    new = self.expect(TokenType.IDENT).value
                    statements.append(OverrideNode(base_name=base, new_name=new,
                                                   fixed_args=fixed_args, fixed_kwargs=None))
                else:
                    new = self.expect(TokenType.IDENT).value
                    statements.append(OverrideNode(base, new))
                self.skip_terminators()
                continue
            # Handle in-file auto mode flag
            if self.peek().type == TokenType.DASHDASH and self.peek().value == '--auto':
                statements.append(self.parse_auto_flag())
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
            if self.peek().type in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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
            if self.peek().type not in (TokenType.SEMI, TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
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
            # Accept IDENT or keyword tokens (null, true, false) as type names
            if self.peek().type == TokenType.IDENT:
                name = self.advance().value
            elif self.peek().type in (TokenType.NULL, TokenType.TRUE, TokenType.FALSE):
                name = self.advance().value
            else:
                raise ArbPlusError(f"Parse error: expected type name but got {self.peek().type} ('{self.peek().value}') at line {self.peek().line}")
            # Check if this is a typed declaration: let [int] name = value
            if self.at(TokenType.RBRACKET):
                self.advance()  # consume ] — forward declaration: let [name];
                return ForwardDeclNode(name=name)
            # else: the IDENT after [ is a type name, not the variable name
            type_hint = name  # e.g. "int", "string", "float", etc.
            # null is also valid as a type hint
            if type_hint == "null" or type_hint == "Null":
                type_hint = "null"
            self.expect(TokenType.RBRACKET)  # consume ]
            name = self.expect(TokenType.IDENT).value
            self.expect(TokenType.ASSIGN)
            value = self.parse_expr()
            return AssignNode(name=name, value=value, is_const=is_const, type_hint=type_hint)
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
        elif self.at(TokenType.LT):
            # for (i < N) — iterate from 0 to N-1
            self.advance()
            end = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            # start=0, end=N, step=1 — variable goes 0..N-1
            return ForNode(var_name=var_name, start=LiteralNode(ArbInt(0)),
                         end=end, step=LiteralNode(ArbInt(1)), body=body)
        elif self.at(TokenType.LE):
            # for (i <= N) — iterate from 0 to N inclusive
            self.advance()
            end = self.parse_expr()
            self.expect(TokenType.RPAREN)
            self.skip_newlines()
            self.expect(TokenType.LBRACE)
            body = self.parse_block_until([TokenType.RBRACE])
            self.expect(TokenType.RBRACE)
            # start=0, end=N+1, step=1 — variable goes 0..N
            return ForNode(var_name=var_name, start=LiteralNode(ArbInt(0)),
                         end=end, step=LiteralNode(ArbInt(1)), body=body)
        else:
            raise ArbPlusError(f"Parse error: expected 'in', '=', '<', or '<=' in for loop at line {self.peek().line}")

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
        while self.peek().type in (TokenType.EQ, TokenType.NEQ, TokenType.LT, TokenType.LE, TokenType.GE, TokenType.GT):
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
                        if self._try_parse_flag_arg(kwargs):
                            pass
                        elif self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
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
                    if self._try_parse_flag_arg(kwargs):
                        pass
                    elif self.peek().type == TokenType.IDENT and self.peek(1).type == TokenType.COLON:
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

    def _try_parse_flag_arg(self, kwargs):
        """Check for -w or -e flags in function call arguments. Returns True if consumed."""
        if self.peek().type == TokenType.MINUS and self.peek(1).type == TokenType.IDENT:
            flag = self.peek(1).value
            if flag == "w":
                self.advance()  # consume -
                self.advance()  # consume w
                kwargs["_warn_flag"] = LiteralNode(value=ArbBool(True))
                return True
            elif flag == "e":
                self.advance()  # consume -
                self.advance()  # consume e
                kwargs["_err_flag"] = LiteralNode(value=ArbBool(True))
                return True
        return False

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
        self.skip_newlines()
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


