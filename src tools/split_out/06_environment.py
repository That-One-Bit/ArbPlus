## 06 -- 06_environment.py -- Environment
class Environment:
    def __init__(self, parent=None):
        self.vars = {}
        self.consts = set()
        self.parent = parent

    def get(self, name):
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise ArbPlusError(f"Undefined variable: {name}")

    def set(self, name, value, is_const=False):
        if name in self.consts:
            raise ArbPlusError(f"Cannot reassign const variable: {name}")
        if is_const:
            self.consts.add(name)
        self.vars[name] = value

    def set_existing(self, name, value):
        if name in self.vars:
            if name in self.consts:
                raise ArbPlusError(f"Cannot reassign const variable: {name}")
            self.vars[name] = value
            return True
        if self.parent:
            return self.parent.set_existing(name, value)
        return False

    def declare(self, name, value, is_const=False, type_hint=""):
        if is_const:
            self.consts.add(name)
        if type_hint:
            value = arb_coerce(value, type_hint)
        self.vars[name] = value

    def has(self, name):
        if name in self.vars:
            return True
        if self.parent:
            return self.parent.has(name)
        return False

    def has_local(self, name):
        """Check if variable exists in THIS scope only (not parent)."""
        return name in self.vars

    def delete(self, name):
        """Delete a variable from THIS scope only."""
        if name in self.consts:
            self.consts.discard(name)
        if name in self.vars:
            del self.vars[name]
        else:
            raise ArbPlusError(f"Cannot delete variable '{name}': not found in this scope")


# =============================================================================
# ARBPLUS EVALUATOR
# =============================================================================


