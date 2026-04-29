# crew.py
from crewai import Crew, Process
from groq import RateLimitError
import time
from ledger import AgreementLedger
from agents import create_party_a, create_party_b, create_mediator
from tasks import (
    make_opening_offer_task,
    make_counter_offer_task,
    mediate_task,
    final_report_task,
)
from utils.parser import parse_ledger_update, extract_mediator_instruction
from config import MAX_TURNS, DEADLOCK_THRESHOLD, INTER_CALL_DELAY


class NegotiationCrew:
    def __init__(self, scenario: dict):
        self.scenario = scenario

        # Build agents from scenario data
        self.party_a = create_party_a(
            name=scenario["party_a"]["name"],
            position="Lead negotiator",
            goals=scenario["party_a"]["goals"],
            red_lines=scenario["party_a"]["red_lines"],
        )
        self.party_b = create_party_b(
            name=scenario["party_b"]["name"],
            position="Lead negotiator",
            goals=scenario["party_b"]["goals"],
            red_lines=scenario["party_b"]["red_lines"],
        )
        self.mediator = create_mediator(
            name=scenario["mediator_name"]
        )

        # Initialize ledger
        self.ledger = AgreementLedger(
            scenario=scenario["title"],
            party_a_name=scenario["party_a"]["name"],
            party_b_name=scenario["party_b"]["name"],
            open_issues=scenario["open_issues"].copy(),
        )

        # Will store full transcript for UI
        self.transcript = []

    def _log(self, speaker: str, text: str):
        """Append to transcript and print to terminal."""
        entry = {"speaker": speaker, "text": text}
        self.transcript.append(entry)
        print(f"\n{'='*60}")
        print(f"  {speaker}")
        print(f"{'='*60}")
        print(text)

    def _run_single_agent(self, task, retries: int = 3) -> str:
        for attempt in range(retries):
            try:
                crew = Crew(
                    agents=[task.agent],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=False,
                )
                result = crew.kickoff()
                time.sleep(INTER_CALL_DELAY)
                return str(result)
            except Exception as e:
                if "rate_limit" in str(e).lower() or "429" in str(e):
                    wait = 60 * (attempt + 1)  # 60s, 120s, 180s
                    print(f"\n[RATE LIMIT] Waiting {wait}s before retry {attempt+1}/{retries}...")
                    time.sleep(wait)
                else:
                    raise e
        raise RuntimeError("Max retries exceeded due to rate limiting.")

    def run(self) -> dict:
        """
        Main negotiation loop.
        Returns a summary dict with transcript, ledger, and final report.
        """
        party_a_name = self.scenario["party_a"]["name"]
        party_b_name = self.scenario["party_b"]["name"]

        print(f"\n{'*'*60}")
        print(f"  NEGOTIATION: {self.scenario['title']}")
        print(f"  Mediator: {self.scenario['mediator_name']}")
        print(f"{'*'*60}")

        # ── Turn 1: Party A opens ──────────────────────────────
        opening_task = make_opening_offer_task(
            self.party_a, self.ledger, party_a_name
        )
        offer_a = self._run_single_agent(opening_task)
        self.ledger.record_offer("a", offer_a)
        self._log(party_a_name, offer_a)

        # Party B responds to opening
        counter_task = make_counter_offer_task(
            self.party_b, self.ledger,
            party_b_name, party_a_name, offer_a
        )
        offer_b = self._run_single_agent(counter_task)
        self.ledger.record_offer("b", offer_b)
        self._log(party_b_name, offer_b)

        # Mediator processes Turn 1
        med_task = mediate_task(
            self.mediator, self.ledger,
            party_a_name, party_b_name,
            offer_a, offer_b
        )
        med_output = self._run_single_agent(med_task)
        parsed = parse_ledger_update(med_output, self.ledger)
        mediator_instruction = extract_mediator_instruction(med_output)  # NEW
        self._log(f"MEDIATOR ({self.scenario['mediator_name']})", med_output)

        # ── Turns 2 to MAX_TURNS ───────────────────────────────
        for turn in range(2, MAX_TURNS + 1):

            # Check for early exit
            if self.ledger.status == "settled":
                print(f"\n[SYSTEM] Settlement reached at turn {turn - 1}.")
                break

            if self.ledger.status == "failed":
                print(f"\n[SYSTEM] Negotiation failed at turn {turn - 1}.")
                break

            print(f"\n[SYSTEM] ── Turn {turn} ──────────────────────────────")
            print(self.ledger.to_context_string())

            # Use sanitized versions from mediator as inputs
            # Falls back to raw if parser missed them
            input_for_b = parsed.get("sanitized_a") or self.ledger.last_offer_a
            input_for_a = parsed.get("sanitized_b") or self.ledger.last_offer_b

            # Party A responds to B's last sanitized offer
            task_a = make_counter_offer_task(
                self.party_a, self.ledger,
                party_a_name, party_b_name, input_for_a,
                mediator_instruction=mediator_instruction, 
            )
            offer_a = self._run_single_agent(task_a)
            self.ledger.record_offer("a", offer_a)
            self._log(party_a_name, offer_a)

            # Party B responds to A's last sanitized offer
            task_b = make_counter_offer_task(
                self.party_b, self.ledger,
                party_b_name, party_a_name, input_for_b,
                mediator_instruction=mediator_instruction,
            )
            offer_b = self._run_single_agent(task_b)
            self.ledger.record_offer("b", offer_b)
            self._log(party_b_name, offer_b)

            # Mediator processes this turn
            med_task = mediate_task(
                self.mediator, self.ledger,
                party_a_name, party_b_name,
                offer_a, offer_b
            )
            med_output = self._run_single_agent(med_task)
            parsed = parse_ledger_update(med_output, self.ledger)
            self._log(f"MEDIATOR ({self.scenario['mediator_name']})", med_output)

        # ── Max turns hit with no settlement ──────────────────
        else:
            self.ledger.fail()
            print(f"\n[SYSTEM] Max turns ({MAX_TURNS}) reached. Negotiation failed.")

        # ── Final report ───────────────────────────────────────
        report_task = final_report_task(self.mediator, self.ledger)
        final_report = self._run_single_agent(report_task)
        self._log("FINAL REPORT", final_report)

        return {
            "title": self.scenario["title"],
            "status": self.ledger.status,
            "transcript": self.transcript,
            "ledger": self.ledger,
            "final_report": final_report,
        }