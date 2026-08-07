"""
classical_optimizer.py

Classical Multi-Objective Portfolio Optimization
using Gurobi MIQP.

Decision Variables
------------------
w_i : continuous portfolio weights

x_i : binary asset selection

Objective
---------
maximize

α μᵀw+ β yᵀw− λ wᵀΣw− γ dᵀw− δ cᵀw
subject to

Σw = 1
Σx = K
l_i x_i ≤ w_i ≤ u_i x_i

sector exposure constraints
"""
import os
import sys

import time

import numpy as np
import pandas as pd

from gurobipy import (
    Model,
    GRB,
    quicksum,
)

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

from config.settings import Classical_Result_File

from config.user_inputs import DEFAULT_USER_INPUTS

from src.data_loader import (
    load_portfolio_data,
    get_sector_indices,
    portfolio_dataframe,
)

from src.objective_functions import (
    build_classical_objective,
    evaluate_portfolio,
    print_metrics,
)


# ==========================================================
# Classical Solver
# ==========================================================

def solve(user_preferences=None):
    """
    Solve the portfolio optimization problem.

    Parameters
    ----------
    user_preferences : dict

        {
            "alpha":...
            "beta":...
            "lambda":...
            "gamma":...
            "delta":...
        }

    Returns
    -------
    dict
    """

    # ------------------------------------------------------
    # User Preferences
    # ------------------------------------------------------

    if user_preferences is None:

        user_preferences = DEFAULT_USER_INPUTS

    # ------------------------------------------------------
    # Portfolio Data
    # ------------------------------------------------------

    portfolio_data = load_portfolio_data()

    N = portfolio_data["N"]

    sectors = get_sector_indices(

        portfolio_data["asset_classes"]

    )

    # ------------------------------------------------------
    # Model
    # ------------------------------------------------------

    model = Model("PortfolioOptimization")

    model.Params.OutputFlag = 1

    # ------------------------------------------------------
    # Decision Variables
    # ------------------------------------------------------

    w = model.addVars(

        N,

        lb=0,

        ub=1,

        vtype=GRB.CONTINUOUS,

        name="Weight",

    )

    x = model.addVars(

        N,

        vtype=GRB.BINARY,

        name="Selected",

    )

    # ------------------------------------------------------
    # Objective
    # ------------------------------------------------------

    objective = build_classical_objective(

        model,

        w,

        portfolio_data,

        user_preferences,

    )

    model.setObjective(

        objective,

        GRB.MAXIMIZE,

    )

    # ======================================================
    # Constraints
    # ======================================================

    #
    # Budget
    #

    model.addConstr(

        quicksum(

            w[i]

            for i in range(N)

        )

        ==

        BUDGET,

        name="Budget",

    )

    #
    # Cardinality
    #

    model.addConstr(

        quicksum(

            x[i]

            for i in range(N)

        )

        ==

        MAX_ASSETS,

        name="Cardinality",

    )

    #
    # Linking
    #

    for i in range(N):

        #
        # Minimum allocation
        #

        model.addConstr(

            w[i]

            >=

            MIN_WEIGHT * x[i],

            name=f"MinWeight_{i}",

        )

        #
        # Maximum allocation
        #

        model.addConstr(

            w[i]

            <=

            MAX_WEIGHT * x[i],

            name=f"MaxWeight_{i}",

        )

    #
    # Technology Exposure
    #

    if "Technology" in sectors:

        model.addConstr(

            quicksum(

                w[i]

                for i in sectors["Technology"]

            )

            <=

            MAX_TECHNOLOGY,

            name="TechnologyLimit",

        )

    # ------------------------------------------------------
    # Optimize
    # ------------------------------------------------------

    start = time.perf_counter()

    model.optimize()

    runtime = time.perf_counter() - start

        # ======================================================
    # Solution Status
    # ======================================================

    if model.Status != GRB.OPTIMAL:

        raise RuntimeError(
            f"Gurobi failed to find an optimal solution.\n"
            f"Solver Status = {model.Status}"
        )

    # ------------------------------------------------------
    # Extract Solution
    # ------------------------------------------------------

    weights = np.array(

        [w[i].X for i in range(N)]

    )

    selected = np.array(

        [int(round(x[i].X)) for i in range(N)]

    )

    # ------------------------------------------------------
    # Portfolio Metrics
    # ------------------------------------------------------

    metrics = evaluate_portfolio(

        weights,

        portfolio_data,

        user_preferences,

    )

    # ------------------------------------------------------
    # Portfolio DataFrame
    # ------------------------------------------------------

    allocation = portfolio_dataframe(

        weights,

        portfolio_data,

    )

    allocation["Selected"] = (

        allocation["Weight"] > 1e-8

    ).astype(int)

    # ------------------------------------------------------
    # Selected Assets
    # ------------------------------------------------------

    selected_assets = allocation.loc[
        allocation["Selected"] == 1,
        "Ticker"
    ].tolist()

    # ------------------------------------------------------
    # Build Result Dictionary
    # ------------------------------------------------------

    results = {

        "status":
            model.Status,

        "objective":
            float(model.ObjVal),

        "runtime":
            runtime,

        "weights":
            weights,

        "selected":
            selected,

        "selected_assets":
            selected_assets,

        "allocation":
            allocation,

        "metrics":
            metrics,

        "preferences":
            user_preferences,

    }

    return results


# ==========================================================
# Pretty Printing
# ==========================================================

def print_solution(results):

    print("\n")
    print("=" * 70)
    print(" Classical Portfolio Optimization ")
    print("=" * 70)

    print()

    print(results["allocation"])

    print()

    print_metrics(results["metrics"])

    print()

    print(f"Solver Runtime : {results['runtime']:.4f} sec")

    print(f"Objective      : {results['objective']:.6f}")

    print()

    print("Selected Assets")

    for ticker in results["selected_assets"]:

        print(f"   • {ticker}")

    print("=" * 70)


# ==========================================================
# Save Results
# ==========================================================

def save_results(results):

    os.makedirs(
            os.path.dirname(Classical_Result_File),
            exist_ok=True,
        )

    with pd.ExcelWriter(
        Classical_Result_File,
        engine="openpyxl",
    ) as writer:

        results["allocation"].to_excel(
            writer,
            sheet_name="Allocation",
            index=False,
        )

        pd.DataFrame(
            [results["metrics"]]
        ).to_excel(
            writer,
            sheet_name="Metrics",
            index=False,
        )

    print(f"\nSaved to {Classical_Result_File}")


# ==========================================================
# Main
# ==========================================================

def main():

    results = solve()

    print_solution(results)

    save_results(results)


if __name__ == "__main__":

    main()