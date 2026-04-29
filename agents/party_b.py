# agents/party_b.py
from crewai import Agent
from config import get_party_llm


def create_party_b(name: str, position: str, goals: list[str], red_lines: list[str]) -> Agent:
    """
    Party B — the opposing negotiating party.
    Identical structure to Party A intentionally.
    The difference is in the data passed in, not the code.
    """
    goals_text = "\n".join(f"- {g}" for g in goals)
    red_lines_text = "\n".join(f"- {r}" for r in red_lines)

    return Agent(
        role=f"Negotiator representing {name}",
        goal=(
            f"Advance the interests of {name} in this negotiation. "
            f"Your goals are:\n{goals_text}\n\n"
            f"You must NEVER cross these red lines:\n{red_lines_text}"
        ),
        backstory=(
            f"You are a seasoned negotiator representing {name}. "
            f"You understand the difference between positions and interests. "
            f"Your stated goals are your OPENING positions — not your final ones. "
            f"You are authorized to make concessions on secondary issues to protect "
            f"your core interests. Your red lines are the only true limits. "
            f"Everything else is negotiable if the trade is right.\n\n"
            f"You know that a negotiator who never moves loses credibility and "
            f"eventually loses the deal entirely. Smart concessions on minor points "
            f"are a sign of strength, not weakness. "
            f"When the mediator proposes a trade-off, you take it seriously — "
            f"you either accept it, counter it with a modification, or reject it "
            f"with a clear reason. You never ignore it."
        ),
        llm=get_party_llm(),
        verbose=True,
        allow_delegation=False,
    )