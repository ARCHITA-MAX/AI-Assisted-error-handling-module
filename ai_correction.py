"""
ai_correction.py — AI Error Correction via OpenRouter

Flow per phase:
  1. Receive errors from lexer / parser / semantic analyser
  2. Call OpenRouter API with C source + errors
  3. Return corrected C source code
  4. Caller re-runs the phase on corrected code

API Key is injected at runtime from the frontend/dashboard.
"""

import re
import json
import requests

# ── OpenRouter Config ─────────────────────────────────────────
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Model used for correction (fast + cost-efficient)
MODEL          = "openai/gpt-4o-mini"   
# Timeout for API request (in seconds)
TIMEOUT        = 30

# Global variable to store API key (set dynamically from frontend)
_API_KEY = ""

def set_api_key(key: str):
    #Store API key globally for future API calls.
    global _API_KEY
    _API_KEY = key.strip()

def get_api_key():
    #Return currently stored API key
    return _API_KEY


def get_ai_fix(source_code: str, errors: list, phase: str) -> dict:
    """
    Send C source + errors to OpenRouter.
    Each phase is strictly restricted to ONLY fix its own class of errors.
    Returns:
    {
      "corrected_code": str,
      "fixes": [ {"line": int, "original": str, "fixed": str, "explanation": str} ],
      "confidence": int (0-100),
      "error": str  (only if API call failed)
    }
    """

    # ── No errors → nothing to fix ──
    if not errors:
        return {"corrected_code": source_code, "fixes": [], "confidence": 100}

    # ── API key not set → cannot call AI ──
    if not _API_KEY:
        return {
            "corrected_code": source_code, "fixes": [], "confidence": 0,
            "error": "No API key set. Enter your OpenRouter API key in the dashboard."
        }

    # ── Phase-specific rules: what THIS phase is allowed to fix ──
    phase_rules = {
        "lexical": (
            "You are the LEXICAL phase fixer. Fix ONLY these lexical errors:\n"
            "  - Invalid identifiers that start with a digit (e.g. '2num' → 'num')\n"
            "  - Unknown/illegal characters in the source\n"
            "  - Misspelled C keywords or built-in names (e.g. 'pintf'→'printf', 'retrun'→'return')\n"
            "OUT_OF_BOUNDS array index errors are already auto-fixed — do NOT touch them.\n"
            "FORBIDDEN (do NOT fix these — they belong to later phases):\n"
            "  - Missing semicolons\n"
            "  - Missing or mismatched parentheses / braces\n"
            "  - Type mismatches\n"
            "  - Undeclared variables"
        ),
        "syntax": (
            "You are the SYNTAX phase fixer. Fix ONLY these syntax errors:\n"
            "  - 'Missing semicolon — add ; at the end of line N' → append a ';' to the END of that line\n"
            "  - 'Expected ) but got {' in if/for/while → add the missing ')' before the '{'\n"
            "  - Missing '{' or '}' for blocks → add the missing brace\n"
            "  - Missing return type on function definitions\n"
            "HOW TO FIX SEMICOLONS: if the error says 'add ; at the end of line N', look at line N "
            "and add a semicolon character at the very end of that line. Example: "
            "'    int a = 10' becomes '    int a = 10;'\n"
            "FORBIDDEN (do NOT fix these — they belong to other phases):\n"
            "  - Invalid identifiers (e.g. '2num') — that is a lexical error\n"
            "  - Type mismatches or undeclared variables — those are semantic errors\n"
            "  - 'declared but never used' warnings — NOT errors, ignore them"
        ),
        "semantic": (
            "You are the SEMANTIC phase fixer. Fix ONLY these semantic errors:\n"
            "  - Type mismatches in expressions (e.g. int + string → fix the operand)\n"
            "  - Wrong argument counts in function calls (adjust the call)\n"
            "  - 'return' used outside a function (wrap or move it)\n"
            "Undeclared variables are already auto-fixed — do NOT re-declare them.\n"
            "FORBIDDEN (do NOT fix these — they belong to other phases):\n"
            "  - Missing semicolons or parentheses — those are syntax errors\n"
            "  - Invalid identifiers — those are lexical errors\n"
            "  - 'declared but never used' warnings — NOT errors, never touch them\n"
            "  - Never add comments like '// unused' or '// fixed'"
        ),
    }.get(phase, "Fix only the errors listed below.")

    # ── Build focused snippet: only the error lines ± 1 context line ──
    """
    Instead of sending full code blindly,
    we extract only lines around errors (±1 line context).

    This improves:
    - Accuracy of AI fixes
    - Reduces token usage (cost optimization)
    """
    src_lines = source_code.splitlines()
    error_line_nums = set(e.get("line", 0) for e in errors if e.get("line"))
    context_set = set()
    for ln in error_line_nums:
        for offset in (-1, 0, 1):
            idx = ln + offset - 1
            if 0 <= idx < len(src_lines):
                context_set.add(ln + offset)

    snippet_parts = []
    prev = None
    for ln in sorted(context_set):
        if prev is not None and ln > prev + 1:
            snippet_parts.append("    ... (lines unchanged) ...")
        arrow = "  ← FIX THIS" if ln in error_line_nums else ""
        snippet_parts.append(f"  {ln:3d} | {src_lines[ln-1]}{arrow}")
        prev = ln
    focused_snippet = "\n".join(snippet_parts)

    # ── Build error list with explicit fix hints per error ──
    def _fix_hint(e, phase):
        desc = e.get("description", "")
        if phase == "syntax":
            if "Missing semicolon" in desc:
                return f"→ ADD ';' at the end of line {e.get('line','?')}"
            if "Expected ')'" in desc:
                return f"→ ADD missing ')' before the '{{' on line {e.get('line','?')}"
            if "Expected '}'" in desc:
                return f"→ ADD missing '}}' on line {e.get('line','?')}"
        if phase == "lexical":
            if "starts with a digit" in desc or "Unknown character" in desc:
                return f"→ FIX the invalid identifier on line {e.get('line','?')}"
        if phase == "semantic":
            if "arithmetic" in desc or "type mismatch" in desc.lower():
                return f"→ REPLACE the string literal with a numeric value on line {e.get('line','?')}"
            if "not declared" in desc:
                return f"→ DECLARE the variable before use on line {e.get('line','?')}"
        return ""

    error_list = "\n".join(
        f"  Line {e.get('line','?')} [{e.get('type','?')}]: {e.get('description','')}  {_fix_hint(e, phase)}"
        for e in errors
    )

    prompt = f"""You are a precise C compiler error fixer. Make MINIMAL, SURGICAL fixes only.

Language: C  |  Phase: {phase.upper()}

=== YOUR ROLE FOR THIS PHASE ===
{phase_rules}

=== ERRORS TO FIX (ONLY THESE) ===
{error_list}

=== LINES TO FIX (only lines marked ← FIX THIS) ===
{focused_snippet}

=== FULL SOURCE (return with ONLY the above errors fixed) ===
```c
{source_code}
```

ABSOLUTE RULES:
1. Fix ONLY the errors listed above — one fix per listed error, nothing more.
2. Do NOT fix any other issues you notice elsewhere in the code.
3. No comments added (no "// unused", "// fixed", "// error", etc.).
4. No Python syntax (no def, print(, elif, True:, False:).
5. Output valid C for every line you change.
6. Return ONLY valid JSON, no markdown fences, no extra text.

JSON:
{{
  "corrected_code": "<full C source with only the listed errors fixed>",
  "fixes": [
    {{
      "line": <number>,
      "original": "<original line snippet>",
      "fixed": "<corrected line snippet>",
      "explanation": "<one sentence: what was wrong and exactly what you changed>"
    }}
  ],
  "confidence": <0-100>
}}"""

     #  API Request Setup
    headers = {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/ARCHITA-MAX",
        "X-Title":       "PCS-601 C Compiler GEU",
    }
    payload = {
        "model":       MODEL,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens":  2000,
    }

    #  API Call + Response Handling
    try:
        resp = requests.post(OPENROUTER_URL, headers=headers,
                             json=payload, timeout=TIMEOUT)
        resp.raise_for_status()

        # Extract AI response text
        raw = resp.json()["choices"][0]["message"]["content"]

        # Clean formatting (remove markdown if present)
        raw = re.sub(r'```(?:json)?\n?', '', raw).strip().rstrip('`')

        # Convert JSON string to dictionary
        result = json.loads(raw)

         # Ensure required fields exist
        result.setdefault("corrected_code", source_code)
        result.setdefault("fixes", [])
        result.setdefault("confidence", 50)
        return result


     #  Error Handling
    except requests.exceptions.RequestException as e:
        return {
            "corrected_code": source_code, "fixes": [], "confidence": 0,
            "error": f"API request failed: {e}"
        }
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "corrected_code": source_code, "fixes": [], "confidence": 0,
            "error": f"Could not parse AI response: {e}"
        }

