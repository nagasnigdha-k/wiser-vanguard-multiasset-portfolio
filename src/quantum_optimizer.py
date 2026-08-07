"""
quantum_optimizer.py

Hybrid CVaR-QAOA portfolio optimizer for the existing WISER/Vanguard
multi-asset project.

Implements the formulation in the project methodology:
    F_Q(x) = Q(x) + L(x) + C0

with inequality constraints deliberately excluded from the quantum
Hamiltonian.  For CVaR evaluation, the complete sampled objective is

    F(x) = E_H(x) + P_ineq(x)

and Powell optimizes the QAOA variational parameters.

The simulator below is a dependency-light statevector implementation of
QAOA.  It can later be replaced by a Qiskit/Aer backend without changing the
QUBO/Ising/CVaR interfaces.
"""

from __future__ import annotations

import os
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.constraints import (
    BUDGET,
    MAX_ASSETS,
    MIN_WEIGHT,
    MAX_WEIGHT,
    MAX_TECHNOLOGY,
)
from config.user_inputs import DEFAULT_USER_INPUTS
from src.data_loader import load_portfolio_data, get_sector_indices
from src.objective_functions import evaluate_portfolio
from config.settings import Quantum_Result_File
import pandas as pd


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class QAOAResult:
    bitstring: str
    weights: np.ndarray
    metrics: Dict[str, float]
    selected_assets: List[str]
    cvar: float
    gamma: np.ndarray
    beta: np.ndarray
    counts: Dict[str, int]
    runtime_seconds: float
    feasible: bool


# ---------------------------------------------------------------------------
# QUBO / Ising construction
# ---------------------------------------------------------------------------

def build_qubo_coefficients(portfolio_data, preferences, eta2=None, K=None):
    """Build q_i, q_ij and C0 exactly from the supplied formulation."""
    if K is None:
        K = MAX_ASSETS

    if eta2 is None:
        # A moderate default; expose it as a function argument so experiments
        # can tune the cardinality penalty without changing the code.
        eta2 = float(os.getenv("QAOA_ETA2", "100.0"))

    mu = np.asarray(portfolio_data["mu"], dtype=float)
    sigma = np.asarray(portfolio_data["Sigma"], dtype=float)
    dividend = np.asarray(portfolio_data["yield"], dtype=float)
    drawdown = np.asarray(portfolio_data["drawdown"], dtype=float)
    cost = np.asarray(portfolio_data["cost"], dtype=float)

    alpha = float(preferences["alpha"])
    beta = float(preferences["beta"])
    lambda_ = float(preferences["lambda"])
    gamma = float(preferences["gamma"])
    delta = float(preferences["delta"])

    n = len(mu)
    q_linear = (
        -alpha * mu / K
        -beta * dividend / K
        +lambda_ * np.diag(sigma) / (K**2)
        +gamma * drawdown / K
        +delta * cost / K
        +eta2 * (1.0 - 2.0 * K)
    )

    q_pair = np.zeros((n, n), dtype=float)
    for i in range(n):
        for j in range(i + 1, n):
            q_pair[i, j] = (
                2.0 * lambda_ * sigma[i, j] / (K**2)
                + 2.0 * eta2
            )
            q_pair[j, i] = q_pair[i, j]

    constant = eta2 * (K**2)

    Q = np.diag(q_linear.copy())
    for i in range(n):
        for j in range(i + 1, n):
            Q[i, j] = q_pair[i, j] / 2.0
            Q[j, i] = q_pair[i, j] / 2.0

    return Q, q_linear, q_pair, constant, eta2


def qubo_to_ising(q_linear, q_pair, constant):
    """Map x=(1-z)/2 to C + sum h_i z_i + sum J_ij z_i z_j."""
    n = len(q_linear)
    h = -0.5 * q_linear.copy()
    J = np.zeros((n, n), dtype=float)

    for i in range(n):
        for j in range(i + 1, n):
            Jij = q_pair[i, j] / 4.0
            J[i, j] = Jij
            J[j, i] = Jij
            h[i] -= q_pair[i, j] / 4.0
            h[j] -= q_pair[i, j] / 4.0

    c_ising = (
        constant
        + 0.25 * np.sum(q_pair[np.triu_indices(n, 1)])
        + 0.5 * np.sum(q_linear)
    )

    return h, J, c_ising


# ---------------------------------------------------------------------------
# Bitstrings and energies
# ---------------------------------------------------------------------------

def bitstring_to_x(bitstring: str) -> np.ndarray:
    return np.fromiter((int(b) for b in bitstring), dtype=int)


def x_to_bitstring(x: Sequence[int]) -> str:
    return "".join(str(int(v)) for v in x)


def qubo_energy(x, Q, constant=0.0):
    """Evaluate x^T Q x + constant."""
    x = np.asarray(x, dtype=float)
    return float(x @ Q @ x + constant)


def ising_energy_from_bitstring(bitstring, h, J, constant=0.0):
    x = bitstring_to_x(bitstring)
    z = 1.0 - 2.0 * x
    return float(constant + h @ z + 0.5 * z @ J @ z)


# ---------------------------------------------------------------------------
# Classical inequality penalty / feasibility
# ---------------------------------------------------------------------------

def constraint_report(x, portfolio_data):
    """Evaluate binary-selection constraints without adding them to H_C."""
    x = np.asarray(x, dtype=int)
    sectors = get_sector_indices(portfolio_data["asset_classes"])

    cardinality = int(np.sum(x))
    violations = {}

    if cardinality != MAX_ASSETS:
        violations["cardinality"] = abs(cardinality - MAX_ASSETS)

    if "Technology" in sectors:
        tech_selected = int(np.sum(x[sectors["Technology"]]))
        # Selection-level screen only. Continuous weights are checked later.
        if tech_selected > 0:
            violations.setdefault("technology_selection", 0.0)

    return {
        "cardinality": cardinality,
        "violations": violations,
    }


def inequality_penalty(x, portfolio_data, penalty_scale=1000.0):
    """Evaluate bitstring-level inequality penalties when they are defined.

    The submitted formulation explicitly puts the cardinality equality in
    F_Q/H_C and keeps inequality penalties outside the Hamiltonian.  The
    current repository's Technology constraint is a *continuous-weight*
    constraint, so it cannot be evaluated from x alone without inventing an
    additional surrogate.  Therefore the bitstring-stage penalty is zero and
    the actual hard constraints are enforced after continuous weight
    optimization in ``final_feasibility``.

    ``penalty_scale`` is retained for API compatibility with future
    selection-level inequality penalties.
    """
    return 0.0


# ---------------------------------------------------------------------------
# Continuous weight optimization for a selected subset
# ---------------------------------------------------------------------------

def optimize_weights_for_selection(
    bitstring: str,
    portfolio_data,
    preferences,
):
    """Optimize continuous weights for a fixed binary selection.

    SLSQP is used here because it handles the exact budget and bound
    constraints directly. Powell is reserved for the QAOA variational
    parameters, where it is the requested outer optimizer.
    """
    x = bitstring_to_x(bitstring)
    n = len(x)
    selected = np.where(x == 1)[0]

    if len(selected) != MAX_ASSETS:
        return None

    mu = portfolio_data["mu"]
    Sigma = portfolio_data["Sigma"]
    dividend = portfolio_data["yield"]
    drawdown = portfolio_data["drawdown"]
    cost = portfolio_data["cost"]

    alpha = float(preferences["alpha"])
    beta = float(preferences["beta"])
    lambda_ = float(preferences["lambda"])
    gamma = float(preferences["gamma"])
    delta = float(preferences["delta"])

    def objective(w_sel):
        w = np.zeros(n)
        w[selected] = w_sel
        return -(
            alpha * (mu @ w)
            + beta * (dividend @ w)
            - lambda_ * (w @ Sigma @ w)
            - gamma * (drawdown @ w)
            - delta * (cost @ w)
        )

    def tech_exposure(w_sel):
        w = np.zeros(n)
        w[selected] = w_sel
        tech = [i for i, a in enumerate(portfolio_data["asset_classes"])
                if a == "Technology"]
        return MAX_TECHNOLOGY - np.sum(w[tech])

    m = len(selected)
    initial = np.full(m, BUDGET / m)

    constraints = [
        {"type": "eq", "fun": lambda w: np.sum(w) - BUDGET},
    ]

    groups = np.asarray(portfolio_data.get("groups", [""] * n))
    tech_selected = selected[groups[selected] == "Technology"]
    if len(tech_selected) > 0:
        tech_positions = [
            pos for pos, idx in enumerate(selected)
            if groups[idx] == "Technology"
        ]
        constraints.append({
            "type": "ineq",
            "fun": lambda w, pos=tech_positions: (
                MAX_TECHNOLOGY - np.sum(w[pos])
            ),
        })

    result = minimize(
        objective,
        initial,
        method="SLSQP",
        bounds=[(MIN_WEIGHT, MAX_WEIGHT)] * m,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )

    if not result.success:
        return None

    weights = np.zeros(n)
    weights[selected] = result.x

    return weights


def final_feasibility(weights, portfolio_data, tolerance=1e-7):
    """Check the hard portfolio constraints on continuous weights."""
    weights = np.asarray(weights, dtype=float)
    selected = weights > tolerance

    breaches = {}

    if abs(float(np.sum(weights)) - BUDGET) > 1e-5:
        breaches["budget"] = float(np.sum(weights) - BUDGET)

    if int(np.sum(selected)) != MAX_ASSETS:
        breaches["cardinality"] = int(np.sum(selected)) - MAX_ASSETS

    active = weights[selected]
    if np.any(active < MIN_WEIGHT - tolerance):
        breaches["minimum_weight"] = float(np.min(active))
    if np.any(active > MAX_WEIGHT + tolerance):
        breaches["maximum_weight"] = float(np.max(active))

    # Existing project stores broad asset class, not group, in portfolio_data.
    # Therefore technology exposure is only checked if the loader/data provides
    # an explicit `groups` array.
    groups = portfolio_data.get("groups")
    if groups is not None:
        tech = np.array(groups) == "Technology"
        tech_weight = float(np.sum(weights[tech]))
        if tech_weight > MAX_TECHNOLOGY + tolerance:
            breaches["technology"] = tech_weight - MAX_TECHNOLOGY

    return len(breaches) == 0, breaches


# ---------------------------------------------------------------------------
# QAOA statevector simulator
# ---------------------------------------------------------------------------

def _apply_mixer_layer(state, beta, n):
    """Apply exp(-i beta sum X_i) using tensor-product Rx-like rotations."""
    state = state.reshape([2] * n)
    c = np.cos(beta)
    s = -1j * np.sin(beta)

    # Matrix [[c,s],[s,c]] on each qubit.  Axis ordering is immaterial as long
    # as it is used consistently with computational basis indexing.
    for axis in range(n):
        state = np.moveaxis(state, axis, 0)
        shape = state.shape
        flat = state.reshape(2, -1)
        a = flat[0].copy()
        b = flat[1].copy()
        flat[0] = c * a + s * b
        flat[1] = s * a + c * b
        state = flat.reshape(shape)
        state = np.moveaxis(state, 0, axis)

    return state.reshape(-1)


class QAOASimulator:
    def __init__(self, h, J, n, p=1, shots=1024, seed=42):
        self.h = np.asarray(h, dtype=float)
        self.J = np.asarray(J, dtype=float)
        self.n = int(n)
        self.p = int(p)
        self.shots = int(shots)
        self.rng = np.random.default_rng(seed)

        self._states = np.arange(2**self.n, dtype=np.uint32)
        bits = ((self._states[:, None] >> np.arange(self.n - 1, -1, -1)) & 1)
        self._x = bits.astype(np.int8)
        self._z = 1 - 2 * self._x

        self._energies = (
            self._z @ self.h
            + 0.5 * np.einsum("bi,ij,bj->b", self._z, self.J, self._z)
        )

    @property
    def energies(self):
        return self._energies

    def state(self, params):
        params = np.asarray(params, dtype=float)
        gammas = params[:self.p]
        betas = params[self.p:]

        dim = 2**self.n
        psi = np.ones(dim, dtype=complex) / np.sqrt(dim)

        for layer in range(self.p):
            psi *= np.exp(-1j * gammas[layer] * self._energies)
            psi = _apply_mixer_layer(psi, betas[layer], self.n)

        return psi

    def sample(self, params, shots=None):
        if shots is None:
            shots = self.shots
        psi = self.state(params)
        probs = np.abs(psi)**2
        probs = probs / probs.sum()
        idx = self.rng.choice(len(probs), size=shots, p=probs)
        bitstrings = [format(int(i), f"0{self.n}b") for i in idx]
        return bitstrings, probs


# ---------------------------------------------------------------------------
# CVaR
# ---------------------------------------------------------------------------

def calculate_cvar(costs: Sequence[float], tau: float) -> float:
    costs = np.sort(np.asarray(costs, dtype=float))
    if len(costs) == 0:
        return float("inf")
    m_tau = max(1, int(np.ceil(float(tau) * len(costs))))
    return float(np.mean(costs[:m_tau]))


# ---------------------------------------------------------------------------
# Main solver
# ---------------------------------------------------------------------------

def solve_quantum(
    user_preferences=None,
    p=1,
    tau=0.10,
    shots=256,
    final_shots=2048,
    maxiter=30,
    eta2=None,
    seed=42,
):
    """Run the hybrid CVaR-QAOA + Powell workflow."""
    if user_preferences is None:
        user_preferences = DEFAULT_USER_INPUTS.copy()

    portfolio_data = load_portfolio_data()
    n = portfolio_data["N"]

    if n > 22:
        raise ValueError(
            f"Statevector simulator received N={n}. "
            """For larger N, use a Qiskit/Aer or hardware backend instead."""
        )

    Q, q_linear, q_pair, constant, eta2 = build_qubo_coefficients(
        portfolio_data,
        user_preferences,
        eta2=eta2,
        K=MAX_ASSETS,
    )

    h, J, c_ising = qubo_to_ising(q_linear, q_pair, constant)

    simulator = QAOASimulator(
        h=h,
        J=J,
        n=n,
        p=p,
        shots=shots,
        seed=seed,
    )

    # Objective used by Powell.  It evaluates the complete sampled objective
    # E_H + P_ineq, following the submitted methodology.
    def objective(params):
        samples, _ = simulator.sample(params, shots=shots)
        costs = []
        for bitstring in samples:
            x = bitstring_to_x(bitstring)
            e_h = ising_energy_from_bitstring(
                bitstring, h, J, c_ising
            )
            penalty = inequality_penalty(x, portfolio_data)
            costs.append(e_h + penalty)
        return calculate_cvar(costs, tau)

    rng = np.random.default_rng(seed)
    initial = np.concatenate([
        rng.uniform(0.0, np.pi, p),
        rng.uniform(0.0, np.pi / 2.0, p),
    ])

    start = time.perf_counter()

    result = minimize(
        objective,
        initial,
        method="Powell",
        bounds=[(0.0, 2.0 * np.pi)] * p
        + [(0.0, np.pi)] * p,
        options={
            "maxiter": maxiter,
            "xtol": 1e-3,
            "ftol": 1e-3,
            "disp": True,
        },
    )

    runtime = time.perf_counter() - start

    # Final sampling with optimized parameters.
    final_samples, _ = simulator.sample(
        result.x,
        shots=final_shots,
    )
    counts = dict(Counter(final_samples))

    # Rank by complete classical objective.  We first keep candidates with the
    # desired cardinality, then optimize continuous weights and check hard
    # constraints.
    ranked = []
    for bitstring, count in counts.items():
        x = bitstring_to_x(bitstring)
        e_h = ising_energy_from_bitstring(bitstring, h, J, c_ising)
        penalty = inequality_penalty(x, portfolio_data)
        ranked.append((e_h + penalty, e_h, penalty, count, bitstring))

    ranked.sort(key=lambda r: r[0])

    best = None
    candidate_results = []

    for total_cost, e_h, penalty, count, bitstring in ranked:
        weights = optimize_weights_for_selection(
            bitstring,
            portfolio_data,
            user_preferences,
        )
        if weights is None:
            continue

        feasible, breaches = final_feasibility(
            weights,
            portfolio_data,
        )

        metrics = evaluate_portfolio(
            weights,
            portfolio_data,
            user_preferences,
        )
        metrics["constraint_breaches"] = len(breaches)
        metrics["hamiltonian_energy"] = e_h
        metrics["total_sample_cost"] = total_cost
        metrics["measurement_probability"] = count / final_shots

        candidate_results.append({
            "bitstring": bitstring,
            "weights": weights,
            "metrics": metrics,
            "feasible": feasible,
            "breaches": breaches,
        })

        if feasible:
            best = candidate_results[-1]
            break

    if best is None:
        raise RuntimeError(
            "QAOA produced no feasible candidate after classical weight "
            "optimization. Increase shots/maxiter or adjust eta2/tau."
        )

    x_best = bitstring_to_x(best["bitstring"])
    selected_assets = [
        portfolio_data["tickers"][i]
        for i in np.where(x_best == 1)[0]
    ]

    final_cvar = calculate_cvar(
        [
            ising_energy_from_bitstring(s, h, J, c_ising)
            + inequality_penalty(bitstring_to_x(s), portfolio_data)
            for s in final_samples
        ],
        tau,
    )

    return QAOAResult(
        bitstring=best["bitstring"],
        weights=best["weights"],
        metrics=best["metrics"],
        selected_assets=selected_assets,
        cvar=final_cvar,
        gamma=result.x[:p],
        beta=result.x[p:],
        counts=counts,
        runtime_seconds=runtime,
        feasible=best["feasible"],
    )



def save_results(result: QAOAResult, portfolio_data=None):
    """Save the optimized quantum portfolio to Excel."""
    if portfolio_data is None:
        portfolio_data = load_portfolio_data()

    allocation = pd.DataFrame({
        "Ticker": portfolio_data["tickers"],
        "AssetClass": portfolio_data["asset_classes"],
        "Group": portfolio_data.get("groups", [""] * len(result.weights)),
        "Weight": result.weights,
        "Selected": (result.weights > 1e-8).astype(int),
    })
    allocation = allocation[allocation["Selected"] == 1].copy()
    allocation.sort_values("Weight", ascending=False, inplace=True)

    metrics = dict(result.metrics)
    metrics.update({
        "CVaR": result.cvar,
        "QAOA_Runtime": result.runtime_seconds,
        "Feasible": result.feasible,
        "Bitstring": result.bitstring,
        "SelectedAssets": ", ".join(result.selected_assets),
        "Gamma": ", ".join(f"{v:.8f}" for v in result.gamma),
        "Beta": ", ".join(f"{v:.8f}" for v in result.beta),
    })

    counts = pd.DataFrame(
        sorted(result.counts.items(), key=lambda kv: kv[1], reverse=True),
        columns=["Bitstring", "Count"],
    )
    counts["Probability"] = counts["Count"] / counts["Count"].sum()

    os.makedirs(os.path.dirname(Quantum_Result_File), exist_ok=True)
    with pd.ExcelWriter(Quantum_Result_File, engine="openpyxl") as writer:
        allocation.to_excel(writer, sheet_name="Allocation", index=False)
        pd.DataFrame([metrics]).to_excel(writer, sheet_name="Metrics", index=False)
        counts.to_excel(writer, sheet_name="QAOA_Samples", index=False)

    return Quantum_Result_File

# Backward-compatible alias expected by run.py.
solve = solve_quantum


if __name__ == "__main__":
    result = solve_quantum()
    print("\n==============================")
    print("CVaR-QAOA RESULT")
    print("==============================")
    print("Bitstring       :", result.bitstring)
    print("Selected assets :", result.selected_assets)
    print("CVaR            :", result.cvar)
    print("Gamma           :", result.gamma)
    print("Beta            :", result.beta)
    print("Feasible        :", result.feasible)
    print("Runtime (s)     :", result.runtime_seconds)
    print("\nWeights:")
    for ticker, weight in zip(
        load_portfolio_data()["tickers"], result.weights
    ):
        if weight > 1e-8:
            print(f"  {ticker:8s} {weight:.6f}")
