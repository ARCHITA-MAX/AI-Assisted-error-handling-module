#this file send errors to OpenRouter AI and receive explanation + corrected code
import urllib.request     #used to send HTTP request to OpenRouter API
import urllib.error       #used to handle HTTP-related errors
import json               #used to encode/decode JSON data
import os                 #used to access environment variables

#OpenRouter endpoint for chatbased models
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

#reads the API key from the systemm evironment
def get_api_key():
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        print("\n  [AI Module] OPENROUTER_API_KEY not set.")
        print("  Get a FREE key at: https://openrouter.ai")
        print("  Then in VS Code terminal run:")
        print("    $env:OPENROUTER_API_KEY='your-key-here'")
        print("  Then run python main.py again.")
    return key

#create a detailed prompt to send to the AI model
#including original code, compiler errors, instruction for AI to fix it
def build_prompt(source_code, lex_errors, syn_errors, sem_errors):
    #combine all type of error into one list
    all_errors = lex_errors + syn_errors + sem_errors
    #if no errro
    if not all_errors:
        return None
    #converts error list into readable text
    error_block = "\n".join(all_errors)
    #final prompt taht will be sent to the AI
    return (
        f"You are a C++ compiler assistant helping a beginner student fix their code.\n\n"
        f"The student wrote this C++ code:\n\n"
        f"```cpp\n{source_code.strip()}\n```\n\n"
        f"The compiler found these errors:\n{error_block}\n\n"
        f"Your job:\n"
        f"1. Explain each error in simple words (1-2 lines each).\n"
        f"2. Show the FULLY CORRECTED C++ code — fix every error, do NOT remove or comment out lines.\n"
        f"   For example:\n"
        f"   - If a variable is assigned the wrong type, fix the type or the value.\n"
        f"   - If a semicolon is missing, add it.\n"
        f"   - If an invalid character like '@' is used, replace it with a valid value.\n"
        f"   - If a variable is undeclared, declare it with a proper type and value.\n"
        f"3. Give one short tip to avoid such mistakes.\n\n"
        f"IMPORTANT: The corrected code must be complete and compilable. "
        f"Every line from the original must appear in fixed form — never delete or comment lines out.\n\n"
        f"Be concise and beginner-friendly."
    )

#send prompt to OpenRouter AI and receives response
def call_openrouter(prompt, api_key):
    #creates JSON payload to send to the API
    payload = json.dumps({
        "model": "openrouter/auto",     # let OpenRouter choose best model
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1000              #limit response size
    }).encode("utf-8")

    #create HTTP request
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {api_key}",       #API authentication
            "HTTP-Referer":  "https://compiler-project.local",
            "X-Title":       "Mini Compiler PCS601"
        },
        method="POST"
    )

    try:
        #send request too OpenRouter and wait for response
        with urllib.request.urlopen(req, timeout=30) as resp:
            #convert response JSON to python dictionary
            data = json.loads(resp.read().decode("utf-8"))
            #extract AI text message
            return data["choices"][0]["message"]["content"]
    #for server errors
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            msg = json.loads(body).get("error", {}).get("message", body)
        except Exception:
            msg = body
        return f"OpenRouter API error {e.code}: {msg}"
    except Exception as e:
        return f"Request failed: {e}"

#used for displaying header, checks errors, calls AI, print responses
def run_ai_correction(source_code, lex_errors, syn_errors, sem_errors):
    print("\n" + "="*60)
    print("  PHASE 4 — AI CORRECTION MODULE  (via OpenRouter)")
    print("="*60)

    #merges all errors from previous phases
    all_errors = lex_errors + syn_errors + sem_errors

    #if no error
    if not all_errors:
        print("\n  No errors detected across all phases.")
        print("  Your C++ code looks correct!")
        return

    #retrieve API key
    api_key = get_api_key()
    if not api_key:
        #if API is missing prints error
        print(f"\n  {len(all_errors)} error(s) found (set OPENROUTER_API_KEY for AI suggestions):")
        for e in all_errors:
            print(e)
        return

    #display status
    total = len(all_errors)
    print(f"\n  {total} error(s) found across all phases.")
    print("  Sending to AI for analysis and correction...")
    print("  Please wait...\n")

    #build AI prompt
    prompt   = build_prompt(source_code, lex_errors, syn_errors, sem_errors)
    #sends prompt to OpenRouter and receive response
    response = call_openrouter(prompt, api_key)
    #prints response
    print("  " + "-"*56)
    for line in response.strip().splitlines():
        print(f"  {line}")
    print("  " + "-"*56)