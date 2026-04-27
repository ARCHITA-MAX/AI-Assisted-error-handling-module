"""
lexer.py — Lexical Analyser for C Language
Tokenises C source code.
Detects: (1) Typo errors via TYPO_MAP + Levenshtein
         (2) Invalid C tokens
"""

#used for regular expression-based pattern matchng to identify tokens in source code
import re

#set of reserved words in c used to classify identfiers correctly
KEYWORDS = {
    "auto","break","case","char","const","continue","default","do",
    "double","else","enum","extern","float","for","goto","if","int",
    "long","register","return","short","signed","sizeof","static",
    "struct","switch","typedef","union","unsigned","void","volatile",
    "while","NULL","true","false","bool",
}

#preprocessor directives
PREPROCESSOR_KW = {"include","define","ifdef","ifndef","endif","elif","pragma","undef"}

#used for typos
BUILTINS = {
    "printf","scanf","malloc","free","calloc","realloc",
    "strlen","strcpy","strcat","strcmp","strncpy","strncat","strncmp",
    "memcpy","memset","memmove","memcmp",
    "fopen","fclose","fread","fwrite","fgets","fputs","feof","fflush",
    "abs","fabs","sqrt","pow","ceil","floor","rand","srand","exit",
    "atoi","atof","sprintf","sscanf","fprintf","fscanf","main",
}

#used for mapping to correct keyword
TYPO_MAP = {
    "retrun":"return","retur":"return","retrn":"return","reutrn":"return",
    "pintf":"printf","prntf":"printf","prinf":"printf","pritnf":"printf","prrint":"printf",
    "scnaf":"scanf","sacnf":"scanf",
    "whlie":"while","whiel":"while","wihle":"while",
    "breka":"break","braek":"break","brek":"break",
    "contineu":"continue","contnue":"continue",
    "strcut":"struct","sruct":"struct","stuct":"struct",
    "swtich":"switch","swithc":"switch","swich":"switch",
    "caes":"case","csae":"case",
    "defualt":"default","deafult":"default","defalt":"default",
    "vodi":"void","viod":"void",
    "flota":"float","foalt":"float","flot":"float",
    "intt":"int","itn":"int",
    "chrar":"char","cahrr":"char",
    "doubel":"double","doulbe":"double",
    "mian":"main","maiin":"main",
    "calcualte":"calculate","caluclate":"calculate",
    "totl":"total","toatl":"total",
    "numbr":"number","conut":"count","resutl":"result",
    "lenght":"length","stirng":"string",
    "integr":"integer","dictonary":"dictionary",
}

#tokens to ignore for typo detection
SKIP_TOKENS = {
    'i','j','k','n','x','y','z','v','e','f','g','h','a','b','c','d',
    't','p','q','r','s','w','m','l','fn','ok','db','id','ip','io',
    'arr','buf','tmp','num','val','key','obj','msg','err','res',
    'ret','req','ctx','cfg','app','cmd','log','url','api','row','col',
    'pos','idx','ptr','ref','out','inp','cur','src','dst','fmt',
    'ch','sz','len','cnt','sum','avg','ans','sp','hp','ep',
}

# Regex pattern to match keywords
_KW_PAT = r'\b(?:' + '|'.join(sorted(KEYWORDS, key=len, reverse=True)) + r')\b'

#token rules
TOKEN_SPEC = [
    ("PREPROCESSOR", r'#\s*(?:include|define|ifdef|ifndef|endif|elif|pragma|undef)[^\n]*'),
    
    # Numeric literals
    ("FLOAT",        r'\b\d+\.\d+(?:[eE][+-]?\d+)?[fFlL]?\b'),
    ("INTEGER",      r'\b(?:0[xX][0-9a-fA-F]+[uUlL]*|\d+[uUlL]*)\b'),
    
    # Character and string literals
    ("CHAR_LIT",     r"'(?:\\.|[^'\\])'"),
    ("STRING",       r'"(?:\\.|[^"\\])*"'),
    
    # Comments
    ("BLOCK_COMMENT",r'/\*.*?\*/'),
    ("LINE_COMMENT", r'//[^\n]*'),
    
    # Core tokens
    ("KEYWORD",      _KW_PAT),
    ("IDENTIFIER",   r'\b[a-zA-Z_][a-zA-Z0-9_]*\b'),
    
    # Operators
    ("OPERATOR",     r'->|<<|>>|==|!=|<=|>=|\+\+|--|&&|\|\||\+=|-=|\*=|/=|%=|&=|\|=|\^=|<<=|>>=|[+\-*/%=<>&|^~!?:]'),
    
    # Punctuation symbols
    ("DELIMITER",    r'[(){}\[\],;.]'),
    
    # Formatting tokens
    ("NEWLINE",      r'\n'),
    ("WHITESPACE",   r'[ \t]+'),
    
    # Anything else → invalid token
    ("UNKNOWN",      r'.'),
]

# Compile all token patterns into one master regex
_MASTER = re.compile('|'.join(f'(?P<{n}>{p})' for n, p in TOKEN_SPEC), re.DOTALL)

# Tokens to skip during final token generation
_SKIP   = {"WHITESPACE", "LINE_COMMENT", "BLOCK_COMMENT", "NEWLINE", "PREPROCESSOR"}


class Token:
    def __init__(self, type_, value, line, col, typo_hint=None):
        self.type      = type_
        self.value     = value
        self.line      = line
        self.col       = col
        self.typo_hint = typo_hint

    def to_dict(self):
        d = {"type": self.type, "value": self.value,
             "line": self.line, "col": self.col}
        if self.typo_hint:
            d["typo_hint"] = self.typo_hint
        return d

    def __repr__(self):
        h = f" → '{self.typo_hint}'?" if self.typo_hint else ""
        return f"Token({self.type}, {self.value!r}, L{self.line}:C{self.col}{h})"

#Computes edit distance between two strings.
def _lev(a, b):
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, n + 1):
            prev, dp[j] = dp[j], min(dp[j]+1, dp[j-1]+1,
                                     prev+(0 if a[i-1]==b[j-1] else 1))
    return dp[n]

#Suggests correction for identifiers if they are likely typos.
def typo_suggestion(token: str):
    t = token.lower()
    if len(t) <= 2 or token in SKIP_TOKENS:
        return None
    if t in TYPO_MAP:
        return TYPO_MAP[t]
    best, bd = None, 3
    for w in KEYWORDS | BUILTINS:
        d = _lev(t, w.lower())
        if d < bd:
            bd, best = d, w
    return best if bd <= 2 else None


"""
    Main lexical analyzer.

    Responsibilities:
    - Token generation
    - Lexical error detection
    - Typo detection (error vs warning classification)
"""
class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.tokens : list = []
        self.errors : list = []
        self.typos  : list = []

    #Core tokenization process.
    def tokenise(self):
        self.tokens, self.errors = [], []
        line = col = 1
        for m in _MASTER.finditer(self.source):
            kind, val = m.lastgroup, m.group()

            # Handle new lines for accurate position tracking
            if kind == "NEWLINE":
                line += 1; col = 1; continue
            
            # Skip irrelevant tokens            
            if kind in _SKIP:
                col += len(val); continue
            
            # Unknown characters → lexical error
            if kind == "UNKNOWN":
                self.errors.append({
                    "type": "LEXICAL_ERROR", "line": line,
                    "token": val, "severity": "error",
                    "description": f"Unknown character: '{val}'",
                    "suggestion": "Remove or replace this character.",
                    "corrected": ""
                })
                col += len(val); continue
            
            # Check typo suggestion for identifiers
            hint = None
            if kind == "IDENTIFIER":
                s = typo_suggestion(val)
                if s and s != val:
                    hint = s

            # Store token
            self.tokens.append(Token(kind, val, line, col, hint))
            col += len(val)

        seen = set()
        for tok in self.tokens:
            if tok.typo_hint and tok.value not in seen:
                seen.add(tok.value)
                
                is_keyword_typo = tok.typo_hint in KEYWORDS or tok.typo_hint in BUILTINS
                dist = _lev(tok.value.lower(), tok.typo_hint.lower())
                
                # Strong typo → treat as error
                if is_keyword_typo and dist <= 2:
                    self.errors.append({
                        "type": "LEXICAL_ERROR", "line": tok.line,
                        "token": tok.value, "severity": "error",
                        "description": f"Misspelled keyword/identifier: '{tok.value}' — did you mean '{tok.typo_hint}'?",
                        "suggestion": f"Replace '{tok.value}' with '{tok.typo_hint}'.",
                        "corrected": tok.typo_hint
                    })
                else:
                    # Weak typo → warning
                    self.typos.append({
                        "type": "TYPO", "line": tok.line,
                        "token": tok.value, "severity": "warning",
                        "description": f"Possible typo: '{tok.value}' — did you mean '{tok.typo_hint}'?",
                        "suggestion": f"Replace '{tok.value}' with '{tok.typo_hint}'.",
                        "corrected": tok.typo_hint
                    })

        return self.tokens

    def all_errors(self):
        #Returns all detected issues
        return self.errors + self.typos

    def to_dict_list(self):
        #Convert tokens into dictionary format
        return [t.to_dict() for t in self.tokens]
