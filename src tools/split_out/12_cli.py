## 12 -- 12_cli.py -- CLI entry point (run_file/main)
def _extract_auto_mode(argv):
    auto_mode = False
    auto_input_text = ""
    positional = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--auto":
            auto_mode = True
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                auto_input_text = argv[i + 1]
                i += 1
        elif arg.startswith("--auto="):
            auto_mode = True
            auto_input_text = arg.split("=", 1)[1]
        else:
            positional.append(arg)
        i += 1

    return auto_mode, auto_input_text, positional






def run_file(filepath, auto_mode=False, auto_input_text="", script_args=None):
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
        interp.auto_mode = auto_mode
        interp.auto_input_text = auto_input_text
        if script_args is not None:
            interp.script_args = script_args
        elif len(sys.argv) > 2:
            interp.script_args = sys.argv[2:]
        return interp.run(program)
    except ArbPlusError as e:
        try: interp._print_error(str(e))
        except: print(f"ArbPlus Error: {e}")
        return 1
    except ArbError as e:
        try: interp._print_error(str(e))
        except: print(f"Arb Error: {e}")
        return 1
    except ExitException as e:
        return e.code
    except Exception as e:
        try: interp._print_error(str(e))
        except: print(f"Runtime Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


def main():
    auto_mode, auto_input_text, argv = _extract_auto_mode(sys.argv[1:])
    if not argv:
        print("Usage: arbplus <file.arb> [args...]")
        print("       ArbPlus Language Interpreter - CLimate (v0.0.21) ")
        print("       'A Really Bad Programming Language'")
        return 1
    code = run_file(argv[0], auto_mode=auto_mode, auto_input_text=auto_input_text, script_args=argv[1:])
    sys.exit(code)

if __name__ == "__main__":
    main()

