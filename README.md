AI-Assisted Compiler Design

A modular compiler simulation that performs lexical, syntax, and semantic analysis, enhanced with AI-based error explanation and correction suggestions. The project demonstrates how real compilers process source code through multiple phases while improving developer understanding of errors.

Key Features
Tokenizes source code using a custom lexical analyzer
Builds and validates program structure through a syntax parser
Performs semantic checks such as undeclared variables and type mismatches
Uses AI to generate human-readable explanations and correction suggestions
Tech Stack
Language: Python
Concepts: Compiler Design, Parsing, AST, Symbol Tables
AI Integration: API-based error explanation module
Project Structure
.
├── main.py            # Entry point connecting all compiler phases
├── lexer.py           # Token generation
├── parser.py          # Syntax analysis and AST creation
├── semantic.py        # Semantic validation
└── ai_correction.py   # AI-powered error explanation
Example

Input

intt x = 10;
float result = x + y

Output

Lexical Error: Unknown keyword 'intt'
Syntax Error: Missing semicolon
Semantic Error: Undeclared variable 'y'

What I Learned
Implementation of core compiler phases
Design of token streams, ASTs, and symbol tables
Integrating AI into traditional systems to improve usability
