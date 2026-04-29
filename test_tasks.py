# test_tasks.py  (delete after testing)
from ledger import AgreementLedger
from agents import create_party_a, create_party_b, create_mediator
from tasks import make_opening_offer_task, make_counter_offer_task, mediate_task

ledger = AgreementLedger(
    scenario="USA-Iran nuclear negotiations",
    party_a_name="USA",
    party_b_name="Iran",
    open_issues=["enrichment cap", "inspection rights", "sanction relief"]
)

party_a = create_party_a(
    name="USA",
    position="Lead negotiator",
    goals=["Cap enrichment at 5%", "Mandatory IAEA inspections"],
    red_lines=["No enrichment above 5%", "No sanctions relief before compliance"]
)

party_b = create_party_b(
    name="Iran",
    position="Lead negotiator",
    goals=["Retain 20% enrichment", "Full sanctions relief"],
    red_lines=["Will not accept zero enrichment", "Sovereignty must be respected"]
)

mediator = create_mediator(name="Pakistan")

t1 = make_opening_offer_task(party_a, ledger, "USA")
t2 = make_counter_offer_task(party_b, ledger, "Iran", "USA", "We demand 5% enrichment cap.")
t3 = mediate_task(mediator, ledger, "USA", "Iran", "5% cap is our position.", "20% is our minimum.")

print(f"Task 1 agent : {t1.agent.role}")
print(f"Task 2 agent : {t2.agent.role}")
print(f"Task 3 agent : {t3.agent.role}")
print("\nAll tasks created. Phase 3 complete.")