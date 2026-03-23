#this file connects all the compilation phases
from lexer         import tokenize, print_tokens
from parser        import Parser,   print_tree
from semantic      import SemanticAnalyzer
from ai_correction import run_ai_correction

#sample code for testing
SOURCE_CODE = """\
#include <iostream>
using namespace std;

int main() {
    intt x = 10;
    int y = 20;
    int z = x + y;
    num = "hello";
    float result = x + y
    int val = @;
    cout << z << endl;
    cout << undefined_var << endl;
    return 0;
}
"""

#controls the execution flow of the phases
def main():
    print("  Source code under analysis:")
    print("  " + "-"*50)
    for i, line in enumerate(SOURCE_CODE.strip().splitlines(), 1):
        print(f"  {i:>3} | {line}")
    print("  " + "-"*50)

    # Phase 1 — Lexical
    tokens, lex_errors = tokenize(SOURCE_CODE)
    print_tokens(tokens, lex_errors)

    # Phase 2 — Syntax
    parser     = Parser(tokens)
    tree       = parser.parse()
    syn_errors = parser.errors
    print_tree(tree, syn_errors)

    # Phase 3 — Semantic
    analyzer   = SemanticAnalyzer(tree)
    analyzer.analyze()
    analyzer.print_results()
    sem_errors = analyzer.errors

    # Phase 4 — AI Correction
    run_ai_correction(SOURCE_CODE, lex_errors, syn_errors, sem_errors)

    # Summary
    print("\n" + "="*60)
    print("  SUMMARY")
    print("="*60)
    print(f"  Lexical errors  : {len(lex_errors)}")
    print(f"  Syntax errors   : {len(syn_errors)}")
    print(f"  Semantic errors : {len(analyzer.errors)}")
    print(f"  Warnings        : {len(analyzer.warnings)}")
    print(f"  Total issues    : {len(lex_errors)+len(syn_errors)+len(analyzer.errors)}")
    print("="*60 + "\n")

#ensures main() runs only when file is executed directly
if __name__ == "__main__":
    main()