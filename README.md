# C Compiler — Python-Based Multi-Phase Compiler with AI Error Correction

> A fully functional multi-phase C compiler built in Python, featuring lexical analysis, parsing, semantic analysis, and AI-powered error correction via OpenRouter (GPT-4o-mini). Developed as part of the Compiler Design course at Graphic Era (Deemed to be) University, Dehradun.

---

## Overview

This project implements a **multi-phase compiler for the C language** from scratch using Python. Each phase — lexical analysis, parsing, and semantic analysis — independently detects errors and optionally invokes an **AI correction engine** powered by OpenRouter to suggest and apply surgical fixes to the source code.

The compiler also includes a **visual HTML dashboard** for interactive code submission, error visualization, and AI-corrected output display.

---

## Features

- ✅ **Lexical Analyser** — tokenizes C source, catches invalid identifiers, unknown characters, and misspelled keywords
- ✅ **Parser** — checks syntactic correctness (missing semicolons, mismatched braces/parentheses, missing return types)
- ✅ **Semantic Analyser** — detects type mismatches, wrong argument counts, undeclared variables, and scope violations
- ✅ **AI Error Correction** — calls OpenRouter API (GPT-4o-mini) per phase to auto-fix only phase-specific errors
- ✅ **Phase-Isolated Fixes** — each phase fixer is strictly constrained to its own error class (no cross-phase interference)
- ✅ **Focused Snippet Optimisation** — only error-surrounding lines (±1 context) are sent to the AI, reducing token usage
- ✅ **Visual HTML Dashboard** — browser-based UI to submit code, view errors, and see corrected output
- ✅ **Optional Code Generation** — generates intermediate/target code if all phases pass

---

## Project Structure

```
compiler-project/
│
├── lexer.py               # Lexical analysis — tokenizer and error detection
├── parser.py              # Syntax analysis — grammar and structure checks
├── semantic.py            # Semantic analysis — type checking, scope, declarations
├── ai_correction.py       # AI error correction via OpenRouter API
├── api.py                 # Entry point — orchestrates all compiler phase
├── dashboard.html         # Visual HTML dashboard for interactive use
```

---

## Compiler Phases

### Phase 1 — Lexical Analysis (`lexer.py`)
- Tokenizes the C source code
- Detects invalid identifiers (e.g., `2num`), illegal characters, and misspelled keywords (e.g., `pintf` → `printf`)
- Outputs a token stream and a list of lexical errors

### Phase 2 — Syntax Analysis (`parser.py`)
- Validates the grammatical structure of the token stream
- Detects missing semicolons, mismatched parentheses/braces, missing return types on functions
- Outputs a parse tree / AST and syntax errors

### Phase 3 — Semantic Analysis (`semantic.py`)
- Checks meaning and consistency beyond syntax
- Detects type mismatches in expressions, wrong argument counts, undeclared variables, and invalid `return` usage
- Outputs semantic errors

---

## AI Error Correction

Powered by **OpenRouter API** using `openai/gpt-4o-mini`.

### How it works:
1. After each phase detects errors, `get_ai_fix()` is called with the source code, error list, and phase name
2. The AI receives **only the error-surrounding lines** (±1 context line) plus a phase-specific role prompt
3. The AI returns a JSON response with `corrected_code`, a `fixes` list, and a `confidence` score
4. The caller re-runs the phase on the corrected code

### Phase-Isolated Correction Rules:
| Phase | Allowed to Fix | Forbidden |
|-------|---------------|-----------|
| Lexical | Invalid identifiers, unknown chars, misspelled keywords | Semicolons, braces, type errors |
| Syntax | Missing `;`, `)`, `{`, `}`, return types | Identifiers, semantic errors |
| Semantic | Type mismatches, wrong arg counts, return outside function | Syntax errors, unused variable warnings |

### Without an API Key:
The compiler runs all phases normally. AI correction is skipped and the original source is returned unchanged with an informational message.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.x |
| AI Model | GPT-4o-mini via OpenRouter |
| HTTP Client | `requests` |
| Frontend Dashboard | HTML, CSS, JavaScript |
| Data Format | JSON |
| Version Control | Git / GitHub |

---

## Installation

### Prerequisites
- Python 3.8+
- pip
- An [OpenRouter](https://openrouter.ai) API key *(optional — for AI correction)*

### Steps

```bash
# 1. Clone the repository
git clone https://github.com/ARCHITA-MAX/AI-Assisted-error-handling-module.git
cd compiler-project

# 2. Install dependencies

# 3. (Optional) Set your OpenRouter API key
#    Enter it in the dashboard UI, or set it programmatically:
#    from ai_correction import set_api_key
#    set_api_key("your-key-here")
```

---

## Usage

### Run via terminal

```bash
python main.py
```

You will be prompted to enter or provide a C source file. The compiler will run all phases sequentially and print errors and corrections to the console.

### Run via Dashboard

Open `dashboard/index.html` in your browser. click on demo and the demo code will load contaning errors, provide your OpenRouter API key, and click **Compile** to see phase-by-phase results and AI-corrected output.

---

## Dashboard

The visual HTML dashboard provides:
- A code editor for C source input
- API key input field (injected at runtime — never hardcoded)
- Phase-by-phase error display with line numbers
- AI-corrected code output with fix explanations and confidence score
- Clean, colour-coded error categorisation by phase

---

## Important Notes

- **API key security** — The API key is injected at runtime from the frontend. It is never hardcoded in source files.
- **AI fixes are surgical** — The AI is strictly prompted to fix only the errors of its phase. It does not rewrite or refactor code.
- **Warnings are not errors** — `declared but never used` warnings are intentionally ignored by all phases.
---
