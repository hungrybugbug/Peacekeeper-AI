# experiments/run_comparative_study.py
"""
Offline comparative study for the course milestone: multiple "model" behaviors
(via mock LLM profiles), several scenarios, quantitative metrics, curves, and
tables — no remote API usage when PEACEKEEPER_EXPERIMENT_BACKEND=mock.

For a short live validation (e.g. ≤8 full runs), unset mock flags and use
`--live` plus `--max-live-runs`; each run will call real providers.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _base_env(
    *,
    mock: bool,
    max_turns: int,
    profile_a: str,
    profile_b: str,
    profile_m: str,
    seed: int,
) -> dict[str, str]:
    env: dict[str, str] = {
        "PEACEKEEPER_MAX_TURNS": str(max_turns),
        "PEACEKEEPER_RUN_SEED": str(seed),
    }
    if mock:
        env["PEACEKEEPER_INTER_CALL_DELAY_SEC"] = "0"
        env["PEACEKEEPER_MOCK_PROFILE_PARTY_A"] = profile_a
        env["PEACEKEEPER_MOCK_PROFILE_PARTY_B"] = profile_b
        env["PEACEKEEPER_MOCK_PROFILE_MEDIATOR"] = profile_m
        env["PEACEKEEPER_EXPERIMENT_BACKEND"] = "mock"
        env["PEACEKEEPER_MOCK_REDLINES"] = "1"
    else:
        env["PEACEKEEPER_INTER_CALL_DELAY_SEC"] = os.getenv(
            "PEACEKEEPER_INTER_CALL_DELAY_SEC", "15"
        )
    return env


def _clear_mock_env():
    for k in (
        "PEACEKEEPER_EXPERIMENT_BACKEND",
        "PEACEKEEPER_MOCK_REDLINES",
        "PEACEKEEPER_MOCK_PROFILE_PARTY_A",
        "PEACEKEEPER_MOCK_PROFILE_PARTY_B",
        "PEACEKEEPER_MOCK_PROFILE_MEDIATOR",
    ):
        os.environ.pop(k, None)


def _apply_env(updates: dict[str, str]):
    for k, v in updates.items():
        os.environ[k] = v


def _run_single(
    scenario_name: str,
    scenario: dict,
    cfg_id: str,
    profiles: tuple[str, str, str],
    seed: int,
    mock: bool,
    max_turns: int,
):
    pa, pb, pm = profiles
    os.environ["PEACEKEEPER_AGENT_VERBOSE"] = "false"

    if not mock:
        _clear_mock_env()
    env = _base_env(
        mock=mock,
        max_turns=max_turns,
        profile_a=pa,
        profile_b=pb,
        profile_m=pm,
        seed=seed,
    )
    _apply_env(env)

    trace: list[dict] = []
    from crew import NegotiationCrew

    crew = NegotiationCrew(
        scenario,
        event_queue=None,
        response_queue=None,
        auto_hitl=True,
        experiment_trace=trace,
    )
    result = crew.run()

    hitl_n = sum(1 for e in trace if e.get("type") == "auto_hitl")
    snaps = [e for e in trace if e.get("type") == "ledger_snapshot"]

    return {
        "config_id": cfg_id,
        "scenario_name": scenario_name,
        "seed": seed,
        "profiles_party_a": pa,
        "profiles_party_b": pb,
        "profiles_mediator": pm,
        "status": result["ledger"].status,
        "ledger_turn": result["ledger"].turn,
        "deadlock_count": result["ledger"].deadlock_count,
        "agreed_n": len(result["ledger"].agreed_points),
        "open_issues_n": len(result["ledger"].open_issues),
        "hitl_interventions": hitl_n,
        "trace": trace,
        "snapshots": snaps,
        "mock_backend": mock,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use real LLM APIs from .env (no mock backend).",
    )
    parser.add_argument("--trials", type=int, default=4, help="Runs per config×scenario.")
    parser.add_argument("--max-turns", type=int, default=5)
    parser.add_argument(
        "--max-live-runs",
        type=int,
        default=8,
        help="Stop after this many completed live runs (ignored in mock mode).",
    )
    args = parser.parse_args()
    mock = not args.live

    plt = _ensure_matplotlib()
    from scenarios import ALL_SCENARIOS

    results_dir = ROOT / "experiments" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Four comparative "model stacks" (profiles act as generative behavior ablations).
    configs = [
        ("Cfg1_AllCooperative", ("cooperative", "cooperative", "cooperative")),
        ("Cfg2_AllBalanced", ("balanced", "balanced", "balanced")),
        ("Cfg3_CoopVsStubborn", ("cooperative", "stubborn", "balanced")),
        ("Cfg4_AllStubborn", ("stubborn", "stubborn", "stubborn")),
    ]

    traces_path = results_dir / "run_traces.jsonl"
    csv_path = results_dir / "summary.csv"

    rows: list[dict] = []
    live_completed = 0
    stop_live = False

    with traces_path.open("w", encoding="utf-8") as tlog:
        for cfg_id, profiles in configs:
            if stop_live:
                break

            for scenario_name, scenario in ALL_SCENARIOS.items():
                if stop_live:
                    break

                for trial in range(args.trials):
                    seed = (
                        hash((cfg_id, scenario_name, trial)) % (2**31 - 1)
                    ) + 1

                    if not mock and live_completed >= args.max_live_runs:
                        stop_live = True
                        break

                    out = _run_single(
                        scenario_name,
                        scenario,
                        cfg_id,
                        profiles,
                        seed,
                        mock=mock,
                        max_turns=args.max_turns,
                    )
                    if not mock:
                        live_completed += 1

                    snap = out.pop("snapshots", [])
                    trace = out.pop("trace", [])
                    row = {k: v for k, v in out.items() if k != "snapshots"}
                    row["trace_json"] = json.dumps(trace)
                    rows.append(row)

                    tlog.write(
                        json.dumps(
                            {
                                "config_id": cfg_id,
                                "scenario_name": scenario_name,
                                "trial": trial,
                                "seed": seed,
                                "trace": trace,
                            }
                        )
                        + "\n"
                    )

                if stop_live:

                    break

            if stop_live:

                break

    fieldnames = [
        "config_id",
        "scenario_name",
        "seed",
        "profiles_party_a",
        "profiles_party_b",
        "profiles_mediator",
        "status",
        "ledger_turn",
        "deadlock_count",
        "agreed_n",
        "open_issues_n",
        "hitl_interventions",
        "mock_backend",
        "trace_json",
    ]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})

    # ── Plot 1: settlement rate by config ─────────────────────
    settled_rate: dict[str, list[int]] = defaultdict(list)
    for r in rows:

        settled_rate[r["config_id"]].append(
            1 if r["status"] == "settled" else 0
        )

    cfg_ids = [c[0] for c in configs]
    rates = [
        sum(settled_rate[c]) / max(1, len(settled_rate[c])) for c in cfg_ids
    ]

    fig1, ax1 = plt.subplots(figsize=(9, 4.5))
    bars = ax1.bar(cfg_ids, rates, color=["#2d6a4f", "#40916c", "#74c69d", "#95d5b2"])
    ax1.set_ylim(0, 1.05)
    ax1.set_ylabel("Settlement rate")
    ax1.set_title("Comparative settlement rate (mock profiles = model ablations)")
    for b, v in zip(bars, rates, strict=True):
        ax1.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}", ha="center")
    fig1.tight_layout()
    fig1.savefig(results_dir / "fig_settlement_rate.png", dpi=150)

    # ── Plot 2: mean agreed points vs mediator snapshot index ─
    curve = defaultdict(lambda: defaultdict(list))
    for r in rows:
        trace = json.loads(r["trace_json"])
        snaps = [e for e in trace if e.get("type") == "ledger_snapshot"]

        for i, s in enumerate(snaps):
            curve[r["config_id"]][i].append(s["agreed_n"])

    fig2, ax2 = plt.subplots(figsize=(9, 4.5))
    for cfg_id in cfg_ids:
        xs = sorted(curve[cfg_id].keys())
        if not xs:

            continue

        ys = [sum(curve[cfg_id][i]) / len(curve[cfg_id][i]) for i in xs]
        ax2.plot(xs, ys, marker="o", label=cfg_id)
    ax2.set_xlabel("Mediator snapshot index (proxy for negotiation progress)")
    ax2.set_ylabel("Mean agreed clauses (count)")
    ax2.set_title("Convergence curves: agreed items vs progress snapshots")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)
    fig2.tight_layout()
    fig2.savefig(results_dir / "fig_convergence_curves.png", dpi=150)

    # ── Text table for paper paste ───────────────────────────
    table_path = results_dir / "comparison_table.txt"

    with table_path.open("w", encoding="utf-8") as tf:
        tf.write("config\tmean_settled\tmean_agreed_n\tmean_hitl\tmean_deadlocks\n")
        for cid in cfg_ids:
            sub = [r for r in rows if r["config_id"] == cid]
            if not sub:

                continue

            ms = sum(1 for r in sub if r["status"] == "settled") / len(sub)
            ma = sum(r["agreed_n"] for r in sub) / len(sub)
            mh = sum(r["hitl_interventions"] for r in sub) / len(sub)
            md = sum(r["deadlock_count"] for r in sub) / len(sub)
            tf.write(
                f"{cid}\t{ms:.3f}\t{ma:.3f}\t{mh:.3f}\t{md:.3f}\n"
            )

    print(f"Wrote: {csv_path}")
    print(f"Wrote: {traces_path}")
    print(f"Wrote: {table_path}")
    print(f"Plots: {results_dir / 'fig_settlement_rate.png'}")
    print(f"       {results_dir / 'fig_convergence_curves.png'}")
    if not mock:

        print(f"(Live runs completed: {live_completed})")


if __name__ == "__main__":
    main()
