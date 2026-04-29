# utils/parser.py
from ledger import AgreementLedger


def extract_mediator_instruction(mediator_output: str) -> str | None:
    """
    Pulls out the TRADE_OFF line from mediator output so we can
    pass it directly to party agents as a forced acknowledgment.
    """
    try:
        start = mediator_output.index("---LEDGER UPDATE---")
        end = mediator_output.index("---END UPDATE---")
        block = mediator_output[start:end]
    except ValueError:
        return None

    for line in block.splitlines():
        if line.startswith("TRADE_OFF:"):
            value = line.split(":", 1)[1].strip()
            if value.upper() != "NONE" and value:
                return value
    return None

def parse_ledger_update(mediator_output: str, ledger: AgreementLedger) -> dict:
    """
    Reads the structured block the mediator always produces:

        ---LEDGER UPDATE---
        NEW_AGREEMENT: ...
        DEADLOCK: YES/NO
        TRADE_OFF: ...
        SETTLEMENT: YES/NO
        SANITIZED_A: ...
        SANITIZED_B: ...
        ---END UPDATE---

    Updates the ledger in place and returns a dict of parsed values
    so crew.py can use them to route the next turn.
    """
    result = {
        "new_agreement": None,
        "deadlock": False,
        "trade_off": None,
        "settlement": False,
        "sanitized_a": None,
        "sanitized_b": None,
    }

    # Extract only the block between the delimiters
    try:
        start = mediator_output.index("---LEDGER UPDATE---")
        end = mediator_output.index("---END UPDATE---")
        block = mediator_output[start:end]
    except ValueError:
        # Mediator didn't follow the format — log and return defaults
        print("[PARSER WARNING] No LEDGER UPDATE block found in mediator output.")
        return result

    for line in block.splitlines():
        line = line.strip()

        if line.startswith("NEW_AGREEMENT:"):
            value = line.split(":", 1)[1].strip()
            if value.upper() != "NONE" and value:
                result["new_agreement"] = value
                ledger.add_agreed_point(value)

        elif line.startswith("DEADLOCK:"):
            value = line.split(":", 1)[1].strip().upper()
            if value == "YES":
                result["deadlock"] = True
                ledger.increment_deadlock()

        elif line.startswith("TRADE_OFF:"):
            value = line.split(":", 1)[1].strip()
            if value.upper() != "NONE" and value:
                result["trade_off"] = value
                ledger.propose_trade_off(value)

        elif line.startswith("SETTLEMENT:"):
            value = line.split(":", 1)[1].strip().upper()
            if value == "YES":
                result["settlement"] = True
                ledger.settle()

        elif line.startswith("SANITIZED_A:"):
            result["sanitized_a"] = line.split(":", 1)[1].strip()

        elif line.startswith("SANITIZED_B:"):
            result["sanitized_b"] = line.split(":", 1)[1].strip()

    return result