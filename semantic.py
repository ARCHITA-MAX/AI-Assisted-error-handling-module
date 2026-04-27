"""
semantic.py — Semantic Analyser for C
PCS-601 Compiler Design | Graphic Era University

Checks: (1) Undeclared variables / functions
         (2) Type mismatches (basic)
         (3) Return outside function
         (4) Argument count mismatches
         (5) Unused variables
         (6) Out-of-bounds array accesses
Outputs: Symbol table in structured format for frontend
"""

import re

from parser import (
    ProgramNode, FuncDefNode, StructDefNode, VarDeclNode,
    AssignNode, ReturnNode, IfNode, ForNode, WhileNode, DoWhileNode,
    SwitchNode, CaseNode, CallNode, BinOpNode, UnaryNode, IndexNode,
    MemberNode, IdentNode, LiteralNode, BlockNode, ExprStmtNode,
    BreakNode, ContinueNode, GotoNode, LabelNode,
    SizeofNode, CastNode, TernaryNode, ListNode
)


def detect_oob(source: str) -> list:
    """
    Detect out-of-bounds array accesses in C code.
    Belongs in the semantic phase — requires array size context (symbol info).
    Only flags actual array ACCESSES — never array declarations like int arr[5].
    """
    errors = []
    sizes  = {}
    lines  = source.splitlines()

    decl_re = re.compile(
        r'\b(?:int|char|float|double|long|short|unsigned|signed|bool)\s+\**(\w+)\s*\[(\d+)\]'
    )
    idx_re  = re.compile(r'\b(\w+)\s*\[(-?\d+)\]')
    off_re  = re.compile(r'\b(\w+)\s*\[(\w+)\s*\+\s*(\d+)\]')

    for line in lines:
        m = decl_re.search(line)
        if m:
            sizes[m.group(1)] = int(m.group(2))

    for ln, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('#'):
            continue

        for m in idx_re.finditer(line):
            name, idx = m.group(1), int(m.group(2))
            if name not in sizes:
                continue
            before = line[:m.start()].rstrip()
            is_decl = bool(re.search(
                r'\b(?:int|char|float|double|long|short|unsigned|signed|bool)\s*\**\s*$',
                before
            ))
            if is_decl:
                continue
            sz = sizes[name]
            if idx < 0:
                corrected = f'{name}[{sz + idx if sz + idx >= 0 else 0}]'
                errors.append({
                    "type": "OUT_OF_BOUNDS", "line": ln,
                    "token": m.group(0), "severity": "error",
                    "description": (
                        f"Negative index '{name}[{idx}]' in C. "
                        f"Unlike Python, C does NOT support negative indices. "
                        f"This is undefined behaviour. "
                        f"'{name}' has {sz} element(s), valid: 0 to {sz-1}."
                    ),
                    "suggestion": (
                        f"Use '{name}[{sz-1}]' for the last element, "
                        f"or '{name}[{sz + idx}]' if you intended Python-style indexing."
                    ),
                    "corrected": corrected
                })
            elif idx >= sz:
                errors.append({
                    "type": "OUT_OF_BOUNDS", "line": ln,
                    "token": m.group(0), "severity": "error",
                    "description": (
                        f"Out-of-bounds: '{name}[{idx}]' but '{name}' "
                        f"declared as size {sz}. Valid indices: 0 to {sz-1}. "
                        f"This causes undefined behaviour in C (buffer overflow)."
                    ),
                    "suggestion": f"Change to '{name}[{sz-1}]' for last element, or resize array to at least [{idx+1}].",
                    "corrected": f"{name}[{sz-1}]"
                })

        for m in off_re.finditer(line):
            name, var, offset = m.group(1), m.group(2), int(m.group(3))
            ctx = "\n".join(lines[max(0, ln-4):ln])
            if ("for" in ctx or "while" in ctx) and name in sizes:
                sz = sizes[name]
                errors.append({
                    "type": "OUT_OF_BOUNDS", "line": ln,
                    "token": m.group(0), "severity": "warning",
                    "description": (
                        f"Off-by-one risk: '{m.group(0)}' in loop. "
                        f"When '{var}' = {sz-offset}, index {sz-offset}+{offset}={sz} "
                        f"exceeds '{name}' (size={sz}, max valid={sz-1})."
                    ),
                    "suggestion": (
                        f"Change loop bound to 'i < {sz} - {offset}' "
                        f"or add guard: 'if ({var} + {offset} < {sz})'."
                    ),
                    "corrected": f"if ({var} + {offset} < {sz}) {{ {m.group(0)} }}"
                })

    return errors


def apply_oob_fixes(source: str, oob_errors: list) -> str:
    """
    Patch out-of-bounds accesses directly in the source code.
    Only fixes errors (severity='error'), skips off-by-one warnings.
    Skips array declaration lines — those are not accesses.
    """
    decl_re = re.compile(
        r'\b(?:int|char|float|double|long|short|unsigned|signed|bool)\s+\**\w+\s*\['
    )
    lines   = source.splitlines(keepends=True)
    fix_map = {}
    for e in oob_errors:
        if e.get("severity") == "error" and e.get("corrected") and e.get("token"):
            ln = e["line"]
            fix_map.setdefault(ln, []).append((e["token"], e["corrected"]))

    for ln, replacements in fix_map.items():
        idx = ln - 1
        if 0 <= idx < len(lines):
            line = lines[idx]
            if decl_re.search(line):
                continue
            for old, new in replacements:
                line = re.sub(re.escape(old), new, line, count=1)
            lines[idx] = line

    return "".join(lines)


class SemanticAnalyser:
    def __init__(self, ast, symbol_table):
        self.ast          = ast
        self.sym          = symbol_table
        self.errors       = []
        self._in_fn       = False
        self._fn_ret_type = "void"

    def _err(self, msg, line=0, token="", suggestion=""):
        self.errors.append({
            "type": "SEMANTIC_ERROR", "line": line, "token": str(token),
            "severity": "error", "description": msg,
            "suggestion": suggestion or "Review this line."
        })

    def _warn(self, msg, line=0, token=""):
        self.errors.append({
            "type": "SEMANTIC_WARNING", "line": line, "token": str(token),
            "severity": "warning", "description": msg, "suggestion": ""
        })

    def analyse(self):
        self._pre_register(self.ast)
        self._visit(self.ast)
        self._check_unused()
        return self.errors

    def get_symbol_table_data(self):
        """Returns structured symbol table for frontend display."""
        return [s.to_dict() for s in self.sym.all_symbols()]

    # ── Pre-registration pass: register all declarations first ──

    def _pre_register(self, node):
        if node is None: return
        if isinstance(node, ProgramNode):
            for s in node.body: self._pre_register(s)
        elif isinstance(node, FuncDefNode):
            self.sym.define(node.name, "function", node.ret_type, node.line,
                            params=[f"{p[0]} {p[1]}".strip() for p in (node.params or [])])
            for s in (node.body if isinstance(node.body, list) else []):
                self._pre_register(s)
        elif isinstance(node, StructDefNode):
            if node.name:
                self.sym.define(node.name, "struct", "struct", node.line)
        elif isinstance(node, VarDeclNode):
            self.sym.define(node.name, "variable", node.type_, node.line, size=node.size)
        elif isinstance(node, BlockNode):
            for s in node.stmts: self._pre_register(s)
        elif hasattr(node, '__dict__'):
            for val in vars(node).values():
                if isinstance(val, list):
                    for item in val:
                        if hasattr(item, '__dict__'): self._pre_register(item)
                elif hasattr(val, '__dict__'): self._pre_register(val)

    # ── Visitor dispatch ──

    def _visit(self, node):
        if node is None: return
        return getattr(self, "_v_" + node.__class__.__name__, self._v_generic)(node)

    def _v_generic(self, node):
        for val in vars(node).values():
            if isinstance(val, list):
                for item in val:
                    if hasattr(item, '__dict__'): self._visit(item)
            elif hasattr(val, '__dict__'): self._visit(val)

    # ── Visitor methods ──

    def _v_ProgramNode(self, n):
        for s in n.body: self._visit(s)

    def _v_FuncDefNode(self, n):
        prev_fn, prev_rt  = self._in_fn, self._fn_ret_type
        self._in_fn       = True
        self._fn_ret_type = n.ret_type
        for s in (n.body if isinstance(n.body, list) else []):
            self._visit(s)
        self._in_fn       = prev_fn
        self._fn_ret_type = prev_rt

    def _v_StructDefNode(self, n): pass

    def _v_VarDeclNode(self, n):
        if n.init is not None:
            self._visit(n.init)

    def _v_AssignNode(self, n):
        self._visit(n.value)
        target = n.target
        if isinstance(target, IdentNode):
            if not self.sym.lookup(target.name):
                self._err(
                    f"'{target.name}' is used but not declared.",
                    target.line if hasattr(target, 'line') else n.line,
                    target.name,
                    f"Declare it: 'int {target.name};' or appropriate type before use."
                )
        elif isinstance(target, IndexNode):
            self._visit(target.target)
            self._visit(target.index)

    def _v_ReturnNode(self, n):
        if not self._in_fn:
            self._err("'return' used outside a function.", n.line, "return",
                      "Wrap this in a function definition.")
        if n.value:
            self._visit(n.value)

    def _v_IfNode(self, n):
        self._visit(n.cond)
        for s in (n.body if isinstance(n.body, list) else [n.body]):
            self._visit(s)
        if n.else_body:
            for s in (n.else_body if isinstance(n.else_body, list) else [n.else_body]):
                self._visit(s)

    def _v_ForNode(self, n):
        if n.init:   self._visit(n.init)
        if n.cond:   self._visit(n.cond)
        if n.update: self._visit(n.update)
        for s in (n.body if isinstance(n.body, list) else [n.body]):
            self._visit(s)

    def _v_WhileNode(self, n):
        self._visit(n.cond)
        for s in (n.body if isinstance(n.body, list) else [n.body]):
            self._visit(s)

    def _v_DoWhileNode(self, n):
        for s in (n.body if isinstance(n.body, list) else [n.body]):
            self._visit(s)
        self._visit(n.cond)

    def _v_SwitchNode(self, n):
        self._visit(n.expr)
        for case in (n.cases or []):
            self._visit(case)

    def _v_CaseNode(self, n):
        if n.value is not None:
            self._visit(n.value)
        for s in (n.body or []):
            self._visit(s)

    def _v_BlockNode(self, n):
        for s in n.stmts: self._visit(s)

    def _v_ExprStmtNode(self, n):
        self._visit(n.expr)

    def _v_CallNode(self, n):
        sym = self.sym.lookup(n.name)
        if not sym:
            self._err(f"'{n.name}' is called but not defined.", n.line, n.name,
                      f"Declare the function before calling: void {n.name}(...);")
        elif sym.kind == "function" and sym.params:
            expected = len([p for p in sym.params if p != "..."])
            if "..." not in sym.params and len(n.args) != expected:
                self._err(
                    f"'{n.name}' expects {expected} argument(s) but {len(n.args)} given.",
                    n.line, n.name, f"Pass exactly {expected} argument(s)."
                )
        for a in n.args:
            self._visit(a)

    def _v_BinOpNode(self, n):
        self._visit(n.left)
        self._visit(n.right)
        arith_ops = {"+", "-", "*", "/", "%"}
        if n.op in arith_ops:
            left_is_str  = isinstance(n.left,  LiteralNode) and n.left.lit_type  == "string"
            right_is_str = isinstance(n.right, LiteralNode) and n.right.lit_type == "string"
            if left_is_str or right_is_str:
                str_side   = repr(n.left.value) if left_is_str else repr(n.right.value)
                other_side = "right" if left_is_str else "left"
                self._err(
                    f"Invalid operation '{n.op}': cannot use string literal {str_side} "
                    f"in arithmetic — {other_side} operand is not a string.",
                    n.line if hasattr(n, 'line') else 0,
                    str_side,
                    "Use numeric types (int, float) for arithmetic operations."
                )

    def _v_UnaryNode(self, n):   self._visit(n.operand)
    def _v_IndexNode(self, n):   self._visit(n.target); self._visit(n.index)
    def _v_MemberNode(self, n):  self._visit(n.obj)
    def _v_LiteralNode(self, n): pass

    def _v_IdentNode(self, n):
        if not self.sym.lookup(n.name):
            self._err(
                f"'{n.name}' is used but not declared.",
                n.line, n.name,
                f"Declare it: 'int {n.name};' or appropriate type before use."
            )

    def _v_TernaryNode(self, n):
        self._visit(n.cond)
        self._visit(n.then)
        self._visit(n.else_)

    def _v_SizeofNode(self, n):
        if not isinstance(n.operand, str):
            self._visit(n.operand)

    def _v_CastNode(self, n):  self._visit(n.expr)
    def _v_ListNode(self, n):  [self._visit(e) for e in n.elements]

    def _v_BreakNode(self, n):    pass
    def _v_ContinueNode(self, n): pass
    def _v_GotoNode(self, n):     pass
    def _v_LabelNode(self, n):    self._visit(n.stmt)

    def _check_unused(self):
        for sym in self.sym.all_symbols():
            if sym.kind == "variable" and not sym.used:
                self._warn(
                    f"Variable '{sym.name}' declared but never used.",
                    sym.line, sym.name
                )
