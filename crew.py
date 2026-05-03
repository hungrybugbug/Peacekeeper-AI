# crew.py
import time
import random
import queue
from crewai import Crew, Process

from ledger import AgreementLedger
from agents import create_party_a, create_party_b, create_mediator
from tasks import (
    make_opening_offer_task,
    make_counter_offer_task,
    mediate_task,
    final_report_task,
)
from utils.parser import parse_ledger_update, extract_mediator_instruction
from utils.formatter import format_ledger_panel
from config import MAX_TURNS, INTER_CALL_DELAY


class NegotiationCrew:
    def __init__(self, scenario: dict,
                 event_queue: queue.Queue = None,
                 response_queue: queue.Queue = None):
        self.scenario      = scenario
        self.event_queue   = event_queue    # crew → UI
        self.response_queue = response_queue  # UI → crew

        self.party_a  = create_party_a(
            name      = scenario["party_a"]["name"],
            position  = "Lead negotiator",
            goals     = scenario["party_a"]["goals"],
            red_lines = scenario["party_a"]["red_lines"],
        )
        self.party_b  = create_party_b(
            name      = scenario["party_b"]["name"],
            position  = "Lead negotiator",
            goals     = scenario["party_b"]["goals"],
            red_lines = scenario["party_b"]["red_lines"],
        )
        self.mediator = create_mediator(name=scenario["mediator_name"])

        self.ledger = AgreementLedger(
            scenario     = scenario["title"],
            party_a_name = scenario["party_a"]["name"],
            party_b_name = scenario["party_b"]["name"],
            open_issues  = scenario["open_issues"].copy(),
        )
        self.transcript = []


    def _emit(self, event_type: str, **kwargs):
        """Send an event to the UI queue."""
        if self.event_queue:
            self.event_queue.put({"type": event_type, **kwargs})


    def _log(self, speaker: str, text: str):
        entry = {"speaker": speaker, "text": text}
        self.transcript.append(entry)
        print(f"\n{'='*60}\n  {speaker}\n{'='*60}\n{text}")
        # Push to UI immediately — this is what enables live streaming
        self._emit(
            "transcript",
            speaker = speaker,
            text    = text,
            ledger  = format_ledger_panel(self.ledger),
        )


    def _request_human_input(self, trigger: str, context: str,
                              options: list[str]) -> str:
        """
        Pauses the negotiation thread and waits for human input.
        trigger:  "deadlock" | "red_line"
        context:  description of what's happening
        options:  suggested actions the human can choose or override
        Returns the human's instruction string.
        """
        self._emit(
            "human_input_required",
            trigger = trigger,
            context = context,
            options = options,
        )
        print(f"\n[HITL] Waiting for human input on trigger: {trigger}")

        # Block this thread until UI puts a response in the queue
        while True:
            try:
                response = self.response_queue.get(timeout=1)
                print(f"[HITL] Human responded: {response}")
                return response
            except queue.Empty:
                continue   # keep waiting


    def _check_red_line_pressure(self, offer: str, party_key: str) -> bool:
        """
        Detects if the latest offer from a party is dangerously close
        to or beyond their stated red lines — a signal to ask the human
        whether to allow flexibility.
        """
        red_lines = self.scenario[f"party_{party_key}"]["red_lines"]
        offer_lower = offer.lower()
        for red_line in red_lines:
            # Extract key terms from the red line and check if the offer
            # contradicts or compromises them
            key_terms = [w for w in red_line.lower().split()
                         if len(w) > 4 and w not in
                         {"above","below","never","will","must","cannot","accept","under"}]
            matches = sum(1 for t in key_terms if t in offer_lower)
            if matches >= 2:
                return True
        return False


    def _run_single_agent(self, task, retries: int = 4) -> str:
        for attempt in range(retries):
            try:
                crew = Crew(
                    agents  = [task.agent],
                    tasks   = [task],
                    process = Process.sequential,
                    verbose = False,
                )
                result = crew.kickoff()
                time.sleep(INTER_CALL_DELAY)
                return str(result)
            except Exception as e:
                err = str(e).lower()
                is_rate_limit = any(x in err for x in
                                    ["rate_limit","429","too many"])
                if is_rate_limit and attempt < retries - 1:
                    wait = 60 * (2 ** attempt) + random.uniform(0, 15)
                    print(f"\n[RATE LIMIT] Waiting {wait:.0f}s "
                          f"(attempt {attempt+1}/{retries})...")
                    self._emit("status",
                               text=f"Rate limit hit — waiting {wait:.0f}s...")
                    time.sleep(wait)
                else:
                    raise e
        raise RuntimeError("Max retries exceeded.")


    def run(self) -> dict:
        party_a_name = self.scenario["party_a"]["name"]
        party_b_name = self.scenario["party_b"]["name"]
        mediator_instruction = None

        self._emit("status", text="Agents initialized. Starting Turn 1...")
        print(f"\n{'*'*60}\n  {self.scenario['title']}\n{'*'*60}")

        # ── Turn 1 ─────────────────────────────────────────────
        self._emit("status", text=f"{party_a_name} is preparing opening offer...")
        opening_task = make_opening_offer_task(
            self.party_a, self.ledger, party_a_name
        )
        offer_a = self._run_single_agent(opening_task)
        self.ledger.record_offer("a", offer_a)
        self._log(party_a_name, offer_a)

        self._emit("status", text=f"{party_b_name} is preparing opening offer...")
        counter_task = make_counter_offer_task(
            self.party_b, self.ledger,
            party_b_name, party_a_name, offer_a,
        )
        offer_b = self._run_single_agent(counter_task)
        self.ledger.record_offer("b", offer_b)
        self._log(party_b_name, offer_b)

        self._emit("status", text="Mediator is analyzing Turn 1...")
        med_task = mediate_task(
            self.mediator, self.ledger,
            party_a_name, party_b_name,
            offer_a, offer_b,
        )
        med_output = self._run_single_agent(med_task)
        parse_ledger_update(med_output, self.ledger)
        mediator_instruction = extract_mediator_instruction(med_output)
        self._log(f"Mediator ({self.scenario['mediator_name']})", med_output)

        # ── Turns 2 → MAX_TURNS ────────────────────────────────
        for turn in range(2, MAX_TURNS + 1):

            if self.ledger.status == "settled":
                self._emit("status", text="Settlement reached!")
                break
            if self.ledger.status == "failed":
                self._emit("status", text="Negotiation failed.")
                break

            self._emit("status",
                       text=f"Turn {turn} — {party_a_name} is responding...")

            # ── HITL TRIGGER 1: Deadlock ───────────────────────
            if self.ledger.is_deadlocked(threshold=2):
                agreed_so_far = (", ".join(self.ledger.agreed_points)
                                 or "none yet")
                still_open    = ", ".join(self.ledger.open_issues)

                human_instruction = self._request_human_input(
                    trigger = "deadlock",
                    context = (
                        f"Both parties have repeated the same positions for "
                        f"{self.ledger.deadlock_count} turns with no movement.\n\n"
                        f"Agreed so far: {agreed_so_far}\n"
                        f"Still disputed: {still_open}\n"
                        f"Last offer from {party_a_name}: "
                        f"{self.ledger.last_offer_a}\n"
                        f"Last offer from {party_b_name}: "
                        f"{self.ledger.last_offer_b}"
                    ),
                    options = [
                        "Force both parties to split the difference on each open issue",
                        "Introduce a time pressure — tell parties talks collapse in 1 turn",
                        "Propose a phased agreement — settle easiest issue first",
                        "Allow one party to make a final take-it-or-leave-it offer",
                    ]
                )
                if human_instruction:
                    mediator_instruction = human_instruction
                    self._log(
                        "Human Mediator",
                        f"[HUMAN INTERVENTION on deadlock]\n{human_instruction}"
                    )

            # Party A responds
            input_for_a = self.ledger.get_last_offer("b")
            task_a = make_counter_offer_task(
                self.party_a, self.ledger,
                party_a_name, party_b_name, input_for_a,
                mediator_instruction=mediator_instruction,
            )
            offer_a = self._run_single_agent(task_a)
            self.ledger.record_offer("a", offer_a)
            self._log(party_a_name, offer_a)

            # ── HITL TRIGGER 2: Red Line Pressure ─────────────
            if self._check_red_line_pressure(offer_a, "a"):
                human_instruction = self._request_human_input(
                    trigger = "red_line",
                    context = (
                        f"{party_a_name} appears to be under pressure on "
                        f"a core red line.\n\n"
                        f"Their red lines: "
                        f"{'; '.join(self.scenario['party_a']['red_lines'])}\n"
                        f"Their latest offer: {offer_a}\n\n"
                        f"Should you allow this red line to flex, "
                        f"or hold firm?"
                    ),
                    options = [
                        f"Allow {party_a_name} to flex their red line slightly",
                        f"Hold firm — instruct {party_a_name} to not cross the line",
                        "Reframe the issue so the red line is not directly challenged",
                        "Declare this point non-negotiable and move to other issues",
                    ]
                )
                if human_instruction:
                    self._log(
                        "Human Mediator",
                        f"[HUMAN INTERVENTION on red line — {party_a_name}]\n"
                        f"{human_instruction}"
                    )
                    # Re-run Party A with the human instruction
                    task_a_revised = make_counter_offer_task(
                        self.party_a, self.ledger,
                        party_a_name, party_b_name, input_for_a,
                        mediator_instruction=human_instruction,
                    )
                    offer_a = self._run_single_agent(task_a_revised)
                    self.ledger.record_offer("a", offer_a)
                    self._log(
                        f"{party_a_name} (revised after human input)", offer_a
                    )

            self._emit("status",
                       text=f"Turn {turn} — {party_b_name} is responding...")

            # Party B responds to A's actual current offer
            input_for_b = self.ledger.get_last_offer("a")
            task_b = make_counter_offer_task(
                self.party_b, self.ledger,
                party_b_name, party_a_name, input_for_b,
                mediator_instruction=mediator_instruction,
            )
            offer_b = self._run_single_agent(task_b)
            self.ledger.record_offer("b", offer_b)
            self._log(party_b_name, offer_b)

            self._emit("status",
                       text=f"Turn {turn} — Mediator is analyzing...")

            # Mediator processes turn
            med_task = mediate_task(
                self.mediator, self.ledger,
                party_a_name, party_b_name,
                offer_a, offer_b,
            )
            med_output = self._run_single_agent(med_task)
            parse_ledger_update(med_output, self.ledger)
            mediator_instruction = extract_mediator_instruction(med_output)
            self._log(
                f"Mediator ({self.scenario['mediator_name']})", med_output
            )

        else:
            self.ledger.fail()
            self._emit("status", text=f"Max turns ({MAX_TURNS}) reached.")

        # ── Final report ───────────────────────────────────────
        self._emit("status", text="Generating final report...")
        report_task   = final_report_task(self.mediator, self.ledger)
        final_report  = self._run_single_agent(report_task)
        self._log("Final Report", final_report)

        self._emit("done",
                   status      = self.ledger.status,
                   final_report= final_report)

        return {
            "title"       : self.scenario["title"],
            "status"      : self.ledger.status,
            "transcript"  : self.transcript,
            "ledger"      : self.ledger,
            "final_report": final_report,
        }