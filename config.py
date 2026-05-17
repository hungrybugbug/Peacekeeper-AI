# config.py
import os
from dotenv import load_dotenv
from crewai import LLM

from utils.mock_negotiation_llm import MockNegotiationLLM

if os.path.exists(".env"):
    load_dotenv()

MAX_TURNS = 3
DEADLOCK_THRESHOLD = 2
INTER_CALL_DELAY_SEC = 15.0


def get_max_turns() -> int:
    """Prefer PEACEKEEPER_MAX_TURNS for experiment sweeps."""
    raw = os.getenv("PEACEKEEPER_MAX_TURNS")
    if raw and raw.strip().isdigit():
        return max(2, min(30, int(raw.strip())))
    return MAX_TURNS


def get_inter_call_delay_sec() -> float:
    raw = os.getenv("PEACEKEEPER_INTER_CALL_DELAY_SEC")
    if raw is not None:
        try:
            return float(raw)
        except ValueError:
            pass
    return INTER_CALL_DELAY_SEC


def experiment_backend() -> str:
    return (os.getenv("PEACEKEEPER_EXPERIMENT_BACKEND") or "").strip().lower()


def _experiment_run_seed() -> int:
    raw = os.getenv("PEACEKEEPER_RUN_SEED", "0") or "0"
    try:
        return abs(int(raw)) % (2**31 - 1)
    except ValueError:
        return 0


def _mock_llm(role: str, profile_env_var: str, default_profile: str) -> MockNegotiationLLM:
    profile = (
        os.getenv(profile_env_var) or default_profile
    ).strip().lower()
    seed = _experiment_run_seed()
    slug = {"party_a": "pa", "party_b": "pb", "mediator": "med"}.get(role, role)
    return MockNegotiationLLM(
        model=f"mock/{slug}/{profile}",
        role=role,
        behavioral_profile=profile,
        run_seed=seed + (sum(ord(c) for c in slug) % 997),
        temperature=None,
        provider="mock",
        is_litellm=False,
    )


# def get_party_llm() -> LLM:
#     """
#     Parties use Llama 3.1 8B — fast, direct, slightly assertive tone.
#     Same model for both parties intentionally — they are peers.
#     """
#     return LLM(
#         model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
#         api_key=os.getenv("GROQ_API_KEY"),
#         temperature=0.8,   # slightly higher = more assertive, less agreeable
#     )

def get_party_a_llm():
    """Party A — Groq Llama, or deterministic mock during experiments."""
    if experiment_backend() == "mock":
        return _mock_llm(
            "party_a",
            "PEACEKEEPER_MOCK_PROFILE_PARTY_A",
            "balanced",
        )
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in .env")
    return LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
        api_key=api_key,
        temperature=0.8,
    )

def get_party_b_llm():
    """Party B — Google Gemini via AI Studio, or deterministic mock."""
    if experiment_backend() == "mock":
        return _mock_llm(
            "party_b",
            "PEACEKEEPER_MOCK_PROFILE_PARTY_B",
            "balanced",
        )
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in .env")
    return LLM(
        model="gemini/gemini-2.5-flash",
        api_key=api_key,
        temperature=0.8,
    )


def get_mediator_llm():
    """
    Mediator uses Llama 3.3 70B — larger model, more nuanced reasoning.
    Or mock mediator with PEACEKEEPER_MOCK_PROFILE_MEDIATOR profile.
    """
    if experiment_backend() == "mock":
        return _mock_llm(
            "mediator",
            "PEACEKEEPER_MOCK_PROFILE_MEDIATOR",
            "balanced",
        )
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.4,
    )


# Alias for callers that still import INTER_CALL_DELAY
INTER_CALL_DELAY = INTER_CALL_DELAY_SEC