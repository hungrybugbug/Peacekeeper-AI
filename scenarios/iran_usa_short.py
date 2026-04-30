# scenarios/iran_usa_short.py
SCENARIO = {
    "title": "USA-Iran Quick Talks — Enrichment Only",
    "mediator_name": "Pakistan",
    "party_a": {
        "name": "USA",
        "goals": [
            "Cap uranium enrichment at 5%",
            "Tie any enrichment agreement to IAEA verification"
        ],
        "red_lines": [
            "Will not accept enrichment above 5% under any framing"
        ],
    },
    "party_b": {
        "name": "Iran",
        "goals": [
            "Retain enrichment rights at 10% for civilian energy",
            "Any cap must include guaranteed sanctions relief"
        ],
        "red_lines": [
            "Will not accept zero enrichment",
            "Will not sign any cap without sanctions relief attached"
        ],
    },
    "open_issues": [
        "enrichment cap percentage",
        "sanctions relief condition"
    ]
}