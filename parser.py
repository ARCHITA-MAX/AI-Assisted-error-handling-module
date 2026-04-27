"""
parser.py — Syntax Analyser for C Language

Builds an AST from C token stream.
Generates: (1) Parse Tree (concrete syntax tree as nested dict)
            (2) Symbol Table (with type info for C types)
"""

import re


# ═══════════════════════════════════════════════════
#  Symbol Table
# ═══════════════════════════════════════════════════

class Symbol:
    def __init__(self, name, kind, type_="unknown", line=0, scope="global"):
        self.name   = name
        self.kind   = kind      # variable | function | parameter | struct | typedef | builtin
        self.type_  = type_     # int | char | float | double | void | pointer | array | struct ...
        self.line   = line
        self.scope  = scope
        self.used   = False
        self.params = []
        self.size   = None      # for arrays

    def to_dict(self):
        d = {
            "name":  self.name,
            "kind":  self.kind,
            "type":  self.type_,
            "line":  self.line,
            "scope": self.scope,
            "used":  self.used,
        }
        if self.size is not None:
            d["size"] = self.size
        if self.params:
            d["params"] = self.params
        return d


class SymbolTable:
    BUILTINS = {
        "printf","scanf","malloc","free","calloc","realloc",
        "strlen","strcpy","strcat","strcmp","strncpy",
        "memcpy","memset","abs","fabs","sqrt","pow","rand","srand",
        "exit","atoi","atof","sprintf","fprintf","main",
        "NULL","true","false","EOF","stdin","stdout","stderr",
    }
    C_TYPES = {"int","char","float","double","void","long","short",
               "unsigned","signed","bool","size_t","FILE","string"}

    def __init__(self):
        self._scopes = [{"name": "global", "symbols": {}}]
        for name in self.BUILTINS:
            self._scopes[0]["symbols"][name] = Symbol(name, "builtin", "builtin", 0, "global")

    def current_scope_name(self):
        return self._scopes[-1]["name"]

    def enter_scope(self, name="block"):
        self._scopes.append({"name": name, "symbols": {}})

    def exit_scope(self):
        if len(self._scopes) > 1:
            self._scopes.pop()

    def define(self, name, kind, type_="unknown", line=0, params=None, size=None):
        scope = self._scopes[-1]
        existing = scope["symbols"].get(name)
        if existing and existing.kind not in ("builtin",):
            return False, existing
        sym = Symbol(name, kind, type_, line, scope["name"])
        if params:
            sym.params = params
        if size is not None:
            sym.size = size
        scope["symbols"][name] = sym
        return True, None

    def lookup(self, name):
        for scope in reversed(self._scopes):
            if name in scope["symbols"]:
                sym = scope["symbols"][name]
                sym.used = True
                return sym
        return None

    def all_symbols(self):
        result = []
        for scope in self._scopes:
            for sym in scope["symbols"].values():
                if sym.kind != "builtin":
                    result.append(sym)
        return result

    def dump(self):
        rows = []
        for scope in self._scopes:
            for sym in scope["symbols"].values():
                if sym.kind != "builtin":
                    rows.append(
                        f"  {scope['name']:<12} | {sym.name:<20} {sym.kind:<12} "
                        f"{sym.type_:<12} line={sym.line}"
                    )
        return "Symbol Table:\n" + ("  (empty)" if not rows else "\n".join(rows))


# ═══════════════════════════════════════════════════
#  AST Node Definitions
# ═══════════════════════════════════════════════════

class Node:
    def node_type(self): return self.__class__.__name__

class ProgramNode(Node):
    def __init__(self, body): self.body = body
class FuncDefNode(Node):
    def __init__(self, ret_type, name, params, body, line=0):
        self.ret_type=ret_type; self.name=name; self.params=params
        self.body=body; self.line=line
class StructDefNode(Node):
    def __init__(self, name, members, line=0):
        self.name=name; self.members=members; self.line=line
class VarDeclNode(Node):
    def __init__(self, type_, name, init=None, line=0, is_array=False, size=None):
        self.type_=type_; self.name=name; self.init=init
        self.line=line; self.is_array=is_array; self.size=size
class AssignNode(Node):
    def __init__(self, target, op, value, line=0):
        self.target=target; self.op=op; self.value=value; self.line=line
class ReturnNode(Node):
    def __init__(self, value, line=0): self.value=value; self.line=line
class IfNode(Node):
    def __init__(self, cond, body, else_body=None, line=0):
        self.cond=cond; self.body=body; self.else_body=else_body; self.line=line
class ForNode(Node):
    def __init__(self, init, cond, update, body, line=0):
        self.init=init; self.cond=cond; self.update=update; self.body=body; self.line=line
class WhileNode(Node):
    def __init__(self, cond, body, line=0):
        self.cond=cond; self.body=body; self.line=line
class DoWhileNode(Node):
    def __init__(self, body, cond, line=0):
        self.body=body; self.cond=cond; self.line=line
class SwitchNode(Node):
    def __init__(self, expr, cases, line=0):
        self.expr=expr; self.cases=cases; self.line=line
class CaseNode(Node):
    def __init__(self, value, body, line=0):
        self.value=value; self.body=body; self.line=line
class CallNode(Node):
    def __init__(self, name, args, line=0):
        self.name=name; self.args=args; self.line=line
class BinOpNode(Node):
    def __init__(self, left, op, right):
        self.left=left; self.op=op; self.right=right
class UnaryNode(Node):
    def __init__(self, op, operand, prefix=True):
        self.op=op; self.operand=operand; self.prefix=prefix
class IndexNode(Node):
    def __init__(self, target, index):
        self.target=target; self.index=index
class MemberNode(Node):
    def __init__(self, obj, member, arrow=False):
        self.obj=obj; self.member=member; self.arrow=arrow
class IdentNode(Node):
    def __init__(self, name, line=0): self.name=name; self.line=line
class LiteralNode(Node):
    def __init__(self, value, lit_type="int"):
        self.value=value; self.lit_type=lit_type
class BlockNode(Node):
    def __init__(self, stmts): self.stmts=stmts
class ExprStmtNode(Node):
    def __init__(self, expr, line=0): self.expr=expr; self.line=line
class BreakNode(Node): pass
class ContinueNode(Node): pass
class GotoNode(Node):
    def __init__(self, label): self.label=label
class LabelNode(Node):
    def __init__(self, name, stmt): self.name=name; self.stmt=stmt
class SizeofNode(Node):
    def __init__(self, operand): self.operand=operand
class CastNode(Node):
    def __init__(self, type_, expr): self.type_=type_; self.expr=expr
class TernaryNode(Node):
    def __init__(self, cond, then, else_):
        self.cond=cond; self.then=then; self.else_=else_


# ═══════════════════════════════════════════════════
#  Parse Tree Builder
# ═══════════════════════════════════════════════════

def ast_to_parse_tree(node, label=None):
    """Convert AST node to a nested dict representing the parse/syntax tree."""
    if node is None:
        return {"label": "null", "children": []}

    def leaf(lbl, val):
        return {"label": lbl, "value": str(val), "children": []}

    def branch(lbl, *children):
        return {"label": lbl, "children": [c for c in children if c is not None]}

    def many(lbl, nodes):
        return branch(lbl, *[ast_to_parse_tree(n) for n in (nodes or [])])

    if isinstance(node, ProgramNode):
        return many("Program", node.body)

    if isinstance(node, FuncDefNode):
        params = [branch("Param", leaf("Type", p[0]), leaf("Name", p[1]))
                  for p in (node.params or [])]
        return branch("FuncDef",
            leaf("ReturnType", node.ret_type),
            leaf("Name", node.name),
            branch("Params", *params),
            ast_to_parse_tree(BlockNode(node.body) if isinstance(node.body, list) else node.body)
        )

    if isinstance(node, StructDefNode):
        members = [branch("Member", leaf("Field", str(m))) for m in (node.members or [])]
        return branch("StructDef", leaf("Name", node.name), branch("Members", *members))

    if isinstance(node, VarDeclNode):
        children = [leaf("Type", node.type_), leaf("Name", node.name)]
        if node.is_array and node.size is not None:
            children.append(leaf("ArraySize", node.size))
        if node.init is not None:
            children.append(branch("Init", ast_to_parse_tree(node.init)))
        return branch("VarDecl", *children)

    if isinstance(node, AssignNode):
        return branch("Assign",
            ast_to_parse_tree(node.target) if isinstance(node.target, Node)
                else leaf("Target", node.target),
            leaf("Op", node.op),
            ast_to_parse_tree(node.value)
        )

    if isinstance(node, ReturnNode):
        children = []
        if node.value:
            children.append(ast_to_parse_tree(node.value))
        return branch("Return", *children)

    if isinstance(node, IfNode):
        children = [
            branch("Condition", ast_to_parse_tree(node.cond)),
            branch("Then", ast_to_parse_tree(BlockNode(node.body)
                           if isinstance(node.body, list) else node.body))
        ]
        if node.else_body:
            children.append(branch("Else",
                ast_to_parse_tree(BlockNode(node.else_body)
                                  if isinstance(node.else_body, list) else node.else_body)))
        return branch("IfStatement", *children)

    if isinstance(node, ForNode):
        return branch("ForLoop",
            branch("Init",   ast_to_parse_tree(node.init) if node.init else leaf("Init","empty")),
            branch("Cond",   ast_to_parse_tree(node.cond) if node.cond else leaf("Cond","empty")),
            branch("Update", ast_to_parse_tree(node.update) if node.update else leaf("Update","empty")),
            branch("Body",   ast_to_parse_tree(BlockNode(node.body)
                                               if isinstance(node.body, list) else node.body))
        )

    if isinstance(node, WhileNode):
        return branch("WhileLoop",
            branch("Condition", ast_to_parse_tree(node.cond)),
            branch("Body", ast_to_parse_tree(BlockNode(node.body)
                           if isinstance(node.body, list) else node.body))
        )

    if isinstance(node, DoWhileNode):
        return branch("DoWhileLoop",
            branch("Body", ast_to_parse_tree(BlockNode(node.body)
                           if isinstance(node.body, list) else node.body)),
            branch("Condition", ast_to_parse_tree(node.cond))
        )

    if isinstance(node, SwitchNode):
        return branch("Switch",
            branch("Expr", ast_to_parse_tree(node.expr)),
            many("Cases", node.cases)
        )

    if isinstance(node, CaseNode):
        return branch("Case",
            leaf("Value", node.value if node.value is not None else "default"),
            many("Body", node.body)
        )

    if isinstance(node, BlockNode):
        return many("Block", node.stmts)

    if isinstance(node, CallNode):
        return branch("FuncCall",
            leaf("Name", node.name),
            many("Args", node.args)
        )

    if isinstance(node, BinOpNode):
        return branch("BinaryOp",
            ast_to_parse_tree(node.left),
            leaf("Op", node.op),
            ast_to_parse_tree(node.right)
        )

    if isinstance(node, UnaryNode):
        op_node = leaf("Op", node.op)
        expr_node = ast_to_parse_tree(node.operand)
        children = [op_node, expr_node] if node.prefix else [expr_node, op_node]
        return branch("UnaryOp", *children)

    if isinstance(node, IndexNode):
        return branch("ArrayIndex",
            ast_to_parse_tree(node.target),
            branch("Index", ast_to_parse_tree(node.index))
        )

    if isinstance(node, MemberNode):
        return branch("MemberAccess",
            ast_to_parse_tree(node.obj),
            leaf("Op", "->" if node.arrow else "."),
            leaf("Member", node.member)
        )

    if isinstance(node, IdentNode):
        return leaf("Identifier", node.name)

    if isinstance(node, LiteralNode):
        return leaf(f"Literal({node.lit_type})", node.value)

    if isinstance(node, ExprStmtNode):
        return branch("ExprStatement", ast_to_parse_tree(node.expr))

    if isinstance(node, TernaryNode):
        return branch("Ternary",
            branch("Cond", ast_to_parse_tree(node.cond)),
            branch("Then", ast_to_parse_tree(node.then)),
            branch("Else", ast_to_parse_tree(node.else_))
        )

    if isinstance(node, SizeofNode):
        op = ast_to_parse_tree(node.operand) if isinstance(node.operand, Node) else leaf("Type", node.operand)
        return branch("Sizeof", op)

    if isinstance(node, CastNode):
        return branch("Cast", leaf("Type", node.type_), ast_to_parse_tree(node.expr))

    if isinstance(node, BreakNode):    return leaf("Break", "break")
    if isinstance(node, ContinueNode): return leaf("Continue", "continue")
    if isinstance(node, GotoNode):     return leaf("Goto", node.label)

    return leaf(node.__class__.__name__, "?")


# ═══════════════════════════════════════════════════
#  C Parser
# ═══════════════════════════════════════════════════

C_TYPES = {"int","char","float","double","void","long","short",
           "unsigned","signed","bool","size_t","string"}
C_TYPE_QUALIFIERS = {"const","static","extern","register","volatile","auto"}


class Parser:
    def __init__(self, tokens):
        self.tokens       = [t for t in tokens if t.type not in ("NEWLINE","PREPROCESSOR")]
        self.pos          = 0
        self.errors       = []
        self.symbol_table = SymbolTable()
        self._current_func = None

    # ── Token navigation ──────────────────────────
    def _peek(self, off=0):
        i = self.pos + off
        return self.tokens[i] if i < len(self.tokens) else None

    def _cur(self): return self._peek(0)

    def _advance(self):
        t = self.tokens[self.pos] if self.pos < len(self.tokens) else None
        if self.pos < len(self.tokens): self.pos += 1
        return t

    def _match(self, *values):
        t = self._cur()
        if t and t.value in values: return self._advance()
        return None

    def _expect(self, value):
        t = self._cur()
        got = t.value if t else "EOF"
        if t and t.value == value: return self._advance()
        ln = t.line if t else 0
        self._err(f"Expected '{value}' but got '{got}'.", ln, got)
        return None

    def _expect_semi(self):
        """Expect a semicolon. If missing, report error on the PREVIOUS token's line
        (i.e. the line where the statement ended without a semicolon)."""
        t = self._cur()
        if t and t.value == ";":
            return self._advance()
        # Report on previous token's line so the error points at the statement missing the ';'
        prev = self.tokens[self.pos - 1] if self.pos > 0 else None
        ln = prev.line if prev else (t.line if t else 0)
        # Get the actual source line content for a clearer message
        self._err(
            f"Missing semicolon — add ';' at the end of line {ln}.",
            ln, ";",
            suggestion=f"Add a semicolon ';' at the end of line {ln}."
        )
        return None

    def _err(self, msg, line=0, token="", suggestion="Check C syntax at this line."):
        self.errors.append({
            "type": "SYNTAX_ERROR", "line": line, "token": str(token),
            "severity": "error", "description": msg,
            "suggestion": suggestion
        })

    def _is_type(self):
        t = self._cur()
        if not t: return False
        return t.value in C_TYPES or t.value in C_TYPE_QUALIFIERS or t.value == "struct"

    def _parse_type(self):
        """Parse a C type specifier, return type string."""
        parts = []
        while self._cur() and (self._cur().value in C_TYPES | C_TYPE_QUALIFIERS
                                or self._cur().value == "struct"):
            if self._cur().value == "struct":
                parts.append(self._advance().value)
                if self._cur() and self._cur().type == "IDENTIFIER":
                    parts.append(self._advance().value)
            else:
                parts.append(self._advance().value)
        # pointer
        while self._cur() and self._cur().value == "*":
            parts.append(self._advance().value)
        return " ".join(parts) if parts else "int"

    # ── Top-level ──────────────────────────────────
    def parse(self):
        stmts = []
        while self._cur():
            s = self._parse_top_level()
            if s: stmts.append(s)
        ast = ProgramNode(stmts)
        parse_tree = ast_to_parse_tree(ast)
        return ast, parse_tree

    def _parse_top_level(self):
        t = self._cur()
        if not t: return None

        # Struct definition
        if t.value == "struct":
            return self._parse_struct_def()

        # typedef
        if t.value == "typedef":
            self._skip_to(";"); self._match(";"); return None

        # Type keyword → could be function or variable declaration
        if self._is_type():
            return self._parse_func_or_var_decl(top_level=True)

        # Stray semicolon
        if t.value == ";":
            self._advance(); return None

        self._advance(); return None  # skip unknown

    def _parse_struct_def(self):
        line = self._cur().line
        self._advance()  # consume 'struct'
        name = ""
        if self._cur() and self._cur().type == "IDENTIFIER":
            name = self._advance().value
        members = []
        if self._match("{"):
            while self._cur() and self._cur().value != "}":
                if self._is_type():
                    type_ = self._parse_type()
                    mname = self._advance().value if self._cur() and self._cur().type == "IDENTIFIER" else "?"
                    members.append((type_, mname))
                    self._match(";")
                else:
                    self._advance()
            self._expect("}")
        self._match(";")
        if name:
            self.symbol_table.define(name, "struct", "struct", line)
        return StructDefNode(name, members, line)

    def _parse_func_or_var_decl(self, top_level=False):
        start = self.pos
        line  = self._cur().line if self._cur() else 0
        type_ = self._parse_type()

        if not self._cur(): return None
        if self._cur().type not in ("IDENTIFIER","KEYWORD"):
            self._advance(); return None

        name = self._advance().value

        # Function definition
        if self._cur() and self._cur().value == "(":
            return self._parse_func_def(type_, name, line)

        # Array declaration
        if self._cur() and self._cur().value == "[":
            return self._parse_array_decl(type_, name, line)

        # Scalar variable declaration (possibly with init)
        init = None
        if self._match("="):
            init = self._parse_expr()
        self._expect_semi()
        # Multiple declarators: int a, b, c;
        while self._match(","):
            extra_name = self._advance().value if self._cur() and self._cur().type == "IDENTIFIER" else ""
            extra_init = None
            if self._match("="):
                extra_init = self._parse_expr()
            if extra_name:
                self.symbol_table.define(extra_name, "variable", type_, line)
        self.symbol_table.define(name, "variable", type_, line)
        return VarDeclNode(type_, name, init, line)

    def _parse_array_decl(self, type_, name, line):
        self._advance()  # consume '['
        size_expr = None
        sz_val = None
        if self._cur() and self._cur().value != "]":
            size_expr = self._parse_expr()
            if isinstance(size_expr, LiteralNode):
                sz_val = size_expr.value
        self._expect("]")
        init = None
        if self._match("="):
            init = self._parse_initializer()
        self._match(";")
        self.symbol_table.define(name, "variable", f"{type_}[]", line, size=sz_val)
        return VarDeclNode(type_, name, init, line, is_array=True, size=sz_val)

    def _parse_initializer(self):
        """Parse { ... } initializer list."""
        if not self._match("{"): return self._parse_expr()
        elems = []
        while self._cur() and self._cur().value != "}":
            elems.append(self._parse_expr())
            if not self._match(","): break
        self._expect("}")
        return ListNode(elems)

    def _parse_func_def(self, ret_type, name, line):
        self._expect("(")
        params = []
        self.symbol_table.define(name, "function", ret_type, line)
        self.symbol_table.enter_scope(name)
        self._current_func = name
        while self._cur() and self._cur().value != ")":
            if self._cur().value == "void" and self._peek(1) and self._peek(1).value == ")":
                self._advance(); break
            if self._match("..."):
                params.append(("...", "..."))
                break
            ptype = self._parse_type()
            pname = ""
            if self._cur() and self._cur().type in ("IDENTIFIER","KEYWORD") and self._cur().value not in (")",","):
                pname = self._advance().value
            # array param: int arr[]
            if self._cur() and self._cur().value == "[":
                self._advance(); self._match("]")
                ptype += "[]"
            params.append((ptype, pname))
            if pname:
                self.symbol_table.define(pname, "parameter", ptype, line)
            if not self._match(","):
                break
        self._expect(")")
        body = []
        if self._cur() and self._cur().value == "{":
            body = self._parse_block()
        elif self._cur() and self._cur().value == ";":
            self._advance()  # forward declaration
        self.symbol_table.exit_scope()
        self._current_func = None
        sym = self.symbol_table.lookup(name)
        if sym: sym.params = [f"{p[0]} {p[1]}".strip() for p in params]
        return FuncDefNode(ret_type, name, params, body, line)

    def _parse_block(self):
        """Parse { stmt* }"""
        self._expect("{")
        stmts = []
        depth = 0
        while self._cur() and self._cur().value != "}":
            s = self._parse_stmt()
            if s: stmts.append(s)
            depth += 1
            if depth > 500: break
        self._expect("}")
        return stmts

    def _parse_stmt(self):
        t = self._cur()
        if not t: return None
        v = t.value

        if v == "{":
            stmts = self._parse_block()
            return BlockNode(stmts)
        if v == "if":     return self._parse_if()
        if v == "for":    return self._parse_for()
        if v == "while":  return self._parse_while()
        if v == "do":     return self._parse_do_while()
        if v == "switch": return self._parse_switch()
        if v == "return": return self._parse_return()
        if v == "break":  self._advance(); self._match(";"); return BreakNode()
        if v == "continue": self._advance(); self._match(";"); return ContinueNode()
        if v == "goto":
            self._advance()
            lbl = self._advance().value if self._cur() else "?"
            self._match(";"); return GotoNode(lbl)
        if v == ";":      self._advance(); return None

        # Declaration inside block
        if self._is_type():
            return self._parse_func_or_var_decl(top_level=False)

        # Label: identifier ':'
        if (t.type == "IDENTIFIER" and self._peek(1) and self._peek(1).value == ":"):
            lbl = self._advance().value; self._advance()
            stmt = self._parse_stmt()
            return LabelNode(lbl, stmt)

        # Expression statement
        expr = self._parse_expr()
        if expr is None: self._advance(); return None
        self._expect_semi()
        return ExprStmtNode(expr, t.line)

    def _parse_if(self):
        line = self._cur().line; self._advance()
        self._expect("("); cond = self._parse_expr(); self._expect(")")
        body = self._parse_stmt_or_block()
        else_body = None
        if self._cur() and self._cur().value == "else":
            self._advance()
            else_body = self._parse_stmt_or_block()
        return IfNode(cond, body, else_body, line)

    def _parse_stmt_or_block(self):
        if self._cur() and self._cur().value == "{":
            return self._parse_block()
        return [self._parse_stmt()]

    def _parse_for(self):
        line = self._cur().line; self._advance()
        self._expect("(")
        self.symbol_table.enter_scope("for")
        init = None
        if self._cur() and self._cur().value != ";":
            if self._is_type():
                init = self._parse_func_or_var_decl(top_level=False)
            else:
                init = self._parse_expr(); self._match(";")
        else:
            self._match(";")
        cond = None
        if self._cur() and self._cur().value != ";":
            cond = self._parse_expr()
        self._match(";")
        update = None
        if self._cur() and self._cur().value != ")":
            update = self._parse_expr()
        self._expect(")")
        body = self._parse_stmt_or_block()
        self.symbol_table.exit_scope()
        return ForNode(init, cond, update, body, line)

    def _parse_while(self):
        line = self._cur().line; self._advance()
        self._expect("("); cond = self._parse_expr(); self._expect(")")
        body = self._parse_stmt_or_block()
        return WhileNode(cond, body, line)

    def _parse_do_while(self):
        line = self._cur().line; self._advance()
        body = self._parse_stmt_or_block()
        self._expect("while"); self._expect("(")
        cond = self._parse_expr()
        self._expect(")"); self._match(";")
        return DoWhileNode(body, cond, line)

    def _parse_switch(self):
        line = self._cur().line; self._advance()
        self._expect("("); expr = self._parse_expr(); self._expect(")")
        self._expect("{")
        cases = []
        while self._cur() and self._cur().value != "}":
            if self._cur().value == "case":
                self._advance()
                val = self._parse_expr()
                self._expect(":")
                body = []
                while self._cur() and self._cur().value not in ("case","default","}"):
                    s = self._parse_stmt()
                    if s: body.append(s)
                cases.append(CaseNode(val, body, line))
            elif self._cur().value == "default":
                self._advance(); self._expect(":")
                body = []
                while self._cur() and self._cur().value not in ("case","default","}"):
                    s = self._parse_stmt()
                    if s: body.append(s)
                cases.append(CaseNode(None, body, line))
            else:
                self._advance()
        self._expect("}")
        return SwitchNode(expr, cases, line)

    def _parse_return(self):
        line = self._cur().line; self._advance()
        val = None
        if self._cur() and self._cur().value != ";":
            val = self._parse_expr()
        self._match(";")
        return ReturnNode(val, line)

    # ── Expressions ────────────────────────────────
    def _parse_expr(self):       return self._parse_assign_expr()

    def _parse_assign_expr(self):
        node = self._parse_ternary()
        t = self._cur()
        assign_ops = {"=","+=","-=","*=","/=","%=","&=","|=","^=","<<=",">>="}
        if t and t.value in assign_ops:
            op = self._advance().value
            val = self._parse_assign_expr()
            name = node.name if isinstance(node, IdentNode) else None
            if name:
                self.symbol_table.define(name, "variable", "unknown",
                                         t.line if t else 0)
            return AssignNode(node, op, val, t.line if t else 0)
        return node

    def _parse_ternary(self):
        cond = self._parse_or()
        if self._cur() and self._cur().value == "?":
            self._advance()
            then = self._parse_expr()
            self._expect(":")
            else_ = self._parse_ternary()
            return TernaryNode(cond, then, else_)
        return cond

    def _parse_or(self):
        l = self._parse_and()
        while self._cur() and self._cur().value == "||":
            self._advance(); l = BinOpNode(l, "||", self._parse_and())
        return l

    def _parse_and(self):
        l = self._parse_bitor()
        while self._cur() and self._cur().value == "&&":
            self._advance(); l = BinOpNode(l, "&&", self._parse_bitor())
        return l

    def _parse_bitor(self):
        l = self._parse_bitxor()
        while self._cur() and self._cur().value == "|":
            self._advance(); l = BinOpNode(l, "|", self._parse_bitxor())
        return l

    def _parse_bitxor(self):
        l = self._parse_bitand()
        while self._cur() and self._cur().value == "^":
            self._advance(); l = BinOpNode(l, "^", self._parse_bitand())
        return l

    def _parse_bitand(self):
        l = self._parse_eq()
        while self._cur() and self._cur().value == "&" and (not self._peek(1) or self._peek(1).value != "&"):
            self._advance(); l = BinOpNode(l, "&", self._parse_eq())
        return l

    def _parse_eq(self):
        l = self._parse_cmp()
        while self._cur() and self._cur().value in ("==","!="):
            l = BinOpNode(l, self._advance().value, self._parse_cmp())
        return l

    def _parse_cmp(self):
        l = self._parse_shift()
        while self._cur() and self._cur().value in ("<",">","<=",">="):
            l = BinOpNode(l, self._advance().value, self._parse_shift())
        return l

    def _parse_shift(self):
        l = self._parse_add()
        while self._cur() and self._cur().value in ("<<",">>"):
            l = BinOpNode(l, self._advance().value, self._parse_add())
        return l

    def _parse_add(self):
        l = self._parse_mul()
        while self._cur() and self._cur().value in ("+","-"):
            l = BinOpNode(l, self._advance().value, self._parse_mul())
        return l

    def _parse_mul(self):
        l = self._parse_cast()
        while self._cur() and self._cur().value in ("*","/","%"):
            if self._cur().value == "*":
                # Disambiguate * as dereference vs multiply
                # In expression context after a non-type, it's multiply
                pass
            l = BinOpNode(l, self._advance().value, self._parse_cast())
        return l

    def _parse_cast(self):
        # (type) expr
        if (self._cur() and self._cur().value == "(" and
            self._peek(1) and self._peek(1).value in C_TYPES | C_TYPE_QUALIFIERS):
            self._advance()
            type_ = self._parse_type()
            if self._cur() and self._cur().value == ")":
                self._advance()
                expr = self._parse_unary()
                return CastNode(type_, expr)
            # backtrack — not a cast
            self.pos -= 1
        return self._parse_unary()

    def _parse_unary(self):
        t = self._cur()
        if not t: return LiteralNode(None)
        if t.value in ("-","!","~","++","--","&","*"):
            op = self._advance().value
            operand = self._parse_unary()
            return UnaryNode(op, operand, prefix=True)
        if t.value == "sizeof":
            self._advance()
            if self._cur() and self._cur().value == "(":
                self._advance()
                if self._cur() and self._cur().value in C_TYPES:
                    type_ = self._parse_type()
                    self._expect(")")
                    return SizeofNode(type_)
                else:
                    expr = self._parse_expr()
                    self._expect(")")
                    return SizeofNode(expr)
            else:
                expr = self._parse_unary()
                return SizeofNode(expr)
        return self._parse_postfix()

    def _parse_postfix(self):
        node = self._parse_primary()
        while self._cur():
            if self._cur().value == "(":
                # function call
                self._advance(); args = []
                while self._cur() and self._cur().value != ")":
                    args.append(self._parse_expr())
                    if not self._match(","): break
                self._expect(")")
                name = node.name if isinstance(node, IdentNode) else "?"
                node = CallNode(name, args, node.line if hasattr(node,"line") else 0)
            elif self._cur().value == "[":
                self._advance(); idx = self._parse_expr(); self._expect("]")
                node = IndexNode(node, idx)
            elif self._cur().value == ".":
                self._advance()
                member = self._advance().value if self._cur() else "?"
                node = MemberNode(node, member, arrow=False)
            elif self._cur().value == "->":
                self._advance()
                member = self._advance().value if self._cur() else "?"
                node = MemberNode(node, member, arrow=True)
            elif self._cur().value in ("++","--"):
                op = self._advance().value
                node = UnaryNode(op, node, prefix=False)
            else:
                break
        return node

    def _parse_primary(self):
        t = self._cur()
        if not t: return LiteralNode(None)

        if t.type == "INTEGER":
            self._advance()
            return LiteralNode(t.value, "int")
        if t.type == "FLOAT":
            self._advance()
            return LiteralNode(t.value, "float")
        if t.type == "STRING":
            self._advance()
            return LiteralNode(t.value, "string")
        if t.type == "CHAR_LIT":
            self._advance()
            return LiteralNode(t.value, "char")
        if t.value in ("true","false","NULL"):
            self._advance()
            return LiteralNode(t.value, "bool" if t.value in ("true","false") else "pointer")
        if t.value == "(":
            self._advance(); expr = self._parse_expr(); self._expect(")")
            return expr
        if t.value == "{":
            # initializer in expression context
            return self._parse_initializer()
        if t.type in ("IDENTIFIER","KEYWORD") and t.value not in C_TYPES:
            self._advance()
            self.symbol_table.lookup(t.value)
            return IdentNode(t.value, t.line)

        self._advance()
        return LiteralNode(None)

    def _skip_to(self, *values):
        while self._cur() and self._cur().value not in values:
            self._advance()


# Minimal ListNode needed for initializer
class ListNode(Node):
    def __init__(self, elements): self.elements = elements
