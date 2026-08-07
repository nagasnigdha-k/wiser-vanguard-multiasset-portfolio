"""
objective_functions.py

Common mathematical objective functions used by both
the classical (Gurobi) and quantum (QUBO) optimizers.

Objective
---------

maximize

α μᵀw
+ β yᵀw
- λ wᵀΣw
- γ dᵀw
- δ cᵀw
"""

import numpy as np


# ==========================================================
# Classical (Gurobi) Objective
# ==========================================================

def build_classical_objective(
    model,
    w,
    portfolio_data,
    preferences,
):
    """
    Build the Gurobi quadratic objective.

    Parameters
    ----------
    model : gurobipy.Model

    w : Gurobi continuous variables

    portfolio_data : dict

    preferences : dict
        alpha
        beta
        lambda
        gamma
        delta
    """

    from gurobipy import QuadExpr, quicksum

    mu = portfolio_data["mu"]
    Sigma = portfolio_data["Sigma"]
    dividend = portfolio_data["yield"]
    drawdown = portfolio_data["drawdown"]
    cost = portfolio_data["cost"]

    N = portfolio_data["N"]

    alpha = preferences["alpha"]
    beta = preferences["beta"]
    lambda_ = preferences["lambda"]
    gamma = preferences["gamma"]
    delta = preferences["delta"]

    # ------------------------------------------------------

    return_term = quicksum(

        mu[i] * w[i]

        for i in range(N)

    )

    income_term = quicksum(

        dividend[i] * w[i]

        for i in range(N)

    )

    drawdown_term = quicksum(

        drawdown[i] * w[i]

        for i in range(N)

    )

    transaction_term = quicksum(

        cost[i] * w[i]

        for i in range(N)

    )

    risk_term = QuadExpr()

    for i in range(N):

        for j in range(N):

            risk_term += (

                Sigma[i, j]

                * w[i]

                * w[j]

            )

    objective = (

          alpha * return_term

        + beta * income_term

        - lambda_ * risk_term

        - gamma * drawdown_term

        - delta * transaction_term

    )

    return objective


# ==========================================================
# Evaluate Portfolio
# ==========================================================

def evaluate_portfolio(
    weights,
    portfolio_data,
    preferences,
):
    """
    Evaluate a portfolio after optimization.
    """

    mu = portfolio_data["mu"]
    Sigma = portfolio_data["Sigma"]
    dividend = portfolio_data["yield"]
    drawdown = portfolio_data["drawdown"]
    cost = portfolio_data["cost"]

    alpha = preferences["alpha"]
    beta = preferences["beta"]
    lambda_ = preferences["lambda"]
    gamma = preferences["gamma"]
    delta = preferences["delta"]

    expected_return = float(

        mu @ weights

    )

    income = float(

        dividend @ weights

    )

    risk = float(

        weights.T @ Sigma @ weights

    )

    downside = float(

        drawdown @ weights

    )

    transaction_cost = float(

        cost @ weights

    )

    objective = (

          alpha * expected_return

        + beta * income

        - lambda_ * risk

        - gamma * downside

        - delta * transaction_cost

    )

    return {

        "expected_return": expected_return,

        "income": income,

        "risk": risk,

        "drawdown": downside,

        "transaction_cost": transaction_cost,

        "objective": objective,

    }


# ==========================================================
# Pretty Printing
# ==========================================================

def print_metrics(metrics):

    print("\nPortfolio Metrics")
    print("------------------------------")

    print(
        f"Expected Return : {metrics['expected_return']:.4f}"
    )

    print(
        f"Income          : {metrics['income']:.4f}"
    )

    print(
        f"Risk            : {metrics['risk']:.4f}"
    )

    print(
        f"Drawdown        : {metrics['drawdown']:.4f}"
    )

    print(
        f"TransactionCost : {metrics['transaction_cost']:.6f}"
    )

    print(
        f"Objective Value : {metrics['objective']:.4f}"
    )