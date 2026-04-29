# tasks/negotiation_tasks.py
from crewai import Task
from crewai import Agent
from ledger import AgreementLedger


def make_opening_offer_task(agent: Agent, ledger: AgreementLedger, party_name: str) -> Task:
    """
    Turn 1 only — Party A makes the first offer.
    No prior offer exists so we don't reference one.
    """
    return Task(
        description=(
            f"You are opening the negotiation on behalf of {party_name}.\n\n"
            f"Read the current state of the negotiation carefully:\n"
            f"{ledger.to_compact_context()}\n\n"
            f"Make your opening offer. Be clear and specific. State:\n"
            f"  1. Your position on each open issue\n"
            f"  2. What you are willing to discuss\n"
            f"  3. What is non-negotiable for you\n\n"
            f"Keep your response under 150 words. Be firm but diplomatic."
        ),
        expected_output=(
            f"A clear opening offer from {party_name} stating their position "
            f"on each open issue. Under 150 words."
        ),
        agent=agent,
    )


def make_counter_offer_task(
    agent: Agent,
    ledger: AgreementLedger,
    party_name: str,
    other_party_name: str,
    incoming_offer: str,
    mediator_instruction: str = None,   # NEW parameter
) -> Task:
    
    mediator_block = ""
    if mediator_instruction:
        mediator_block = (
            f"\nCRITICAL — THE MEDIATOR HAS GIVEN YOU A DIRECT INSTRUCTION:\n"
            f"\"{mediator_instruction}\"\n"
            f"You MUST explicitly acknowledge this instruction and either:\n"
            f"  a) Accept it and adjust your position accordingly, OR\n"
            f"  b) Reject it with a specific reason and propose an alternative\n"
            f"Ignoring the mediator is not acceptable.\n"
        )

    return Task(
        description=(
            f"You are negotiating on behalf of {party_name}.\n\n"
            f"Current negotiation state:\n"
            f"{ledger.to_compact_context()}\n\n"
            f"The mediator passed you this sanitized offer from {other_party_name}:\n"
            f"\"{incoming_offer}\"\n"
            f"{mediator_block}\n"
            f"Your response MUST:\n"
            f"  1. Explicitly acknowledge the mediator's trade-off if one exists\n"
            f"  2. Accept points you can concede — do NOT restate settled points\n"
            f"  3. Push back ONLY on genuinely disputed points with a new number or term\n"
            f"  4. Show movement — repeating your last position exactly is not allowed\n"
            f"  5. NEVER restate anything already in AGREED POINTS\n\n"
            f"Keep your response under 80 words. Show concrete movement."
        ),
        expected_output=(
            f"A response from {party_name} that acknowledges the mediator's "
            f"instruction, shows movement on at least one point, and proposes "
            f"a concrete updated position. Under 80 words."
        ),
        agent=agent,
    )


def mediate_task(
    agent: Agent,
    ledger: AgreementLedger,
    party_a_name: str,
    party_b_name: str,
    offer_a: str,
    offer_b: str,
) -> Task:
    """
    Mediator runs after both parties have spoken each turn.
    It sanitizes, finds agreement, detects deadlock, and
    produces a structured update the system can parse.
    """
    deadlock_instruction = ""
    if ledger.is_deadlocked(threshold=2):
        deadlock_instruction = (
            f"\n\nIMPORTANT: You have detected a deadlock "
            f"({ledger.deadlock_count} turns without movement). "
            f"You MUST propose a creative win-win trade-off that neither "
            f"party has suggested. Explain why it serves both sides."
        )

    return Task(
        description=(
            f"You are the mediator. Both parties have just spoken.\n\n"
            f"Current ledger state:\n"
            f"{ledger.to_context_string()}\n\n"
            f"{party_a_name} said:\n\"{offer_a}\"\n\n"
            f"{party_b_name} said:\n\"{offer_b}\"\n\n"
            f"Your job this turn:\n"
            f"  1. SANITIZE: Restate each party's core proposal without "
            f"     any emotional language or ultimatums\n"
            f"  2. FIND AGREEMENT: Identify any point both parties have "
            f"     accepted — even partially\n"
            f"  3. SUMMARIZE THE GAP: State clearly what is still disputed\n"
            f"  4. CHECK DEADLOCK — THIS IS MANDATORY, NOT OPTIONAL:\n"
            f"     Compare the current offers to the previous turn's offers stored "
            f"     in the ledger. If either party's position on ANY open issue has "
            f"     not changed numerically, that is a deadlock. Declare it. "
            f"     You do not have the option to 'hope' positions will change. "
            f"     If positions are the same as last turn — DEADLOCK: YES.\n"
            f"  5. CHECK SETTLEMENT: Are all open issues now resolved?\n"
            f"{deadlock_instruction}\n\n"
            f"You MUST end your response with this exact structured block "
            f"so the system can update the ledger:\n\n"
            f"---LEDGER UPDATE---\n"
            f"NEW_AGREEMENT: <point that is now agreed, or NONE>\n"
            f"DEADLOCK: <YES or NO>\n"
            f"TRADE_OFF: <your proposed trade-off, or NONE>\n"
            f"SETTLEMENT: <YES or NO>\n"
            f"SANITIZED_A: <your sanitized version of {party_a_name}'s offer>\n"
            f"SANITIZED_B: <your sanitized version of {party_b_name}'s offer>\n"
            f"---END UPDATE---"
        ),
        expected_output=(
            "A mediator summary followed by a structured LEDGER UPDATE block "
            "with all six fields filled in exactly as specified."
        ),
        agent=agent,
    )


def final_report_task(agent: Agent, ledger: AgreementLedger) -> Task:
    """
    Runs once at the end — mediator writes the official closing summary.
    """
    return Task(
        description=(
            f"The negotiation has ended with status: {ledger.status.upper()}\n\n"
            f"Final ledger state:\n"
            f"{ledger.to_context_string()}\n\n"
            f"Write a formal closing statement that includes:\n"
            f"  1. A one-paragraph summary of how the negotiation unfolded\n"
            f"  2. A clear list of all agreed points\n"
            f"  3. Any unresolved issues (if negotiation failed)\n"
            f"  4. A closing diplomatic statement from the mediator\n\n"
            f"This will be the official record of this negotiation session."
        ),
        expected_output=(
            "A formal closing statement with negotiation summary, "
            "agreed points list, and mediator's closing remarks."
        ),
        agent=agent,
    )