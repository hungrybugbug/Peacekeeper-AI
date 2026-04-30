# config.py
import os
from dotenv import load_dotenv
from crewai import LLM
import time
load_dotenv()

MAX_TURNS = 5
DEADLOCK_THRESHOLD = 2
INTER_CALL_DELAY = 15


def get_party_llm() -> LLM:
    """
    Parties use Llama 3.1 8B — fast, direct, slightly assertive tone.
    Same model for both parties intentionally — they are peers.
    """
    return LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.8,   # slightly higher = more assertive, less agreeable
    )


def get_mediator_llm() -> LLM:
    """
    Mediator uses Llama 3.3 70B — larger model, more nuanced reasoning.
    Different size = different emergent behavior on edge cases.
    """
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.4,   # lower = more consistent, structured output
    )