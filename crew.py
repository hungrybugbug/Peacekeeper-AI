# crew.py
import time
import random
import queue
from crewai import Crew, Process
from utils.red_line_validator import check_red_lines

from ledger import AgreementLedger
from agents import create_party_a, create_party_b, create_mediator
from tasks import (
    make_opening_offer_task,
    make_counter_offer_task,
    make_compliant_rerun_task,
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


    def _validate_and_correct(
        self,
        offer: str,
        party_key: str,          # "a" or "b"
        agent,
        ledger: AgreementLedger,
        party_name: str,
        other_party_name: str,
        incoming_offer: str,
        max_attempts: int = 2,
    ) -> str:
        """
        Validation loop:
        1. Check offer against red lines using isolated LLM
        2. If violation — trigger HITL, get human instruction
        3. Rerun agent with mandatory compliance task
        4. Check again (max_attempts times)
        5. Return final offer whether clean or not (with warning)
        """
        red_lines = self.scenario[f"party_{party_key}"]["red_lines"]
        current_offer = offer

        for attempt in range(max_attempts):
            result = check_red_lines(current_offer, party_name, red_lines)

            print(f"[VALIDATOR] Party {party_key.upper()} attempt {attempt+1}: "
                f"violation={result['violation']} "
                f"severity={result['severity']}")

            # No violation — offer is clean, return it
            if not result["violation"] \
                or result["severity"] == "none" \
                or result["severity"] == "soft":
                    if result["violation"] and result["severity"] == "soft":
                        # Log soft violations silently for debugging without blocking
                        print(f"[VALIDATOR] Soft violation noted but not blocking: "
                            f"{result['explanation']}")
                        self._log(
                            "System",
                            f"[Note: soft red line pressure detected in "
                            f"{party_name}'s offer — monitoring but not blocking]"
                        )
                    return current_offer

            # Soft violation on second attempt — warn but allow through
            if attempt == max_attempts - 1 and result["severity"] == "soft":
                print(f"[VALIDATOR] Soft violation on final attempt — allowing through")
                self._log(
                    "System",
                    f"[Note: {party_name}'s offer has borderline language "
                    f"near a red line but was allowed to proceed]"
                )
                return current_offer

            # Hard or soft violation — trigger HITL
            self._emit("status",
                    text=f"Red line violation detected in {party_name}'s offer...")

            human_instruction = self._request_human_input(
                trigger = "red_line",
                context = (
                    f"{party_name} has violated a red line.\n\n"
                    f"Violated red line:\n"
                    f"\"{result['violated_red_line']}\"\n\n"
                    f"Violation details:\n"
                    f"{result['explanation']}\n\n"
                    f"Severity: {result['severity'].upper()}\n\n"
                    f"The offer that caused this:\n"
                    f"\"{current_offer}\""
                ),
                options = [
                    "FALSE POSITIVE — ignore this alert and continue as normal",   # NEW
                    f"Instruct {party_name} to strictly hold their red line "
                    f"and find another concession instead",
                    "Allow a one-time exception — this concession is strategic",
                    "Reframe the issue so the red line is not directly challenged",
                    "Declare this point non-negotiable and move to other issues",
                ]
            )

            self._log(
                "Human Mediator",
                f"[HUMAN INTERVENTION — Red Line Violation by {party_name}]\n"
                f"Violated: {result['violated_red_line']}\n"
                f"Human instruction: {human_instruction}"
            )

            # Check if human chose to allow the exception
            false_positive_keywords = ["false positive", "ignore", "false alarm", "no violation"]
            allow_keywords = ["allow", "exception", "strategic", "permit", "accept"]
            human_lower = human_instruction.lower()
            
            if any(kw in human_lower for kw in false_positive_keywords):
                # Human confirmed this is a false positive
                # Do NOT rerun — return original offer completely unchanged
                self._log(
                    "System",
                    f"[Human confirmed false positive for {party_name}. "
                    f"Original offer accepted as-is. Continuing negotiation.]"
                )
                return current_offer

            if any(kw in human_lower for kw in allow_keywords):
                # Human authorized a genuine exception to the red line
                self._log(
                    "System",
                    f"[Human authorized red line exception for {party_name}. "
                    f"Offer accepted as-is.]"
                )
                return current_offer
            # Human said hold firm — rerun with mandatory compliance task
            self._emit("status",
                    text=f"{party_name} rewriting offer to respect red lines...")

            rerun_task = make_compliant_rerun_task(
                agent              = agent,
                ledger             = ledger,
                party_name         = party_name,
                other_party_name   = other_party_name,
                original_offer     = current_offer,
                violated_red_line  = result["violated_red_line"] or "",
                human_instruction  = human_instruction,
            )
            current_offer = self._run_single_agent(rerun_task)
            self._log(
                f"{party_name} (corrected)",
                current_offer
            )

        # Exhausted attempts — return last offer with warning
        print(f"[VALIDATOR] Max attempts reached for {party_key.upper()}. "
            f"Using last generated offer.")
        return current_offer            

    def _check_red_line_pressure(self, offer: str, party_key: str) -> bool:
        """
        Checks if the offer numerically or semantically violates
        any stated red line. Uses specific pattern matching for
        percentage/number-based red lines, plus keyword fallback.
        """
        import re
        red_lines  = self.scenario[f"party_{party_key}"]["red_lines"]
        offer_lower = offer.lower()

        for red_line in red_lines:
            red_lower = red_line.lower()

            # ── Numeric violation check ────────────────────────
            # Pattern: red line says "above X%" or "below X%"
            # Check if the offer contains a number that violates that bound
            above_match = re.search(
                r'(?:above|exceed|more than|higher than)\s*(\d+\.?\d*)\s*%',
                red_lower
            )
            below_match = re.search(
                r'(?:below|under|less than|lower than)\s*(\d+\.?\d*)\s*%',
                red_lower
            )

            # Extract all percentages mentioned in the offer
            offer_percentages = [
                float(p) for p in
                re.findall(r'(\d+\.?\d*)\s*%', offer_lower)
            ]

            if above_match and offer_percentages:
                threshold = float(above_match.group(1))
                # If any offered percentage EXCEEDS the red line threshold
                if any(p > threshold for p in offer_percentages):
                    print(f"[RED LINE] Numeric violation detected: "
                        f"offer contains {offer_percentages}, "
                        f"red line threshold is {threshold}%")
                    return True

            if below_match and offer_percentages:
                threshold = float(below_match.group(1))
                if any(p < threshold for p in offer_percentages):
                    print(f"[RED LINE] Numeric violation detected: "
                        f"offer contains {offer_percentages}, "
                        f"red line threshold is {threshold}%")
                    return True

            # ── Keyword fallback for non-numeric red lines ─────
            # e.g. "will not accept unannounced inspections"
            key_terms = [
                w for w in red_lower.split()
                if len(w) > 5 and w not in {
                    "accept", "above", "below", "never", "under",
                    "framing", "condition", "cannot", "will", "must",
                    "agree", "allow", "permit"
                }
            ]
            if len(key_terms) >= 2:
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
                is_transient = any(x in err for x in [
                    "rate_limit", "429", "too many",
                    "503", "unavailable", "service unavailable",
                    "high demand",
                ])
                if is_transient and attempt < retries - 1:
                    wait = 60 * (2 ** attempt) + random.uniform(0, 15)
                    print(f"\n[TRANSIENT ERROR] Waiting {wait:.0f}s "
                          f"(attempt {attempt+1}/{retries})...")
                    self._emit("status",
                               text=f"Temporary service issue — waiting {wait:.0f}s...")
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
            offer_a = self._validate_and_correct(
                offer            = offer_a,
                party_key        = "a",
                agent            = self.party_a,
                ledger           = self.ledger,
                party_name       = party_a_name,
                other_party_name = party_b_name,
                incoming_offer   = input_for_a,
                )
            self.ledger.record_offer("a", offer_a)
            self._log(party_a_name, offer_a)

            # ── HITL TRIGGER 2: Red Line Pressure ─────────────────
            # if self._check_red_line_pressure(offer_a, "a"):
            #     red_lines_text = "\n".join(
            #         self.scenario["party_a"]["red_lines"]
            #     )
            #     human_instruction = self._request_human_input(
            #         trigger = "red_line",
            #         context = (
            #             f"{party_a_name} has made an offer that appears to "
            #             f"cross or approach one of their stated red lines.\n\n"
            #             f"Red lines for {party_a_name}:\n{red_lines_text}\n\n"
            #             f"Offer that triggered this:\n{offer_a}"
            #         ),
            #         options = [
            #             f"Allow {party_a_name} to flex slightly — accept the offer as is",
            #             f"Instruct {party_a_name} to retract and hold their red line firmly",
            #             "Reframe the issue so the red line is not directly challenged",
            #             "Declare this specific point non-negotiable and skip to next issue",
            #         ]
            #     )
            #     if human_instruction:
            #         # Carry forward into mediator and next party task
            #         mediator_instruction = (
            #             f"HUMAN OVERRIDE ON RED LINE: {human_instruction}"
            #         )
            #         self._log(
            #             "Human Mediator",
            #             f"[HUMAN INTERVENTION — Red Line ({party_a_name})]\n"
            #             f"{human_instruction}"
            #         )

            # Party B responds to A's actual current offer
            input_for_b = self.ledger.get_last_offer("a")
            task_b = make_counter_offer_task(
                self.party_b, self.ledger,
                party_b_name, party_a_name, input_for_b,
                mediator_instruction=mediator_instruction,
            )
            offer_b = self._run_single_agent(task_b)
            offer_b = self._validate_and_correct(
                offer            = offer_b,
                party_key        = "b",
                agent            = self.party_b,
                ledger           = self.ledger,
                party_name       = party_b_name,
                other_party_name = party_a_name,
                incoming_offer   = input_for_b,
            )
            self.ledger.record_offer("b", offer_b)
            self._log(party_b_name, offer_b)
            # if self._check_red_line_pressure(offer_b, "b"):
            #     red_lines_text = "\n".join(
            #         self.scenario["party_b"]["red_lines"]
            #     )
            #     human_instruction = self._request_human_input(
            #         trigger = "red_line",
            #         context = (
            #             f"{party_b_name} has made an offer that appears to "
            #             f"cross or approach one of their stated red lines.\n\n"
            #             f"Red lines for {party_b_name}:\n{red_lines_text}\n\n"
            #             f"Offer that triggered this:\n{offer_b}"
            #         ),
            #         options = [
            #             f"Allow {party_b_name} to flex slightly — accept the offer as is",
            #             f"Instruct {party_b_name} to retract and hold their red line firmly",
            #             "Reframe the issue so the red line is not directly challenged",
            #             "Declare this specific point non-negotiable and skip to next issue",
            #         ]
            #     )
            #     if human_instruction:
            #         mediator_instruction = (
            #             f"HUMAN OVERRIDE ON RED LINE: {human_instruction}"
            #         )
            #         self._log(
            #             "Human Mediator",
            #             f"[HUMAN INTERVENTION — Red Line ({party_b_name})]\n"
            #             f"{human_instruction}"
            #         )
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
            if self.ledger.status == "in_progress":
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