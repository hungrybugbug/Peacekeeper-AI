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
    mediator_instruction: str = None,
) -> Task:

    # Build mediator block with clear priority — no contradiction
    mediator_block = ""
    if mediator_instruction:
        mediator_block = (
            f"\nTHE MEDIATOR HAS PROPOSED: \"{mediator_instruction}\"\n"
            f"Priority order for your response:\n"
            f"  FIRST — address the mediator's proposal directly\n"
            f"  SECOND — respond to the incoming offer below\n"
            f"  If the mediator's proposal conflicts with your red lines,\n"
            f"  you MUST HOLD your red line, but you MUST offer a significant concession\n"
            f"  on a DIFFERENT open issue to compensate.\n"
            f"  Example: 'I cannot accept 6% (red line is 5%), but I will accept your 30-day timeline.'\n"
        )

    # Build a concise history of last 2 turns so agent sees the trajectory
    recent = ledger.history[-4:] if len(ledger.history) >= 4 else ledger.history
    trajectory = ""
    if recent:
        lines = []
        for entry in recent:
            speaker = entry["party"].upper()
            preview = entry["offer"][:80].replace("\n", " ")
            lines.append(f"  Turn {entry['turn']} {speaker}: {preview}...")
        trajectory = "\nRECENT TRAJECTORY (last 2 turns):\n" + "\n".join(lines)

    return Task(
        description=(
            f"You are negotiating on behalf of {party_name}.\n"
            f"{ledger.to_compact_context()}\n"
            f"{trajectory}\n"
            f"{mediator_block}\n"
            f"Latest offer from {other_party_name}:\n"
            f"\"{incoming_offer}\"\n\n"
            f"CORE DIRECTIVE: You are a pragmatic but tough negotiator. You want a deal, but NEVER at the expense of your Red Lines.\n\n"
            f"RULES — follow in this exact order:\n"
            f"  1. RED LINES ARE ABSOLUTE: You must NEVER make or accept an offer that violates your predefined red lines. If pushed to a red line, clearly state it is your final limit on that issue.\n"
            f"  2. MEDIATOR INPUT: Acknowledge and integrate the mediator's proposal if one exists.\n"
            f"  3. CONDITIONAL CONCESSIONS (GIVE-AND-TAKE): Do not concede for free. If you make a move toward their position on one issue, you MUST demand a concession on another issue (e.g., 'I will accept X, but only if you agree to Y').\n"
            f"  4. PROGRESSION: Do not repeat your exact previous offer. If you are holding firm on an issue, you must pivot and propose a creative solution on a different open issue.\n"
            f"  5. FORMAT: Under 80 words. Specific numbers only. Never restate an already agreed point as a demand. An agreed point cannot be used as a concession."
        ),
        expected_output=(
            f"A tough but strategic response under 80 words using specific numbers. "
            f"Must include a clear give-and-take trade-off if making a concession, "
            f"and contain zero violations of the party's red lines."
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

    # Only allow deadlock declaration after turn 3
    deadlock_instruction = ""
    if ledger.turn < 2:
        deadlock_instruction = (
            f"\nDEADLOCK RULE: This is Turn {ledger.turn}. "
            f"It is too early to declare a deadlock. "
            f"Parties have just begun. DEADLOCK must be NO this turn.\n"
        )
    elif ledger.is_deadlocked(threshold=2):
        deadlock_instruction = (
            f"\nDEADLOCK DETECTED: Both parties have repeated the same "
            f"position for {ledger.deadlock_count} consecutive turns. "
            f"You MUST declare DEADLOCK: YES and propose a trade-off "
            f"that neither party suggested. Explain why it serves both.\n"
        )
    else:
        deadlock_instruction = (
            f"\nDEADLOCK CHECK: Only declare DEADLOCK: YES if both parties "
            f"stated the exact same position as their previous turn on the "
            f"same issue. Partial movement on any issue means NO deadlock. "
            f"When in doubt, declare NO.\n"
        )

    return Task(
        description=(
            f"You are the mediator. Both parties have just spoken.\n\n"
            f"Current ledger state:\n"
            f"{ledger.to_context_string()}\n\n"
            f"{party_a_name} said:\n\"{offer_a}\"\n\n"
            f"{party_b_name} said:\n\"{offer_b}\"\n\n"
            f"{deadlock_instruction}\n"
            f"Your job this turn:\n"
            f"  1. SANITIZE: Restate each party's core proposal without "
            f"     emotional language\n"
            f"  2. FIND AGREEMENT: Identify any point both parties accepted\n"
            f"  3. SUMMARIZE THE GAP: What is still disputed and by how much\n"
            f"  4. DEADLOCK CHECK: Follow the rule above exactly\n"
            f"  5. SETTLEMENT CHECK: Are all open issues resolved?\n\n"
            f"End with this exact block:\n\n"
            f"---LEDGER UPDATE---\n"
            f"NEW_AGREEMENT: <agreed point or NONE>\n"
            f"DEADLOCK: <YES or NO>\n"
            f"TRADE_OFF: <trade-off proposal or NONE>\n"
            f"SETTLEMENT: <YES or NO>\n"
            f"SANITIZED_A: <sanitized version of {party_a_name}'s offer>\n"
            f"SANITIZED_B: <sanitized version of {party_b_name}'s offer>\n"
            f"---END UPDATE---"
        ),
        expected_output=(
            "A mediator analysis followed by the structured LEDGER UPDATE block "
            "with all six fields filled exactly as specified."
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
    
def make_compliant_rerun_task(
    agent: Agent,
    ledger: AgreementLedger,
    party_name: str,
    other_party_name: str,
    original_offer: str,
    violated_red_line: str,
    human_instruction: str,
) -> Task:
    """
    Forces the agent to rerun after a red line violation.
    Unlike the normal counter offer task, this one uses
    mandatory compliance language — the agent MUST follow
    the human instruction, not just acknowledge it.
    """
    return Task(
        description=(
            f"You are negotiating on behalf of {party_name}.\n"
            f"{ledger.to_compact_context()}\n\n"
            f"Your previous offer was flagged for review:\n"
            f"\"{original_offer}\"\n\n"
            f"Issue identified:\n\"{violated_red_line}\"\n\n"
            f"INSTRUCTION FROM YOUR PRINCIPAL (highest authority):\n"
            f"\"{human_instruction}\"\n\n"
            f"Your principal's instruction is your absolute priority. "
            f"Follow it exactly — it overrides your default negotiating "
            f"parameters where they conflict. Your principal has full "
            f"authority to adjust your position.\n\n"
            f"Write a revised offer that:\n"
            f"  1. Follows your principal's instruction to the letter\n"
            f"  2. Respects red lines that your principal has NOT "
            f"     authorized you to cross\n"
            f"  3. Still makes a concrete offer on all open issues\n"
            f"  4. Does not mention this correction process\n\n"
            f"Under 80 words. Specific numbers only."
        ),
        expected_output=(
            f"A revised offer from {party_name} that follows the "
            f"principal's instruction as the top priority. Under 80 words."
        ),
        agent=agent,
    )    