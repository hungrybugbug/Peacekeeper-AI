# ledger.py
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class AgreementLedger:
    scenario: str
    party_a_name: str
    party_b_name: str
    open_issues: list[str]

    # These are managed internally — don't pass them in
    turn: int = 0
    agreed_points: list[str] = field(default_factory=list)
    last_offer_a: Optional[str] = None
    last_offer_b: Optional[str] = None
    deadlock_count: int = 0
    trade_off_proposed: Optional[str] = None
    status: str = "in_progress"   # "in_progress" | "settled" | "failed"
    history: list[dict] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


    def record_offer(self, party: str, offer: str):
        """Call this after each agent makes an offer."""
        self.turn += 1
        if party == "a":
            self.last_offer_a = offer
        elif party == "b":
            self.last_offer_b = offer

        self.history.append({
            "turn": self.turn,
            "party": party,
            "offer": offer,
        })


    def add_agreed_point(self, point: str):
        """Mediator calls this when both sides accept something."""
        if point not in self.agreed_points:
            self.agreed_points.append(point)
            # Remove from open issues if it's there
            self.open_issues = [
                i for i in self.open_issues
                if i.lower() not in point.lower()
            ]

    def to_compact_context(self) -> str:
        """
        Shorter version for party prompts — saves ~200 tokens per call.
        Full version only goes to the mediator who needs all detail.
        """
        agreed = ", ".join(self.agreed_points) if self.agreed_points else "none"
        open_i = ", ".join(self.open_issues) if self.open_issues else "all resolved"
        return (
            f"[LEDGER T{self.turn}] "
            f"Agreed: {agreed} | "
            f"Open: {open_i} | "
            f"Deadlocks: {self.deadlock_count} | "
            f"Status: {self.status}"
        )

    def increment_deadlock(self):
        """Mediator calls this when it detects repeated positions."""
        self.deadlock_count += 1


    def propose_trade_off(self, trade_off: str):
        """Mediator injects a win-win option when deadlocked."""
        self.trade_off_proposed = trade_off
        self.history.append({
            "turn": self.turn,
            "party": "mediator",
            "offer": f"[TRADE-OFF] {trade_off}",
        })


    def settle(self):
        """Call when all issues are resolved."""
        self.status = "settled"


    def fail(self):
        """Call when max turns exceeded with no settlement."""
        self.status = "failed"


    def is_deadlocked(self, threshold: int = 2) -> bool:
        """Returns True if deadlock count has hit the threshold."""
        return self.deadlock_count >= threshold


    def all_issues_resolved(self) -> bool:
        """Returns True when open_issues is empty."""
        return len(self.open_issues) == 0


    def to_context_string(self) -> str:
        """
        This is what gets injected into every agent's prompt.
        Keeps agents grounded in the current state of the deal.
        """
        agreed = "\n".join(f"  - {p}" for p in self.agreed_points) or "  None yet"
        open_i = "\n".join(f"  - {i}" for i in self.open_issues) or "  All resolved"

        return f"""
=== AGREEMENT LEDGER (Turn {self.turn}) ===
Scenario     : {self.scenario}
Status       : {self.status.upper()}
Deadlocks    : {self.deadlock_count}

AGREED POINTS:
{agreed}

OPEN ISSUES:
{open_i}

LAST OFFER ({self.party_a_name}): {self.last_offer_a or 'None yet'}
LAST OFFER ({self.party_b_name}): {self.last_offer_b or 'None yet'}

TRADE-OFF ON TABLE: {self.trade_off_proposed or 'None'}
=========================================
""".strip()


    def to_report(self) -> str:
        """Final summary after negotiation ends."""
        agreed = "\n".join(f"  - {p}" for p in self.agreed_points) or "  None"
        unresolved = "\n".join(f"  - {i}" for i in self.open_issues) or "  None"

        return f"""
NEGOTIATION REPORT
==================
Scenario     : {self.scenario}
Outcome      : {self.status.upper()}
Total turns  : {self.turn}
Deadlocks    : {self.deadlock_count}

FINAL AGREED POINTS:
{agreed}

UNRESOLVED ISSUES:
{unresolved}

TRADE-OFF USED: {self.trade_off_proposed or 'None'}
==================
""".strip()

