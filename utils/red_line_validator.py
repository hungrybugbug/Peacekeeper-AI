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


def _mock_check_red_lines(offer: str, red_lines: list[str]) -> dict:
    """
    Lightweight rule-based checker for offline experiments (no Groq calls).
    Conservative: prefers false negatives over blocking runs.
    """
    offer_lower = offer.lower()

    for red_line in red_lines:
        red_lower = red_line.lower()

        above_match = re.search(
            r"(?:above|exceed|more than|higher than)\s*(\d+\.?\d*)\s*%",
            red_lower,
        )
        below_match = re.search(
            r"(?:below|under|less than|lower than)\s*(\d+\.?\d*)\s*%",
            red_lower,
        )
        offer_nums = [
            float(p)
            for p in re.findall(r"(\d+\.?\d*)\s*%", offer_lower)
        ]

        money_red = re.search(
            r"\$([\d,.]+)\s*[mMbB]",
            red_lower.replace(",", ""),
        )
        offer_money = re.findall(r"\$\s*([\d,.]+)\s*[mMbB]", offer_lower.replace(",", ""))

        if above_match and offer_nums:
            threshold = float(above_match.group(1))
            if any(p > threshold for p in offer_nums):
                return {
                    "violation": True,
                    "violated_red_line": red_line,
                    "explanation": (
                        "Offer states a percentage above the declared maximum "
                        "in the red line."
                    ),
                    "severity": "hard",
                }

        if below_match and offer_nums:
            threshold = float(below_match.group(1))
            if any(p < threshold for p in offer_nums):
                return {
                    "violation": True,
                    "violated_red_line": red_line,
                    "explanation": (
                        "Offer states a percentage below the declared minimum."
                    ),
                    "severity": "hard",
                }

        if money_red and offer_money:
            threshold_raw = money_red.group(1).replace(",", "")
            threshold = float(threshold_raw)

            def _parse_m(s: str) -> float:

                return float(s.replace(",", ""))

            vals = [_parse_m(m) for m in offer_money]
            if "below" in red_lower or "not sell below" in red_lower:

                if any(v < threshold for v in vals):
                    return {
                        "violation": True,
                        "violated_red_line": red_line,
                        "explanation": (
                            "Offer proposes a valuation below the minimum."
                        ),
                        "severity": "hard",
                    }
            if "above" in red_lower or "not pay above" in red_lower or (
                "will not pay above" in red_lower
            ):
                if any(v > threshold for v in vals):
                    return {
                        "violation": True,
                        "violated_red_line": red_line,
                        "explanation": (
                            "Offer proposes consideration above stated cap."
                        ),
                        "severity": "hard",
                    }

        key_terms = [
            w
            for w in red_lower.split()
            if len(w) > 5
            and w
            not in {
                "accept",
                "above",
                "below",
                "never",
                "under",
                "framing",
                "condition",
                "cannot",
                "will",
                "must",
                "agree",
                "allow",
                "permit",
            }
        ]
        if len(key_terms) >= 2:

            hits = sum(1 for t in key_terms if t in offer_lower)
            explicit_phrases = (
                "unannounced inspections",
                "zero enrichment",
                "immediate post-acquisition layoffs",
                "earn-out longer than 2 years",
            )
            for phrase in explicit_phrases:

                if phrase in red_lower and phrase in offer_lower:
                    hits += 3
            if hits >= 4:
                return {
                    "violation": True,
                    "violated_red_line": red_line,
                    "explanation": "Offer language closely mirrors a barred concept.",
                    "severity": "soft",
                }

    return {
        "violation": False,
        "violated_red_line": None,
        "explanation": "No explicit numeric or keyword breach detected.",
        "severity": "none",
    }


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
    mock_flag = (os.getenv("PEACEKEEPER_MOCK_REDLINES") or "").lower()
    if mock_flag in {"1", "true", "yes", "mock"}:
        return _mock_check_red_lines(offer, red_lines)

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