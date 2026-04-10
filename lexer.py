import re

#list of all valid c++ keywords that the lexer should recognise and helps detect misspelled keywords
C_KEYWORDS = {
    "int", "float", "double", "char", "void", "if", "else", "while", "for",
    "return", "cout", "cin", "endl", "include", "using", "namespace", "std",
    "bool", "true", "false", "long", "short", "unsigned", "signed", "struct",
    "class", "new", "delete", "null", "NULL"
}

#used for correcting misspelled keywords
def levenshtein(a, b):
    m, n = len(a), len(b)
    #represnts the distance
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            #if character matches
            if a[i-1] == b[j-1]:
                dp[j] = prev
            #if the character does not match
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]

#used to suggest the keyword if there is any typo
def suggest_keyword(word):
    word_lower = word.lower()
    #only compares keywords of similar length
    candidates = [kw for kw in C_KEYWORDS if abs(len(kw) - len(word)) <= 2]
    best_kw, best_dist = None, 999
    for kw in candidates:
        d = levenshtein(word_lower, kw)
        if d < best_dist:
            best_dist, best_kw = d, kw
    #suggests only if there is likely a typo
    if best_dist <= 1 and best_kw and word_lower != best_kw and len(word) >= 3:
        return best_kw
    return None

#token list
TOKEN_SPEC = [
    ("COMMENT",   r'//[^\n]*|/\*[\s\S]*?\*/'),
    ("INCLUDE",   r'#include\s*[<"][^>"]*[>"]'),
    ("NUMBER",    r'\b\d+(\.\d+)?\b'),
    ("STRING",    r'"[^"]*"'),
    ("CHAR",      r"'[^']*'"),
    ("KEYWORD",   r'\b(int|float|double|char|void|if|else|while|for|return|'
                  r'cout|cin|endl|include|using|namespace|std|bool|true|false|'
                  r'long|short|unsigned|signed|struct|class|new|delete|null|NULL)\b'),
    ("ID",        r'[a-zA-Z_]\w*'),
    ("COMP",      r'==|!=|<=|>=|<<|>>|&&|\|\|'),
    ("ASSIGN",    r'=(?!=)'),
    ("ARITH",     r'[+\-*/%]'),
    ("LBRACE",    r'\{'),
    ("RBRACE",    r'\}'),
    ("LPAREN",    r'\('),
    ("RPAREN",    r'\)'),
    ("SEMICOLON", r';'),
    ("COMMA",     r','),
    ("LT",        r'<'),
    ("GT",        r'>'),
    ("HASH",      r'#'),
    ("NEWLINE",   r'\n'),
    ("SPACE",     r'[ \t]+'),
    ("MISMATCH",  r'.'),
]

#combines all regex patterns into one master pattern
MASTER = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in TOKEN_SPEC))

#used to generate list of tokens as well as if there is any lexical error
def tokenize(code):
    tokens = []
    errors = []
    line   = 1

    for mo in MASTER.finditer(code):
        #scans the entire code using regex
        kind  = mo.lastgroup
        value = mo.group()

        #tracks line number
        if kind == "NEWLINE":
            line += 1
        #ignores space
        elif kind == "SPACE":
            pass
        #detectes unknown character
        elif kind == "MISMATCH":
            errors.append(f"  [Line {line}] Lexical error: unknown character '{value}'")
        #skips comments but counts new line
        elif kind == "COMMENT":
            line += value.count('\n')
        #identifier processing and typo detection
        elif kind == "ID":
            suggestion = suggest_keyword(value)
            if suggestion:
                errors.append(
                    f"  [Line {line}] Lexical error: unknown identifier '{value}' "
                    f"— did you mean '{suggestion}'?"
                )
            tokens.append((kind, value, line))
        #all other valid tokens
        else:
            tokens.append((kind, value, line))

    # Check for unterminated string literals
    for kind, value, ln in tokens:
        if kind == "STRING" and not (value.startswith('"') and value.endswith('"') and len(value) >= 2):
            errors.append(f"  [Line {ln}] Lexical error: unterminated string literal")

    return tokens, errors

#for printing token table
def print_tokens(tokens, errors):
    print("\n" + "="*60)
    print("  PHASE 1 — LEXICAL ANALYSIS")
    print("="*60)
    #for header
    print(f"  {'TOKEN TYPE':<14} {'VALUE':<25} LINE")
    print("  " + "-"*50)
    #for printing token
    for kind, value, line in tokens:
        print(f"  {kind:<14} {repr(value):<25} {line}")
    print(f"\n  Total tokens: {len(tokens)}")
    #for printing lexical error if any
    if errors:
        print(f"\n  Lexical errors ({len(errors)}):")
        for e in errors:
            print(e)
    else:
        print("\n  No lexical errors found.")






