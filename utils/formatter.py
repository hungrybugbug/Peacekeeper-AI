# utils/formatter.py
from ledger import AgreementLedger


def format_ledger_panel(ledger: AgreementLedger) -> dict:
    """
    Returns a structured dict for Streamlit to render
    as metric cards and lists — not raw markdown.
    """
    status_map = {
        "in_progress": ("🟡", "In Progress"),
        "settled":     ("🟢", "Settled"),
        "failed":      ("🔴", "Failed"),
    }
    icon, label = status_map.get(ledger.status, ("⚪", ledger.status))

    return {
        "status_icon":   icon,
        "status_label":  label,
        "turn":          ledger.turn,
        "deadlocks":     ledger.deadlock_count,
        "agreed":        ledger.agreed_points,
        "open":          ledger.open_issues,
        "trade_off":     ledger.trade_off_proposed or "None proposed yet",
        "last_a":        ledger.last_offer_a or "—",
        "last_b":        ledger.last_offer_b or "—",
    }


def format_transcript_entry(entry: dict, party_a_name: str, party_b_name: str) -> dict:
    """
    Takes a raw history entry and returns display-ready fields.
    """
    speaker_map = {
        "a":        ("🇺🇸", party_a_name,  "#1a3a5c"),
        "b":        ("🇮🇷", party_b_name,  "#1a3a1a"),
        "mediator": ("⚖️",  "Mediator",    "#3a1a3a"),
    }
    icon, name, color = speaker_map.get(
        entry["party"],
        ("💬", entry["party"], "#333333")
    )
    return {
        "turn":   entry["turn"],
        "icon":   icon,
        "name":   name,
        "color":  color,
        "text":   entry["offer"],
    }


def format_final_report(ledger: AgreementLedger, raw_report: str) -> dict:
    """
    Structures the final report for the summary tab.
    """
    return {
        "title":        ledger.scenario,
        "status":       ledger.status.upper(),
        "total_turns":  ledger.turn,
        "deadlocks":    ledger.deadlock_count,
        "agreed":       ledger.agreed_points,
        "unresolved":   ledger.open_issues,
        "trade_off":    ledger.trade_off_proposed,
        "narrative":    raw_report,
    }