"""
hybrid_classical_optimizer.py

Continuous weight refinement after CVaR-QAOA asset selection.

The quantum solver decides x (which assets are selected).
This file uses Gurobi to decide w (how much to allocate to each selected asset).
The existing classical MIQP solver is intentionally left untouched.
"""

from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd
from gurobipy import Model, GRB, quicksum

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.constraints import (
    BUDGET,
    MIN_WEIGHT,
    MAX_WEIGHT,
    MAX_TECHNOLOGY,
)
from config.settings import DATA_DIR
from config.user_inputs import DEFAULT_USER_INPUTS
from src.data_loader import load_portfolio_data, get_sector_indices, portfolio_dataframe
from src.objective_functions import evaluate_portfolio


HYBRID_RESULT_FILE = DATA_DIR / "Hybrid_Result.xlsx"


def solve_hybrid(selected, user_preferences=None, save=True):
    """
    Fix the asset selection returned by CVaR-QAOA and optimize only weights.
    """

    if user_preferences is None:
        user_preferences = DEFAULT_USER_INPUTS.copy()

    portfolio_data = load_portfolio_data()
    N = portfolio_data["N"]

    selected = np.asarray(selected, dtype=int)

    if len(selected) != N:
        raise ValueError(
            f"Selection vector has length {len(selected)}; expected {N}."
        )

    if selected.sum() != int(selected.sum()):
        raise ValueError("Invalid binary selection vector.")

    mu = portfolio_data["mu"]
    Sigma = portfolio_data["Sigma"]
    dividend = portfolio_data["yield"]
    drawdown = portfolio_data["drawdown"]
    cost = portfolio_data["cost"]

    alpha = user_preferences["alpha"]
    beta = user_preferences["beta"]
    lambda_ = user_preferences["lambda"]
    gamma = user_preferences["gamma"]
    delta = user_preferences["delta"]

    model = Model("HybridWeightRefinement")
    model.Params.OutputFlag = 0

    w = model.addVars(
        N,
        lb=0.0,
        ub=1.0,
        vtype=GRB.CONTINUOUS,
        name="Weight",
    )

    # Continuous financial objective only.
    return_term = quicksum(mu[i] * w[i] for i in range(N))
    income_term = quicksum(dividend[i] * w[i] for i in range(N))
    drawdown_term = quicksum(drawdown[i] * w[i] for i in range(N))
    cost_term = quicksum(cost[i] * w[i] for i in range(N))

    risk_term = quicksum(
        Sigma[i, j] * w[i] * w[j]
        for i in range(N)
        for j in range(N)
    )

    objective = (
        alpha * return_term
        + beta * income_term
        - lambda_ * risk_term
        - gamma * drawdown_term
        - delta * cost_term
    )

    model.setObjective(objective, GRB.MAXIMIZE)

    # Budget.
    model.addConstr(
        quicksum(w[i] for i in range(N)) == BUDGET,
        name="Budget",
    )

    # Quantum-selected assets are fixed; only their weights are optimized.
    for i in range(N):
        if selected[i] == 1:
            model.addConstr(w[i] >= MIN_WEIGHT, name=f"MinWeight_{i}")
            model.addConstr(w[i] <= MAX_WEIGHT, name=f"MaxWeight_{i}")
        else:
            model.addConstr(w[i] == 0.0, name=f"NotSelected_{i}")

    # Technology exposure.
    sectors = get_sector_indices(portfolio_data["asset_classes"])
    technology = sectors.get("Technology", [])

    if technology:
        model.addConstr(
            quicksum(w[i] for i in technology) <= MAX_TECHNOLOGY,
            name="TechnologyLimit",
        )

    start = time.perf_counter()
    model.optimize()
    runtime = time.perf_counter() - start

    if model.Status != GRB.OPTIMAL:
        raise RuntimeError(
            f"Hybrid Gurobi refinement failed. Status={model.Status}"
        )

    weights = np.array([w[i].X for i in range(N)])
    metrics = evaluate_portfolio(weights, portfolio_data, user_preferences)

    allocation = portfolio_dataframe(weights, portfolio_data)
    allocation["Selected"] = (allocation["Weight"] > 1e-8).astype(int)

    selected_assets = allocation.loc[
        allocation["Selected"] == 1,
        "Ticker",
    ].tolist()

    results = {
        "status": model.Status,
        "objective": float(model.ObjVal),
        "runtime": runtime,
        "x": selected.copy(),
        "weights": weights,
        "selected_assets": selected_assets,
        "allocation": allocation,
        "metrics": metrics,
        "preferences": user_preferences,
    }

    if save:
        save_hybrid_results(results)

    return results


def save_hybrid_results(results):
    """Save final hybrid portfolio to data/Hybrid_Result.xlsx."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(HYBRID_RESULT_FILE, engine="openpyxl") as writer:
        results["allocation"].to_excel(
            writer,
            sheet_name="Allocation",
            index=False,
        )
        pd.DataFrame([results["metrics"]]).to_excel(
            writer,
            sheet_name="Metrics",
            index=False,
        )
        pd.DataFrame({
            "Ticker": results["selected_assets"],
        }).to_excel(
            writer,
            sheet_name="Selected_Assets",
            index=False,
        )

    return HYBRID_RESULT_FILE
