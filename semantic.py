#used for storing the size of each datatype
C_TYPE_SIZES = {"int": 4, "float": 4, "double": 8, "char": 1, "bool": 1, "long": 8, "short": 2, "void": 0}

class SemanticAnalyzer:
    def __init__(self, tree):
        self.tree     = tree      #parse tree from syntax analysis
        self.errors   = []        #semantic error list
        self.warnings = []        #warning message
        self.symbols  = {}        #symbol table
        self.funcs    = {}        #function table

    #infers the data tyoes of nodes
    def infer_type(self, node):
        if node is None: return "unknown"
        k = node[0]
        if k == "LITERAL":
            t = node[2]
            if t == "NUMBER":
                return "float" if "." in node[1] else "int"
            if t == "STRING":  return "char*"
            if t == "CHAR":    return "char"
            if t in ("true","false"): return "bool"
            if t == "NULL":    return "void*"
        #look for variable nodes
        if k == "VAR":
            return self.symbols.get(node[1], "unknown")
        #binary operation nodes
        if k == "BINOP":
            op    = node[1]
            left  = self.infer_type(node[2])
            right = self.infer_type(node[3])
            #comparsion and logical operators
            if op in ("==","!=","<",">","<=",">=","&&","||"):
                return "bool"
            if left == right:
                return left
            # numeric rules
            numeric = ("int","float","double","long","short")
            if left in numeric and right in numeric:
                if "double" in (left, right): return "double"
                if "float"  in (left, right): return "float"
                return "int"
            #report incompatible types
            if left != "unknown" and right != "unknown":
                self.errors.append(
                    f"  [Semantic] Type mismatch: cannot apply '{op}' "
                    f"to '{left}' and '{right}'"
                )
            return "unknown"
        #function call to return types
        if k == "CALL":
            return self.funcs.get(node[1], "unknown")
        if k == "GROUP":
            return self.infer_type(node[1])
        return "unknown"

    #treverses entire parse tree
    def analyze(self):
        for node in self.tree:
            self.analyze_node(node)

    #performs type check and symbol tracking
    def analyze_node(self, node):
        if node is None: return
        k = node[0]

        #stores return type
        if k == "FUNC_DEF":
            self.funcs[node[2]] = node[1]

        #variable declaration
        elif k == "DECL":
            dtype, name, expr, line = node[1], node[2], node[3], node[4]
            #check for unknown datatypes
            if dtype not in C_TYPE_SIZES:
                self.errors.append(f"  [Line {line}] Semantic error: unknown type '{dtype}'")
            #check redeclaration
            if name in self.symbols:
                self.errors.append(f"  [Line {line}] Semantic error: variable '{name}' already declared")
            rtype = self.infer_type(expr)
            # type mismatch check
            if expr and rtype != "unknown":
                #float to int warning
                if dtype == "int" and rtype == "float":
                    self.warnings.append(
                        f"  [Line {line}] Warning: assigning float to int '{name}' — possible data loss"
                    )
                #invalid assignment to char
                if dtype == "char" and rtype not in ("char", "char*", "unknown"):
                    self.errors.append(
                        f"  [Line {line}] Semantic error: cannot assign '{rtype}' to char variable '{name}'"
                    )
                #string to numeric 
                if dtype in ("int","float","double") and rtype == "char*":
                    self.errors.append(
                        f"  [Line {line}] Semantic error: cannot assign string literal to '{dtype}' variable '{name}'"
                    )
            #add variable to symbol table
            self.symbols[name] = dtype

        #assignment statement
        elif k == "ASSIGN":
            name, expr, line = node[1], node[2], node[3]
            #use before declartion
            if name not in self.symbols:
                self.errors.append(
                    f"  [Line {line}] Semantic error: variable '{name}' used before declaration"
                )
            else:
                declared = self.symbols[name]
                rtype    = self.infer_type(expr)
                #check type mismatch
                if rtype != "unknown" and declared != rtype:
                    numeric = ("int","float","double","long","short")
                    if not (declared in numeric and rtype in numeric):
                        self.errors.append(
                            f"  [Line {line}] Semantic error: type mismatch — "
                            f"cannot assign '{rtype}' to '{declared}' variable '{name}'"
                        )

        #return statement
        elif k == "RETURN":
            self.infer_type(node[1])

        #conditional statement
        elif k == "IF" or k == "WHILE":
            ctype = self.infer_type(node[1])
            line  = node[2]
            if ctype not in ("bool","int","unknown"):
                self.errors.append(
                    f"  [Line {line}] Semantic error: condition must be boolean/int, got '{ctype}'"
                )

        #output statement
        elif k == "COUT":
            for part in node[1]:
                self.analyze_node(part)

        #variable usage
        elif k == "VAR":
            name, line = node[1], node[2]
            builtins = {"cout","cin","endl","std","main","NULL","true","false"}
            if name not in self.symbols and name not in self.funcs and name not in builtins:
                self.errors.append(
                    f"  [Line {line}] Semantic error: '{name}' used before declaration"
                )
        #binary operation
        elif k == "BINOP":
            self.infer_type(node)

        #block statement
        elif k == "BLOCK":
            for s in node[1]:
                self.analyze_node(s)

    #displays semantic analysis result
    def print_results(self):
        print("\n" + "="*60)
        print("  PHASE 3 — SEMANTIC ANALYSIS")
        print("="*60)
        #prints symbol  table
        print("\n  Symbol Table:")
        print(f"  {'VARIABLE':<20} {'TYPE':<12} SIZE (bytes)")
        print("  " + "-"*45)
        if self.symbols:
            for name, typ in self.symbols.items():
                size = C_TYPE_SIZES.get(typ, "?")
                print(f"  {name:<20} {typ:<12} {size}")
        else:
            print("  (empty)")

        #prints function table
        if self.funcs:
            print(f"\n  Functions:")
            print(f"  {'NAME':<20} RETURN TYPE")
            print("  " + "-"*30)
            for name, rtype in self.funcs.items():
                print(f"  {name:<20} {rtype}")

        #prints warnings
        if self.warnings:
            print(f"\n  Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                print(w)

        #prints errors
        if self.errors:
            print(f"\n  Semantic errors ({len(self.errors)}):")
            for e in self.errors:
                print(e)
        else:
            print("\n  No semantic errors found.")
