# main.py
import sys
from datetime import datetime
from crew import NegotiationCrew
from scenarios import ALL_SCENARIOS


class OutputLogger:
    """Writes everything to both terminal and a log file simultaneously."""
    def __init__(self, filepath: str):
        self.terminal = sys.stdout
        self.log = open(filepath, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()   # write immediately, don't buffer

    def flush(self):
        self.terminal.flush()
        self.log.flush()

    def close(self):
        self.log.close()


def main():
    # Create timestamped output file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = f"output_{timestamp}.txt"
    logger = OutputLogger(log_path)
    sys.stdout = logger

    print(f"Logging to: {log_path}\n")

    print("\nAvailable scenarios:")
    scenario_list = list(ALL_SCENARIOS.keys())
    for i, name in enumerate(scenario_list):
        print(f"  [{i + 1}] {name}")

    # Restore terminal temporarily for input
    sys.stdout = logger.terminal
    choice = input("\nPick a scenario (number) or press Enter for default: ").strip()
    sys.stdout = logger

    if choice.isdigit() and 1 <= int(choice) <= len(scenario_list):
        scenario_name = scenario_list[int(choice) - 1]
    else:
        scenario_name = scenario_list[0]

    scenario = ALL_SCENARIOS[scenario_name]
    print(f"\nLoading: {scenario_name}")

    crew = NegotiationCrew(scenario)
    result = crew.run()

    print(f"\n{'*'*60}")
    print(f"  NEGOTIATION COMPLETE — {result['status'].upper()}")
    print(f"{'*'*60}")
    print(result["final_report"])
    print(f"\n\nFull log saved to: {log_path}")

    logger.close()
    sys.stdout = logger.terminal


if __name__ == "__main__":
    main()