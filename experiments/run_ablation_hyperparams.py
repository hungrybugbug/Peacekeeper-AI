# experiments/run_ablation_hyperparams.py
"""Mock ablation: sweep PEACEKEEPER_MAX_TURNS; write CSV/txt for the paper."""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.run_comparative_study import _run_single  # noqa: E402

SCENARIOS = __import__("scenarios", fromlist=["ALL_SCENARIOS"]).ALL_SCENARIOS

CONFIGS = [
    ("Cfg1_AllCooperative", ("cooperative", "cooperative", "cooperative")),
    ("Cfg4_AllStubborn", ("stubborn", "stubborn", "stubborn")),
]


def main():
    out_dir = ROOT / "experiments" / "results"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for tmax in (3, 5, 7):
        for cfg_id, profiles in CONFIGS:
            settled = 0
            total = 0
            turns_sum = 0.0
            agreed_sum = 0.0
            diag_sum = 0.0
            for scenario_name, scenario in SCENARIOS.items():
                for trial in range(4):
                    seed = hash((cfg_id, scenario_name, trial, tmax)) % (2**31 - 1) + 1
                    r = _run_single(
                        scenario_name,
                        scenario,
                        cfg_id,
                        profiles,
                        seed,
                        mock=True,
                        max_turns=tmax,
                    )
                    total += 1
                    turns_sum += r["ledger_turn"]
                    agreed_sum += r["agreed_n"]
                    settled += int(r["status"] == "settled")
                    diag_sum += r["ledger_turn"] + len(r["trace"])

            rows.append(
                {
                    "T_max": tmax,
                    "config_id": cfg_id,
                    "settlement_rate": settled / total,
                    "mean_ledger_turn": turns_sum / total,
                    "mean_agreed_n": agreed_sum / total,
                    "mean_diag_units": diag_sum / total,
                }
            )

    csv_path = out_dir / "ablation_max_turns.csv"
    txt_path = out_dir / "ablation_max_turns.txt"
    keys = list(rows[0].keys()) if rows else []
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    with txt_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(
                f"T_max={row['T_max']:d}\t{row['config_id']}\t"
                f"rho={row['settlement_rate']:.3f}\t"
                f"mean_turns={row['mean_ledger_turn']:.3f}\t"
                f"mean_agreed={row['mean_agreed_n']:.3f}\t"
                f"mean_diag_units={row['mean_diag_units']:.1f}\n"
            )

    print(csv_path)


if __name__ == "__main__":
    os.environ.setdefault("PEACEKEEPER_AGENT_VERBOSE", "false")
    main()
