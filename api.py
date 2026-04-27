"""
api.py — Flask REST API Backend

Connects the HTML dashboard frontend to the compiler pipeline.
Endpoints:
    POST /api/compile    — runs full pipeline, returns JSON report
    POST /api/set-key    — sets OpenRouter API key for the session
    GET  /api/health     — health check

Usage:
    pip install flask flask-cors
    python api.py
    → runs on http://localhost:5000
"""

# Standard libraries for system operations, JSON handling, and debugging
import sys
import os
import json
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS

# ── Make sure compiler modules are importable ──────────────────
sys.path.insert(0, os.path.dirname(__file__))


# Import compiler pipeline modules
# Each module represents one phase of the compiler
from lexer         import Lexer
from parser        import Parser
from semantic      import SemanticAnalyser, detect_oob
from ai_correction import get_ai_fix, set_api_key, get_api_key

# Initialize Flask application
# CORS enabled to allow frontend (HTML/JS) to communicate with backend
app = Flask(__name__)
CORS(app)  

# Maximum number of times AI will attempt to fix errors per phase
# Prevents infinite correction loops
MAX_RETRIES = 2


# ═══════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════

# Filters only critical errors (ignores warnings)
# Ensures AI focuses only on actual issues
def _errors_only(errors: list) -> list:
    """Return only severity='error' items — never send warnings to AI."""
    return [e for e in errors if e.get("severity") == "error"]

# Adds phase information (lexical/syntax/semantic) to each error
# Helps frontend display errors correctly phase-wise
def _tag(errors: list, phase: str) -> list:
    """Stamp every error dict with its phase so the frontend can route it correctly."""
    for e in errors:
        e["phase"] = phase
    return errors


def run_phase(phase: str, source: str) -> dict:
    """
Executes a single compiler phase with AI-assisted correction.

Workflow:
1. Run compiler phase (lexical / syntax / semantic)
2. Collect errors
3. Send errors to AI for correction
4. Apply corrected code
5. Repeat until:
   - No errors OR
   - Max retries reached

Key Idea:
- Detection = Rule-based (compiler logic)
- Correction = AI-based (LLM)

This creates a hybrid intelligent compiler system.
"""
   
    report = {
        "phase":          phase,
        "original_code":  source,
        "corrected_code": source,
        "iterations":     [],
        "tokens":         [],
        "parse_tree":     None,
        "symbol_table":   [],
        "initial_errors": [],
        "fixed":          False,
    }

    current = source

    for attempt in range(MAX_RETRIES + 1):

        # ════════════════════════════════════════════
        #  LEXICAL PHASE 
        # - Tokenizes source code
        # - Detects invalid characters and typos
        # ════════════════════════════════════════════
        if phase == "lexical":
            lexer = Lexer(current)
            lexer.tokenise()
            all_errors = _tag(
                [e for e in lexer.all_errors() if e.get("type") != "OUT_OF_BOUNDS"],
                "lexical"
            )
            report["tokens"] = lexer.to_dict_list()
            if attempt == 0:
                report["initial_errors"] = list(all_errors)
            errors    = all_errors
            ai_errors = _errors_only(all_errors)

        # ════════════════════════════════════════════
        #  SYNTAX PHASE 
        # - Builds AST and Parse Tree
        # - Detects grammar errors (missing semicolons, brackets, etc.)
        # ════════════════════════════════════════════
        elif phase == "syntax":
            lexer = Lexer(current)
            lexer.tokenise()
            parser = Parser(lexer.tokens)
            ast, parse_tree = parser.parse()
            all_errors = _tag(list(parser.errors), "syntax")
            if attempt == 0:
                report["parse_tree"]     = parse_tree
                report["symbol_table"]   = [s.to_dict()
                                             for s in parser.symbol_table.all_symbols()]
                report["initial_errors"] = list(all_errors)
            errors    = all_errors
            ai_errors = _errors_only(all_errors)

        # ════════════════════════════════════════════
        #  SEMANTIC PHASE 
        # - Validates meaning of program
        # - Detects:
        #   • undeclared variables
        #   • type mismatches
        #   • out-of-bounds array access
        # ════════════════════════════════════════════
        else:
            lexer = Lexer(current)
            lexer.tokenise()
            oob_errors = _tag(detect_oob(current), "semantic")
            parser = Parser(lexer.tokens)
            ast, parse_tree = parser.parse()
            analyser = SemanticAnalyser(ast, parser.symbol_table)
            analyser.analyse()
            sem_errors = _tag(list(analyser.errors), "semantic")
            all_errors = oob_errors + sem_errors
            if attempt == 0:
                report["symbol_table"]   = analyser.get_symbol_table_data()
                report["parse_tree"]     = parse_tree
                report["initial_errors"] = list(all_errors)
            errors    = all_errors
            ai_errors = _errors_only(all_errors)


        # ════════════════════════════════════════════
        #  COMMON: decide whether to call AI or stop
        # ════════════════════════════════════════════
        real_errors = _errors_only(errors)

        if not real_errors:
            report["corrected_code"] = current
            report["fixed"]          = (current != source)
            break

        if attempt >= MAX_RETRIES:
            report["corrected_code"] = current
            break

        if not ai_errors:
            report["corrected_code"] = current
            report["fixed"]          = (current != source)
            break

        # Call AI model to fix detected errors
        # AI returns:
        # - corrected code
        # - list of fixes applied
        ai_result = get_ai_fix(current, ai_errors, phase)

        if "error" in ai_result:
            report["iterations"].append({
                "attempt":  attempt + 1,
                "phase":    phase,
                "errors":   ai_errors,
                "ai_fixes": [],
            })
            break

        fixed_code = ai_result.get("corrected_code", current)
        fixes      = ai_result.get("fixes", [])

        report["iterations"].append({
            "attempt":  attempt + 1,
            "phase":    phase,
            "errors":   ai_errors,
            "ai_fixes": fixes,
        })

        if fixed_code == current:
            break

        current = fixed_code
        report["corrected_code"] = current

    return report


# ═══════════════════════════════════════════════
#  API Endpoints
# ═══════════════════════════════════════════════

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "PCS-601 C Compiler API is running."})


@app.route("/api/set-key", methods=["POST"])
def set_key():
    """Set OpenRouter API key for this session."""
    data = request.get_json(force=True)
    key  = data.get("api_key", "").strip()
    if not key:
        return jsonify({"success": False, "error": "No API key provided."}), 400
    set_api_key(key)
    return jsonify({"success": True, "message": "API key set successfully."})


@app.route("/api/key-status", methods=["GET"])
def key_status():
    key = get_api_key()
    return jsonify({
        "has_key": bool(key),
        "preview": (key[:8] + "..." + key[-4:]) if len(key) > 12 else ("set" if key else "not set")
    })

@app.route("/")
def home():
    return "Compiler API is running 🚀"


@app.route("/api/compile", methods=["POST"])
def compile_code():
    """
    Main compile endpoint.
    Request JSON:
    {
      "source":   "<C source code>",
      "api_key":  "<optional, overrides session key>"
    }

    Response JSON: full pipeline report.
    """
    try:
        data   = request.get_json(force=True)
        source = data.get("source", "").strip()

        if not source:
            return jsonify({"error": "No source code provided."}), 400

        # Allow per-request API key override
        if data.get("api_key"):
            set_api_key(data["api_key"])

        original = source

        # Run compiler phases sequentially
        # Each phase works on corrected output from previous phase
        pipeline = {
            "original_code":  original,
            "corrected_code": source,
            "phases":         {},
            "summary":        {},
        }

        current = source

        for phase in ("lexical", "syntax", "semantic"):
            report  = run_phase(phase, current)
            pipeline["phases"][phase] = report
            current = report["corrected_code"]

        pipeline["corrected_code"] = current

        # Generate overall statistics for frontend dashboard
        # Includes error count, warnings, and code changes
        total_errors   = sum(
            len([e for e in pipeline["phases"][p]["initial_errors"]
                 if e.get("severity") == "error"])
            for p in ("lexical","syntax","semantic")
        )
        total_warnings = sum(
            len([e for e in pipeline["phases"][p]["initial_errors"]
                 if e.get("severity") == "warning"])
            for p in ("lexical","syntax","semantic")
        )
        pipeline["summary"] = {
            "total_errors":      total_errors,
            "total_warnings":    total_warnings,
            "fixed":             original != current,
            "lines_original":    len(original.splitlines()),
            "lines_corrected":   len(current.splitlines()),
        }

        return jsonify(pipeline)

    # Catch unexpected runtime errors and return traceback
    # Useful for debugging backend issues
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc), "traceback": traceback.format_exc()}), 500


# ═══════════════════════════════════════════════
#  Run
# ═══════════════════════════════════════════════
# Starts Flask development server
# Accessible locally via browser or frontend dashboard
if __name__ == "__main__":
    print("\n  PCS-601 C Compiler — Flask API")
    print("  ================================")
    print("  Running at: http://localhost:5000")
    print("  Health:     http://localhost:5000/api/health")
    print("  Press Ctrl+C to stop.\n")
    app.run(host="0.0.0.0", port=5000, debug=True)