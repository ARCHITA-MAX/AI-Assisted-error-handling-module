#performs syntax analysis on the token stream produced by the lexer
class Parser:
    def __init__(self, tokens):
        self.tokens = tokens   #list of tokens
        self.pos    = 0        #position in token list
        self.errors = []       #syntax error message
        self.tree   = []       #parse tree generation

    #returns the current token
    def current(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    #lookahead:checks future tokens
    def peek(self, offset=1):
        i = self.pos + offset
        return self.tokens[i] if i < len(self.tokens) else None

    #consumes the current token if it matches the expected type/value otherwise logs error
    def consume(self, expected_kind=None, expected_val=None):
        tok = self.current()
        if tok is None:
            return None
        #checks token type
        if expected_kind and tok[0] != expected_kind:
            self.errors.append(
                f"  [Line {tok[2]}] Syntax error: expected '{expected_kind}' "
                f"but got '{tok[0]}' ({tok[1]!r})"
            )
            return None
        #checks token value
        if expected_val and tok[1] != expected_val:
            self.errors.append(
                f"  [Line {tok[2]}] Syntax error: expected '{expected_val}' "
                f"but got '{tok[1]!r}'"
            )
            return None
        self.pos += 1
        return tok

    #parses statements until all tokens are consumed
    def parse(self):
        while self.current():
            stmt = self.parse_statement()
            if stmt:
                self.tree.append(stmt)
            else:
                self.pos += 1
        return self.tree

    #parses statement based on current token
    def parse_statement(self):
        tok = self.current()
        if tok is None:
            return None

        # processes include
        if tok[0] == "INCLUDE":
            self.consume()
            return ("INCLUDE", tok[1], tok[2])

        # using namespace std;
        if tok[0] == "KEYWORD" and tok[1] == "using":
            return self.parse_using()

        # return statement
        if tok[0] == "KEYWORD" and tok[1] == "return":
            return self.parse_return()

        # if statement
        if tok[0] == "KEYWORD" and tok[1] == "if":
            return self.parse_if()

        # while loop
        if tok[0] == "KEYWORD" and tok[1] == "while":
            return self.parse_while()

        # for loop
        if tok[0] == "KEYWORD" and tok[1] == "for":
            return self.parse_for()

        # output statement
        if tok[0] == "KEYWORD" and tok[1] == "cout":
            return self.parse_cout()

        #input statement
        if tok[0] == "KEYWORD" and tok[1] == "cin":
            return self.parse_cin()

        #variable declaration or function declaration
        if tok[0] == "KEYWORD" and tok[1] in ("int","float","double","char","void","bool","long","short"):
            return self.parse_decl_or_func()

        #opening brace
        if tok[0] == "LBRACE":
            return self.parse_block()

        #closing brace
        if tok[0] == "RBRACE":
            self.consume()
            return ("RBRACE", tok[2])

        #function call
        if tok[0] == "ID":
            if self.peek() and self.peek()[0] == "ASSIGN":
                return self.parse_assignment()
            # function call: id(...);
            if self.peek() and self.peek()[0] == "LPAREN":
                return self.parse_expr_stmt()

        #empty statement
        if tok[0] == "SEMICOLON":
            self.consume()
            return ("EMPTY_STMT",)

        return None

    #using namespace std;
    def parse_using(self):
        line = self.current()[2]
        self.consume()                        
        ns = self.current()
        if ns and ns[1] == "namespace":
            self.consume()
            name = self.consume("KEYWORD")
            semi = self.consume("SEMICOLON")
            if not semi:
                self.errors.append(f"  [Line {line}] Syntax error: missing ';' after 'using namespace {name[1] if name else ''}'")
            return ("USING", name[1] if name else "?", line)
        return None

    #return expression
    def parse_return(self):
        line = self.current()[2]
        self.consume()
        expr = self.parse_expr()
        semi = self.consume("SEMICOLON")
        if not semi:
            self.errors.append(f"  [Line {line}] Syntax error: missing ';' after return statement")
        return ("RETURN", expr, line)

    #if condition
    def parse_if(self):
        line = self.current()[2]
        self.consume()
        if not self.consume("LPAREN"):
            self.errors.append(f"  [Line {line}] Syntax error: expected '(' after 'if'")
        cond = self.parse_expr()
        if not self.consume("RPAREN"):
            self.errors.append(f"  [Line {line}] Syntax error: missing ')' after if condition")
        return ("IF", cond, line)

    #while condition
    def parse_while(self):
        line = self.current()[2]
        self.consume()
        if not self.consume("LPAREN"):
            self.errors.append(f"  [Line {line}] Syntax error: expected '(' after 'while'")
        cond = self.parse_expr()
        if not self.consume("RPAREN"):
            self.errors.append(f"  [Line {line}] Syntax error: missing ')' after while condition")
        return ("WHILE", cond, line)

    #for loop
    def parse_for(self):
        line = self.current()[2]
        self.consume()
        if not self.consume("LPAREN"):
            self.errors.append(f"  [Line {line}] Syntax error: expected '(' after 'for'")
        depth = 1
        parts = []
        while self.current() and depth > 0:
            t = self.current()
            if t[0] == "LPAREN":
                depth += 1
            elif t[0] == "RPAREN":
                depth -= 1
                if depth == 0:
                    self.consume()
                    break
            parts.append(t)
            self.consume()
        return ("FOR", parts, line)

    #output expression
    def parse_cout(self):
        line = self.current()[2]
        self.consume() 
        parts = []
        while self.current() and self.current()[0] == "COMP" and self.current()[1] == "<<":
            self.consume()
            parts.append(self.parse_expr())
        semi = self.consume("SEMICOLON")
        if not semi:
            self.errors.append(f"  [Line {line}] Syntax error: missing ';' after cout statement")
        return ("COUT", parts, line)

    #input expression
    def parse_cin(self):
        line = self.current()[2]
        self.consume()  
        parts = []
        while self.current() and self.current()[0] == "COMP" and self.current()[1] == ">>":
            self.consume()
            parts.append(self.parse_expr())
        semi = self.consume("SEMICOLON")
        if not semi:
            self.errors.append(f"  [Line {line}] Syntax error: missing ';' after cin statement")
        return ("CIN", parts, line)

    def parse_decl_or_func(self):
        line  = self.current()[2]
        dtype = self.consume()[1]   #datatype

        name_tok = self.current()
        if name_tok is None:
            return None

        name = self.consume()[1]

        # function definition
        if self.current() and self.current()[0] == "LPAREN":
            self.consume()
            params = []
            while self.current() and self.current()[0] != "RPAREN":
                params.append(self.current()[1])
                self.consume()
            if not self.consume("RPAREN"):
                self.errors.append(f"  [Line {line}] Syntax error: missing ')' in function definition")
            return ("FUNC_DEF", dtype, name, params, line)

        # variable declaration
        expr = None
        if self.current() and self.current()[0] == "ASSIGN":
            self.consume()
            expr = self.parse_expr()

        semi = self.consume("SEMICOLON")
        if not semi:
            self.errors.append(f"  [Line {line}] Syntax error: missing ';' after declaration of '{name}'")
        return ("DECL", dtype, name, expr, line)

    #asssignment operation
    def parse_assignment(self):
        line = self.current()[2]
        name = self.consume("ID")[1]
        self.consume("ASSIGN")
        expr = self.parse_expr()
        semi = self.consume("SEMICOLON")
        if not semi:
            self.errors.append(f"  [Line {line}] Syntax error: missing ';' after assignment to '{name}'")
        return ("ASSIGN", name, expr, line)

    #function call
    def parse_expr_stmt(self):
        expr = self.parse_expr()
        semi = self.consume("SEMICOLON")
        if not semi and self.current():
            tok = self.current()
            self.errors.append(f"  [Line {tok[2]}] Syntax error: missing ';' after expression")
        return ("EXPR_STMT", expr)

    #block statement
    def parse_block(self):
        line = self.current()[2]
        self.consume("LBRACE")
        stmts = []
        while self.current() and self.current()[0] != "RBRACE":
            s = self.parse_statement()
            if s:
                stmts.append(s)
            else:
                self.pos += 1
        self.consume("RBRACE")
        return ("BLOCK", stmts, line)

    #binary operations
    def parse_expr(self):
        left = self.parse_primary()
        while self.current() and self.current()[0] in ("ARITH", "COMP", "LT", "GT"):
            op = self.consume()
            right = self.parse_primary()
            left = ("BINOP", op[1], left, right)
        return left
    
    #parses primary expressions
    def parse_primary(self):
        tok = self.current()
        if tok is None:
            return None
        if tok[0] in ("NUMBER", "STRING", "CHAR"):
            self.consume()
            return ("LITERAL", tok[1], tok[0])
        if tok[0] == "KEYWORD" and tok[1] in ("true","false","NULL","endl","std"):
            self.consume()
            return ("LITERAL", tok[1], tok[0])
        if tok[0] == "ID":
            self.consume()
            if self.current() and self.current()[0] == "LPAREN":
                line = tok[2]
                self.consume("LPAREN")
                args = []
                while self.current() and self.current()[0] != "RPAREN":
                    args.append(self.parse_expr())
                    if self.current() and self.current()[0] == "COMMA":
                        self.consume()
                if not self.consume("RPAREN"):
                    self.errors.append(f"  [Line {line}] Syntax error: missing ')' in call to '{tok[1]}'")
                return ("CALL", tok[1], args, line)
            return ("VAR", tok[1], tok[2])
        #parses expression based on their precedence
        if tok[0] == "LPAREN":
            self.consume()
            expr = self.parse_expr()
            self.consume("RPAREN")
            return ("GROUP", expr)
        return None

#forms AST
def format_node(node):
    #used for handling empty nodes
    if node is None: return "None"
    k = node[0]
    if k == "INCLUDE":   return f"INCLUDE  {node[1]}  (line {node[2]})"
    if k == "USING":     return f"USING namespace {node[1]}  (line {node[2]})"
    if k == "FUNC_DEF":  return f"FUNC_DEF  {node[1]} {node[2]}({', '.join(node[3])})  (line {node[4]})"
    if k == "DECL":      return f"DECL  {node[1]} '{node[2]}' = {format_node(node[3])}  (line {node[4]})"
    if k == "ASSIGN":    return f"ASSIGN  '{node[1]}' = {format_node(node[2])}  (line {node[3]})"
    if k == "RETURN":    return f"RETURN  {format_node(node[1])}  (line {node[2]})"
    if k == "IF":        return f"IF  ({format_node(node[1])})  (line {node[2]})"
    if k == "WHILE":     return f"WHILE  ({format_node(node[1])})  (line {node[2]})"
    if k == "FOR":       return f"FOR (...)  (line {node[2]})"
    if k == "COUT":      return f"COUT  {' << '.join(format_node(p) for p in node[1])}  (line {node[2]})"
    if k == "CIN":       return f"CIN  {' >> '.join(format_node(p) for p in node[1])}  (line {node[2]})"
    if k == "BLOCK":     return f"BLOCK  ({len(node[1])} statements)  (line {node[2]})"
    if k == "BINOP":     return f"({format_node(node[2])} {node[1]} {format_node(node[3])})"
    if k == "LITERAL":   return f"{node[1]}:{node[2]}"
    if k == "VAR":       return f"VAR({node[1]})"
    if k == "CALL":      return f"CALL {node[1]}(...)  (line {node[3]})"
    if k == "GROUP":     return f"({format_node(node[1])})"
    return str(node)

#for printing the parse tree and syntax errors
def print_tree(tree, errors):
    print("\n" + "="*60)
    print("  PHASE 2 — SYNTAX ANALYSIS")
    print("="*60)
    if tree:
        print("  Parse tree:\n")
        for node in tree:
            print(f"    {format_node(node)}")
    else:
        print("  No statements parsed.")
    if errors:
        print(f"\n  Syntax errors ({len(errors)}):")
        for e in errors:
            print(e)
    else:
        print("\n  No syntax errors found.")
