# utils/red_line_validator.py
import os
import re
import json
from groq import Groq


_client = None

def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _client


def check_red_lines(
    offer: str,
    party_name: str,
    red_lines: list[str],
    model: str = "llama-3.1-8b-instant",   # fast small model, isolated
) -> dict:
    """
    Sends the offer to a small LLM that checks it against red lines.
    Returns:
        {
            "violation": True/False,
            "violated_red_line": "the specific red line text or None",
            "explanation": "why it was flagged",
            "severity": "hard" | "soft" | "none"
        }
    hard  = clear numeric/factual breach of a stated limit
    soft  = ambiguous, borderline, or implicit pressure on a red line
    none  = no violation
    """
    red_lines_text = "\n".join(f"  - {r}" for r in red_lines)

    prompt = f"""You are a red line compliance checker for diplomatic negotiations.
Your job is NARROW and STRICT: check only for EXPLICIT violations.

PARTY: {party_name}

RED LINES (hard limits):
{red_lines_text}

OFFER TO CHECK:
\"\"\"{offer}\"\"\"

RULES FOR YOUR ANALYSIS:
1. Only flag a violation if the offer EXPLICITLY states, proposes, or 
   numerically commits to something that directly contradicts a red line.
2. Do NOT infer, imply, or chain logic. If the offer does not contain 
   the exact concept from the red line, it is NOT a violation.
3. Do NOT flag vague language as a violation. Vague language is NOT 
   a violation — only explicit contradiction is.
4. For numeric red lines (e.g. "no above 5%"), only flag if the offer 
   contains an explicit number that breaches the limit.
5. When in doubt — output violation: false. 
   False negatives are acceptable. False positives are not.

EXAMPLES OF WHAT IS NOT A VIOLATION:
- [Diplomacy] Red line: "No enrichment above 5%"
  Offer mentions: "IAEA verification framework" → NOT a violation (no number stated)
- [Business] Red line: "Founders must retain board seats"
  Offer mentions: "We will restructure the executive team" → NOT a violation (too vague, does not explicitly remove board seats)
- [Generic] Red line: "No unannounced inspections"
  Offer mentions: "We agree to a strict monitoring protocol" → NOT a violation (omission of 'announced' is not an explicit violation)

EXAMPLES OF WHAT IS A VIOLATION:
- [Diplomacy] Red line: "No enrichment above 5%"
  Offer says: "We accept a 7.5% enrichment cap" → VIOLATION (explicit numeric breach)
- [Business] Red line: "Minimum acquisition price of $50M"
  Offer says: "We propose a final buyout of $45M" → VIOLATION (explicit numeric breach)
- [Generic] Red line: "No mandatory weekend shifts"
  Offer says: "Staff will be required to work alternating Saturdays" → VIOLATION (explicitly contradicts the constraint)
  
Respond ONLY with valid JSON, no other text:
{{
  "violation": true or false,
  "violated_red_line": "exact red line text or null",
  "explanation": "one sentence — quote the EXACT words from the offer that cause the violation",
  "severity": "hard" or "soft" or "none"
}}"""

    try:
        response = _get_client().chat.completions.create(
            model    = model,
            messages = [{"role": "user", "content": prompt}],
            temperature = 0.0,    # deterministic — this is a checker not a creator
            max_tokens  = 200,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if model adds them
        raw = re.sub(r"```(?:json)?|```", "", raw).strip()
        result = json.loads(raw)

        # Validate expected keys exist
        assert "violation"        in result
        assert "violated_red_line" in result
        assert "explanation"      in result
        assert "severity"         in result

        return result

    except Exception as e:
        print(f"[RED LINE VALIDATOR ERROR] {e}")
        # Fail open — if checker breaks, don't block the negotiation
        return {
            "violation"        : False,
            "violated_red_line": None,
            "explanation"      : f"Validator error: {e}",
            "severity"         : "none",
        }