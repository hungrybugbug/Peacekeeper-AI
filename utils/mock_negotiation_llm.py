# utils/mock_negotiation_llm.py
"""
Deterministic negotiation LLM for offline experiments — no remote API calls.
Implements CrewAI BaseLLM; maps behavioral profiles to different concession curves.
"""

from __future__ import annotations

import random
import re
from typing import TYPE_CHECKING, Any

from pydantic import Field

from crewai.llms.base_llm import BaseLLM

if TYPE_CHECKING:
    from pydantic import BaseModel
    from crewai.agents.agent_builder.base_agent import BaseAgent
    from crewai.task import Task


def _task_prompt(messages: str | list[dict[str, Any]]) -> str:
    """Prefer the latest user/agent task prompt to avoid accidental substring matches."""
    if isinstance(messages, str):
        return messages
    for m in reversed(messages):
        c = m.get("content", "")
        if isinstance(c, str) and c.strip():

            return c
        if c:
            return str(c)
    return ""


def _parse_open_issues(prompt: str) -> list[str]:
    m = re.search(r"OPEN ISSUES:\s*\n((?:[ \t]*-[^\n]+\n?)+)", prompt, re.IGNORECASE)
    if not m:
        return []
    lines = []
    for line in m.group(1).splitlines():
        line = line.strip()
        if line.startswith("- ") and "all resolved" not in line.lower():
            lines.append(line[2:].strip())
    return lines


def _mediator_cycle_index(prompt: str) -> int:
    """Approximate mediator call index within this negotiation from prompt."""
    ledger_m = re.search(r"Turn (\d+)\)", prompt) or re.search(
        r"\[LEDGER T(\d+)\]", prompt
    )
    turn_hint = int(ledger_m.group(1)) if ledger_m else 0
    # Two party offers roughly per outer turn after T1 → map ledger turn → cycle
    return max(0, turn_hint // 2)


class MockNegotiationLLM(BaseLLM):
    llm_type: str = "mock_negotiation"
    model: str = Field(default="peacekeeper/mock-negotiator")
    behavioral_profile: str = Field(default="balanced")
    role: str = Field(default="party_a")
    run_seed: int = Field(default=0)

    def call(
        self,
        messages: str | list[Any],
        tools: list | None = None,
        callbacks: list | None = None,
        available_functions: dict[str, Any] | None = None,
        from_task: Task | None = None,
        from_agent: BaseAgent | None = None,
        response_model: type[BaseModel] | None = None,
    ) -> str:
        _ = tools, callbacks, available_functions, from_task, response_model
        text = _task_prompt(messages)
        rng = random.Random(int(self.run_seed) + hash(text[-500:] if text else "") % 10007)

        if "The negotiation has ended with status:" in text or (
            "negotiation has ended with status:" in text.lower()
        ):
            return self._final_report_snippet(text, rng)

        if "you are opening the negotiation" in text.lower():
            return self._opening(text, rng)
        if "you are the mediator" in text.lower():
            return self._mediator(text, rng)

        # Compliant rerun (validator path)
        if "your previous offer was flagged" in text.lower():
            return self._compliant_offer(text, rng)

        return self._counter_offer(text, rng)

    # --- generators ---------------------------------------------------------

    def _opening(self, text: str, rng: random.Random) -> str:
        party = self.role if self.role in ("party_a", "party_b") else "party_a"
        open_i = _parse_open_issues(text) or ["pricing", "terms"]
        gist = "; ".join(open_i[:4])
        if party == "party_a":
            return (
                f"Opening positions: prioritize {gist}. Seek binding terms "
                f"within our mandate; core limits are non‑negotiable. "
                f"Specific numbers proposed on each item in annex."
            ).replace("‑", "-")[:300]
        return (
            f"Counter-opening: advance {gist} while protecting sovereignty "
            f"and commercial interests. Invite structured trade-offs next round."
        )[:300]

    def _counter_offer(self, text: str, rng: random.Random) -> str:
        inc = rng.choice(
            ["We revise our prior terms", "Adjusted proposal", "Revised stance"]
        )
        # Avoid literal "NN%" tokens — they false-trigger the numeric red-line checker.
        return (
            f"{inc}: accept phased steps on timeline; move substantively toward the "
            f"other side on each open issue without stating explicit values that "
            f"breach our published limits; invite mediator-facilitated sequencing."
        )[:400]

    def _compliant_offer(self, text: str, rng: random.Random) -> str:
        return (
            "Revised compliant offer: aligns with principals and prior ledger; "
            "phased mutual concessions across open topics; numerical terms kept "
            "implicit pending bilateral technical annexes."
        )[:400]

    def _final_report_snippet(self, text: str, rng: random.Random) -> str:
        st = "SETTLED" if "SETTLED" in text.upper() else "CLOSED"
        return (
            f"Formal close ({st}). Dialogue advanced across listed issues.\n\n"
            f"Official record excerpt — session #{rng.randint(1000, 9999)}."
        ).replace("\u2014", "-")

    def _ledger_shows_all_resolved(self, text: str) -> bool:
        i = text.lower().find("open issues:")
        if i < 0:
            return False
        return "all resolved" in text[i : i + 400].lower()

    def _mediator(self, text: str, rng: random.Random) -> str:
        open_issues = _parse_open_issues(text)
        if self._ledger_shows_all_resolved(text):
            open_issues = []
        cycle = _mediator_cycle_index(text)

        profile = self.behavioral_profile
        agree_chance = {"stubborn": 0.25, "balanced": 0.55, "cooperative": 0.85}.get(
            profile, 0.55
        )
        force_deadlock = (
            profile == "stubborn"
            and cycle in (1, 2)
            and rng.random() < 0.35
            and cycle < 6
        )

        new_agg = None
        trade_off = "NONE"

        if open_issues:
            idx = cycle % len(open_issues)
            target = open_issues[idx]
            if rng.random() < agree_chance and not force_deadlock:
                new_agg = (
                    f"A verbal commitment on '{target}' with verification "
                    f"timeline and phased implementation."
                ).replace("'", "'")
                trade_off = (
                    "NONE"
                    if rng.random() > 0.25
                    else (
                        "Contingency: phased delivery tied to reciprocal actions "
                        "on the next unresolved issue."
                    )
                )

        deadlock = force_deadlock and not new_agg

        remaining = len(open_issues)
        if new_agg and remaining > 0:
            remaining = max(0, remaining - 1)
        settles = remaining == 0 and not deadlock
        if profile == "stubborn" and cycle < 2 and remaining == 0:
            settles = False

        offers = re.findall(r'said:\s*\n"([\s\S]*?)"(?=\s*\n)', text)
        excerpt_a = (offers[0][:100].replace("\n", " ") + "...") if offers else (
            "Party A terms (sanitized)"
        )
        excerpt_b = (offers[1][:100].replace("\n", " ") + "...") if len(offers) > 1 else (
            "Party B terms (sanitized)"
        )

        return (
            f"Neutral summary cycle {cycle}: distill positions; "
            f"preserve ledger integrity.\n\n"
            f"---LEDGER UPDATE---\n"
            f"NEW_AGREEMENT: {new_agg or 'NONE'}\n"
            f"DEADLOCK: {'YES' if deadlock else 'NO'}\n"
            f"TRADE_OFF: {trade_off}\n"
            f"SETTLEMENT: {'YES' if settles else 'NO'}\n"
            f"SANITIZED_A: {excerpt_a} — structured offer\n"
            f"SANITIZED_B: {excerpt_b} — structured reply\n"
            f"---END UPDATE---"
        )
