"""
compare_results.py

Compare the Classical MIQP and Hybrid CVaR-QAOA portfolio results.

Expected result files in:
    data/

The script uses the project's own data_loader.py and constraint settings
so that the comparison is based on the same portfolio data and constraints
used by both optimizers.

Output:
    1. Portfolio-level comparison
    2. Asset-by-asset allocation comparison
    3. Selection summary
    4. Hard-constraint check
    5. Practical interpretation
"""

from pathlib import Path
import sys
import os

import numpy as np
import pandas as pd


# ==========================================================
# Project paths
# ==========================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import *


from config.constraints import (
    BUDGET,
    MAX_ASSETS,
    MIN_WEIGHT,
    MAX_WEIGHT,
    MAX_TECHNOLOGY,
)

from config.user_inputs import DEFAULT_USER_INPUTS



# ==========================================================
# Result-file discovery
# ==========================================================

def find_result_file(kind):
    """
    Find the optimizer result file in data/.

    Edit these patterns only if your filenames use different names.
    """
    if kind == "classical":
        patterns = [
            "*classical*.xlsx",
            "*Classical*.xlsx",
        ]
    else:
        patterns = [
            "*quantum*.xlsx",
            "*Quantum*.xlsx",
            "*qaoa*.xlsx",
            "*QAOA*.xlsx",
        ]

    files = []

    for pattern in patterns:
        files.extend(DATA_DIR.glob(pattern))

    files = list(dict.fromkeys(files))

    if not files:
        raise FileNotFoundError(
            f"No {kind} result file found in:\n{DATA_DIR}"
        )

    # Prefer files containing "result".
    result_files = [
        f for f in files
        if "result" in f.name.lower()
    ]

    return sorted(result_files or files)[0]


# ==========================================================
# Load optimizer outputs
# ==========================================================

def load_output(path):
    """Read the Allocation and Metrics sheets."""
    excel = pd.ExcelFile(path)

    if "Allocation" not in excel.sheet_names:
        raise ValueError(
            f"{path.name} does not contain an 'Allocation' sheet."
        )

    allocation = pd.read_excel(
        path,
        sheet_name="Allocation",
    )

    metrics = (
        pd.read_excel(path, sheet_name="Metrics")
        if "Metrics" in excel.sheet_names
        else pd.DataFrame()
    )

    metrics = (
        metrics.iloc[0].to_dict()
        if not metrics.empty
        else {}
    )

    return allocation, metrics


# ==========================================================
# Allocation handling
# ==========================================================

def clean_allocation(allocation, portfolio_data):
    """
    Convert an optimizer Allocation sheet into a full asset vector.

    The comparison uses the master portfolio ticker ordering from
    data_loader.py, so Classical and Quantum are compared consistently.
    """
    ticker_col = "Ticker"
    weight_col = "Weight"

    if ticker_col not in allocation.columns:
        raise ValueError(
            f"'Ticker' column missing. Found: {list(allocation.columns)}"
        )

    if weight_col not in allocation.columns:
        raise ValueError(
            f"'Weight' column missing. Found: {list(allocation.columns)}"
        )

    weights_by_ticker = dict(
        zip(
            allocation[ticker_col].astype(str),
            pd.to_numeric(
                allocation[weight_col],
                errors="coerce",
            ).fillna(0.0),
        )
    )

    tickers = portfolio_data["tickers"]

    weights = np.array(
        [
            float(weights_by_ticker.get(ticker, 0.0))
            for ticker in tickers
        ],
        dtype=float,
    )

    return weights


# ==========================================================
# Portfolio metrics
# ==========================================================

def calculate_metrics(weights, portfolio_data):
    """
    Calculate the practical portfolio metrics directly from the
    same data used by both optimizers.
    """
    mu = np.asarray(portfolio_data["mu"], dtype=float)
    sigma = np.asarray(portfolio_data["Sigma"], dtype=float)
    dividend = np.asarray(portfolio_data["yield"], dtype=float)
    drawdown = np.asarray(portfolio_data["drawdown"], dtype=float)
    cost = np.asarray(portfolio_data["cost"], dtype=float)

    preferences = DEFAULT_USER_INPUTS

    alpha = float(preferences["alpha"])
    beta = float(preferences["beta"])
    lambda_ = float(preferences["lambda"])
    gamma = float(preferences["gamma"])
    delta = float(preferences["delta"])

    expected_return = float(mu @ weights)

    variance = float(weights @ sigma @ weights)
    variance = max(variance, 0.0)
    risk = float(np.sqrt(variance))

    income = float(dividend @ weights)
    drawdown_value = float(drawdown @ weights)
    cost_value = float(cost @ weights)

    objective = float(
        alpha * expected_return
        + beta * income
        - lambda_ * variance
        - gamma * drawdown_value
        - delta * cost_value
    )

    return {
        "Expected Return": expected_return,
        "Risk / Volatility": risk,
        "Income / Dividend Yield": income,
        "Drawdown": drawdown_value,
        "Transaction Cost": cost_value,
        "Objective / Cost Function": objective,
    }


# ==========================================================
# Hard-constraint checks
# ==========================================================

def check_constraints(weights, portfolio_data):
    """
    Check the same practical hard constraints used in the project.
    """
    breaches = []

    selected = weights > 1e-8
    selected_count = int(np.sum(selected))

    # Budget
    budget_error = abs(float(np.sum(weights)) - BUDGET)

    if budget_error > 1e-5:
        breaches.append(
            f"Budget ({np.sum(weights):.6f} != {BUDGET})"
        )

    # Cardinality
    if selected_count != MAX_ASSETS:
        breaches.append(
            f"Cardinality ({selected_count} != {MAX_ASSETS})"
        )

    # Minimum / maximum weights
    active_weights = weights[selected]

    if len(active_weights) > 0:
        if np.any(active_weights < MIN_WEIGHT - 1e-7):
            breaches.append("Minimum weight")

        if np.any(active_weights > MAX_WEIGHT + 1e-7):
            breaches.append("Maximum weight")

    # Technology exposure
    groups = portfolio_data.get("groups")

    if groups is not None:
        groups = np.asarray(groups)
        technology = groups == "Technology"
        technology_weight = float(
            np.sum(weights[technology])
        )

        if technology_weight > MAX_TECHNOLOGY + 1e-7:
            breaches.append(
                f"Technology exposure ({technology_weight:.4f} "
                f"> {MAX_TECHNOLOGY:.4f})"
            )
    else:
        technology_weight = None

    return {
        "breaches": breaches,
        "breach_count": len(breaches),
        "feasible": len(breaches) == 0,
        "selected_count": selected_count,
        "technology_weight": technology_weight,
    }


# ==========================================================
# Formatting
# ==========================================================

def pct(value):
    return f"{value * 100:.2f}%"


def number(value):
    return f"{value:.6f}"


def seconds(value):
    if value is None:
        return "N/A"
    return f"{float(value):.4f}"


def metric_table(classical, quantum):
    rows = []

    for metric in [
        "Expected Return",
        "Risk / Volatility",
        "Income / Dividend Yield",
        "Drawdown",
        "Transaction Cost",
        "Objective / Cost Function",
    ]:
        rows.append(
            {
                "Metric": metric,
                "Classical": (
                    pct(classical[metric])
                    if metric != "Objective / Cost Function"
                    else number(classical[metric])
                ),
                "Quantum": (
                    pct(quantum[metric])
                    if metric != "Objective / Cost Function"
                    else number(quantum[metric])
                ),
            }
        )

    return pd.DataFrame(rows)


# ==========================================================
# Asset comparison
# ==========================================================

def asset_table(classical_weights, quantum_weights, portfolio_data):
    rows = []

    for i, ticker in enumerate(portfolio_data["tickers"]):
        c = float(classical_weights[i])
        q = float(quantum_weights[i])

        c_selected = c > 1e-8
        q_selected = q > 1e-8

        if c_selected and q_selected:
            selection = "Both"
        elif c_selected:
            selection = "Classical only"
        elif q_selected:
            selection = "Quantum only"
        else:
            selection = "Neither"

        # Only show assets selected by at least one optimizer.
        if c_selected or q_selected:
            rows.append(
                {
                    "Ticker": ticker,
                    "AssetClass": portfolio_data["asset_classes"][i],
                    "Classical": c,
                    "Quantum": q,
                    "Difference": q - c,
                    "Selection": selection,
                }
            )

    result = pd.DataFrame(rows)

    if not result.empty:
        result["_sort"] = result[
            ["Classical", "Quantum"]
        ].max(axis=1)

        result = (
            result
            .sort_values(
                ["_sort", "Ticker"],
                ascending=[False, True],
            )
            .drop(columns="_sort")
            .reset_index(drop=True)
        )

    return result


# ==========================================================
# Printing
# ==========================================================

def title(text):
    print()
    print("=" * 78)
    print(text)
    print("=" * 78)


def print_portfolio_summary(
    classical_metrics,
    quantum_metrics,
    classical_constraints,
    quantum_constraints,
    classical_runtime,
    quantum_runtime,
    quantum_metrics_raw,
):
    title("PORTFOLIO COMPARISON")

    table = metric_table(
        classical_metrics,
        quantum_metrics,
    )

    print(table.to_string(index=False))

    print()
    print(
        f"{'Metric':30s}"
        f"{'Classical':20s}"
        f"{'Quantum':20s}"
    )
    print("-" * 70)

    print(
        f"{'Constraint Breaches':30s}"
        f"{classical_constraints['breach_count']:<20d}"
        f"{quantum_constraints['breach_count']:<20d}"
    )

    print(
        f"{'Feasible':30s}"
        f"{'Yes' if classical_constraints['feasible'] else 'No':<20s}"
        f"{'Yes' if quantum_constraints['feasible'] else 'No':<20s}"
    )

    print(
        f"{'Selected Assets':30s}"
        f"{classical_constraints['selected_count']:<20d}"
        f"{quantum_constraints['selected_count']:<20d}"
    )

    print(
        f"{'Runtime (sec)':30s}"
        f"{seconds(classical_runtime):<20s}"
        f"{seconds(quantum_runtime):<20s}"
    )

    # Quantum-specific diagnostics.
    cvar = quantum_metrics_raw.get("CVaR")
    hamiltonian = quantum_metrics_raw.get(
        "hamiltonian_energy"
    )

    if cvar is not None:
        print(
            f"{'Quantum CVaR':30s}"
            f"{'N/A':<20s}"
            f"{number(float(cvar)):<20s}"
        )

    if hamiltonian is not None:
        print(
            f"{'Quantum Hamiltonian Energy':30s}"
            f"{'N/A':<20s}"
            f"{number(float(hamiltonian)):<20s}"
        )


def print_asset_comparison(table):
    title("ASSET-LEVEL ALLOCATION")

    display = table.copy()

    display["Classical"] = display["Classical"].map(pct)
    display["Quantum"] = display["Quantum"].map(pct)
    display["Difference"] = display["Difference"].map(pct)

    print(
        display[
            [
                "Ticker",
                "AssetClass",
                "Classical",
                "Quantum",
                "Difference",
                "Selection",
            ]
        ].to_string(index=False)
    )


def print_selection_summary(asset_table_data):
    classical = set(
        asset_table_data.loc[
            asset_table_data["Selection"].isin(
                ["Both", "Classical only"]
            ),
            "Ticker",
        ]
    )

    quantum = set(
        asset_table_data.loc[
            asset_table_data["Selection"].isin(
                ["Both", "Quantum only"]
            ),
            "Ticker",
        ]
    )

    common = classical & quantum
    classical_only = classical - quantum
    quantum_only = quantum - classical

    union = classical | quantum
    agreement = (
        len(common) / len(union)
        if union
        else 1.0
    )

    title("SELECTION SUMMARY")

    print(f"Classical selected : {len(classical)}")
    print(f"Quantum selected   : {len(quantum)}")
    print(f"Common assets      : {len(common)}")
    print(f"Classical only     : {len(classical_only)}")
    print(f"Quantum only       : {len(quantum_only)}")
    print(f"Selection agreement: {pct(agreement)}")

    print()
    print(
        "Classical only :",
        ", ".join(sorted(classical_only)) or "None",
    )
    print(
        "Quantum only   :",
        ", ".join(sorted(quantum_only)) or "None",
    )


def print_constraint_details(
    classical_constraints,
    quantum_constraints,
):
    title("HARD-CONSTRAINT CHECK")

    print("Classical:")
    if classical_constraints["breaches"]:
        for breach in classical_constraints["breaches"]:
            print(f"  - {breach}")
    else:
        print("  - No breaches")

    print()
    print("Quantum:")
    if quantum_constraints["breaches"]:
        for breach in quantum_constraints["breaches"]:
            print(f"  - {breach}")
    else:
        print("  - No breaches")


def print_practical_conclusion(
    classical_metrics,
    quantum_metrics,
    classical_constraints,
    quantum_constraints,
):
    title("PRACTICAL COMPARISON")

    if (
        classical_constraints["feasible"]
        and not quantum_constraints["feasible"]
    ):
        print("Classical: feasible")
        print("Quantum  : infeasible")
        print("Conclusion: Classical has the stronger feasible solution.")

    elif (
        quantum_constraints["feasible"]
        and not classical_constraints["feasible"]
    ):
        print("Classical: infeasible")
        print("Quantum  : feasible")
        print("Conclusion: Quantum has the stronger feasible solution.")

    elif (
        classical_constraints["feasible"]
        and quantum_constraints["feasible"]
    ):
        print("Both solutions satisfy the hard constraints.")

        c_return = classical_metrics["Expected Return"]
        q_return = quantum_metrics["Expected Return"]

        c_risk = classical_metrics["Risk / Volatility"]
        q_risk = quantum_metrics["Risk / Volatility"]

        c_objective = classical_metrics[
            "Objective / Cost Function"
        ]
        q_objective = quantum_metrics[
            "Objective / Cost Function"
        ]

        print()

        if q_return > c_return:
            print("Higher expected return : Quantum")
        elif c_return > q_return:
            print("Higher expected return : Classical")
        else:
            print("Higher expected return : Tie")

        if q_risk < c_risk:
            print("Lower risk             : Quantum")
        elif c_risk < q_risk:
            print("Lower risk             : Classical")
        else:
            print("Lower risk             : Tie")

        if q_objective > c_objective:
            print("Higher objective value : Quantum")
        elif c_objective > q_objective:
            print("Higher objective value : Classical")
        else:
            print("Higher objective value : Tie")

        print()
        print(
            "For the project score, prioritize:"
            "\n  1. Zero hard-constraint breaches"
            "\n  2. Risk-adjusted outcome"
            "\n  3. Expected return"
            "\n  4. Cost / turnover"
            "\n  5. Selection agreement and explainability"
        )

    else:
        print("Neither solution is feasible.")
        print("Review the constraint configuration before comparing performance.")


# ==========================================================
# Main
# ==========================================================

def main():
    classical_file = find_result_file("classical")
    quantum_file = find_result_file("quantum")

    portfolio_data = load_portfolio_data()

    classical_allocation, _ = load_output(classical_file)
    quantum_allocation, quantum_metrics_raw = load_output(
        quantum_file
    )

    classical_weights = clean_allocation(
        classical_allocation,
        portfolio_data,
    )

    quantum_weights = clean_allocation(
        quantum_allocation,
        portfolio_data,
    )

    classical_metrics = calculate_metrics(
        classical_weights,
        portfolio_data,
    )

    quantum_metrics = calculate_metrics(
        quantum_weights,
        portfolio_data,
    )

    classical_constraints = check_constraints(
        classical_weights,
        portfolio_data,
    )

    quantum_constraints = check_constraints(
        quantum_weights,
        portfolio_data,
    )

    # Runtime is stored differently depending on optimizer.
    classical_runtime = None
    quantum_runtime = None

    for key, value in quantum_metrics_raw.items():
        if str(key).lower().replace("_", "") in {
            "qaoaruntime",
            "runtimeseconds",
            "runtime",
        }:
            try:
                quantum_runtime = float(value)
            except (TypeError, ValueError):
                pass

    # Classical runtime is not stored in its Metrics sheet by the
    # current classical save_results() implementation.
    # Therefore it is intentionally shown as N/A rather than guessed.

    print()
    print("=" * 78)
    print("CLASSICAL MIQP vs HYBRID CVaR-QAOA")
    print("=" * 78)

    print(f"\nClassical file : {classical_file.name}")
    print(f"Quantum file   : {quantum_file.name}")

    print_portfolio_summary(
        classical_metrics,
        quantum_metrics,
        classical_constraints,
        quantum_constraints,
        classical_runtime,
        quantum_runtime,
        quantum_metrics_raw,
    )

    allocations = asset_table(
        classical_weights,
        quantum_weights,
        portfolio_data,
    )

    print_asset_comparison(allocations)

    print_selection_summary(allocations)

    print_constraint_details(
        classical_constraints,
        quantum_constraints,
    )

    print_practical_conclusion(
        classical_metrics,
        quantum_metrics,
        classical_constraints,
        quantum_constraints,
    )

    print()
    print("=" * 78)
    print("COMPARISON COMPLETE")
    print("=" * 78)


if __name__ == "__main__":
    main()