"""Streamlit portfolio co-pilot.

Left: tunable investment goals.
Right top: classical MIQP portfolio.
Right bottom: CVaR-QAOA asset selection + classical weight refinement.
"""

import streamlit as st
import pandas as pd

from config.user_inputs import DEFAULT_USER_INPUTS
from src.classical_optimizer import solve as solve_classical
from src.quantum_optimizer import solve_quantum
from src.hybrid_classical_optimizer import solve_hybrid


st.set_page_config(
    page_title="WISER Portfolio Co-Pilot",
    layout="wide",
)

st.title("WISER Multi-Asset Portfolio Co-Pilot")
st.caption("Classical baseline vs CVaR-QAOA asset selection + classical weight refinement")


# -----------------------------------------------------------------------------
# Left side: tunable goals
# -----------------------------------------------------------------------------

with st.sidebar:
    st.header("Investment Goals")

    growth = st.slider("Growth", 0, 100, int(DEFAULT_USER_INPUTS["alpha"]))
    income = st.slider("Income", 0, 100, int(DEFAULT_USER_INPUTS["beta"]))
    drawdown = st.slider("Drawdown Control", 0, 100, int(DEFAULT_USER_INPUTS["delta"]))
    cost = st.slider("Cost Sensitivity", 0, 100, int(DEFAULT_USER_INPUTS["gamma"]))
    risk = st.slider("Risk Aversion", 0, 20, int(DEFAULT_USER_INPUTS["lambda"]))

    st.divider()
    st.header("CVaR-QAOA")

    cvar_alpha = st.slider(
        "CVaR alpha",
        0.05,
        1.00,
        0.10,
        0.05,
        help="Fraction of the lowest-cost measured outcomes used by CVaR.",
    )

    reps = st.slider("QAOA depth (p)", 1, 4, 2)
    shots = st.select_slider("Shots", options=[256, 512, 1024, 2048], value=1024)

    run = st.button("Run Optimization", type="primary", use_container_width=True)

preferences = {
    "alpha": growth,
    "beta": income,
    "gamma": cost,
    "delta": drawdown,
    "lambda": risk,
}

if run:
    with st.spinner("Running classical baseline..."):
        classical = solve_classical(preferences)

    with st.spinner("Running CVaR-QAOA..."):
        quantum = solve_quantum(
            user_preferences=preferences,
            cvar_alpha=cvar_alpha,
            reps=reps,
            shots=shots,
        )

    with st.spinner("Refining quantum-selected weights with Gurobi..."):
        hybrid = solve_hybrid(
            selected=quantum["x"],
            user_preferences=preferences,
            save=True,
        )

    st.session_state["classical"] = classical
    st.session_state["quantum"] = quantum
    st.session_state["hybrid"] = hybrid


if "classical" not in st.session_state:
    st.info("Set the goals on the left and click **Run Optimization**.")
    st.stop()

classical = st.session_state["classical"]
quantum = st.session_state["quantum"]
hybrid = st.session_state["hybrid"]


# -----------------------------------------------------------------------------
# Right top: classical
# -----------------------------------------------------------------------------

st.header("Classical Solver")

classical_left, classical_right = st.columns([1, 2])

with classical_left:
    st.subheader("Selected Assets")
    st.write(", ".join(classical["selected_assets"]))

    metrics = classical["metrics"]
    c1, c2 = st.columns(2)
    c1.metric("Expected Return", f"{metrics['expected_return']:.4f}")
    c2.metric("Risk", f"{metrics['risk']:.4f}")

    c3, c4 = st.columns(2)
    c3.metric("Income", f"{metrics['income']:.4f}")
    c4.metric("Objective", f"{metrics['objective']:.4f}")

with classical_right:
    st.subheader("Classical Allocation")
    st.dataframe(
        classical["allocation"],
        use_container_width=True,
        hide_index=True,
    )


# -----------------------------------------------------------------------------
# Right bottom: hybrid quantum solver
# -----------------------------------------------------------------------------

st.divider()
st.header("Hybrid Quantum Solver")
st.caption("CVaR-QAOA selects the assets; Gurobi optimizes their final weights.")

hybrid_left, hybrid_right = st.columns([1, 2])

with hybrid_left:
    st.subheader("Selected Assets")
    st.success(", ".join(hybrid["selected_assets"]))

    metrics = hybrid["metrics"]
    c1, c2 = st.columns(2)
    c1.metric("Expected Return", f"{metrics['expected_return']:.4f}")
    c2.metric("Risk", f"{metrics['risk']:.4f}")

    c3, c4 = st.columns(2)
    c3.metric("Income", f"{metrics['income']:.4f}")
    c4.metric("Objective", f"{metrics['objective']:.4f}")

    st.metric("CVaR alpha", f"{quantum['cvar_alpha']:.2f}")

    if quantum["feasible"]:
        st.success("Quantum selection: no hard-constraint breach")
    else:
        st.warning("Quantum selection was infeasible before refinement")

with hybrid_right:
    st.subheader("Final Hybrid Allocation")
    st.dataframe(
        hybrid["allocation"],
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("Goal Settings Used")
st.dataframe(
    pd.DataFrame({
        "Goal": ["Growth", "Income", "Drawdown Control", "Cost Sensitivity", "Risk Aversion"],
        "Value": [growth, income, drawdown, cost, risk],
    }),
    use_container_width=True,
    hide_index=True,
)
