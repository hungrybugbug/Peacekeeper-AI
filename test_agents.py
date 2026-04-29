# test_agents.py  (delete after testing)
from agents import create_party_a, create_party_b, create_mediator

party_a = create_party_a(
    name="USA",
    position="Lead negotiator",
    goals=["Cap enrichment at 5%", "Mandatory IAEA inspections"],
    red_lines=["No enrichment above 5%", "No sanctions relief before compliance"]
)

party_b = create_party_b(
    name="Iran",
    position="Lead negotiator",
    goals=["Retain 20% enrichment for civilian use", "Full sanctions relief"],
    red_lines=["Will not accept zero enrichment", "Sovereignty must be respected"]
)

mediator = create_mediator(name="Pakistan")

print(f"Party A role : {party_a.role}")
print(f"Party B role : {party_b.role}")
print(f"Mediator role: {mediator.role}")
print("\nAll agents created successfully.")