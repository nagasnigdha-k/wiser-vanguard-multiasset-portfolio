"""
portfolio_copilot.py

WISER / Vanguard Multi-Asset Portfolio Co-Pilot.

Workflow:

1. User sets five investment preferences.
2. Generate Portfolio_Data.xlsx.
3. Run classical MIQP optimizer.
4. Run CVaR-QAOA + SLSQP quantum/hybrid optimizer.
5. Check hard constraints.
6. Compare Classical vs Quantum.
7. Display the recommended portfolio.
8. Save Classical_Result.xlsx and Quantum_Result.xlsx.

The separate hybrid_classical_optimizer.py path is intentionally NOT used.
The quantum optimizer already performs SLSQP continuous-weight refinement
after QAOA asset selection.
"""

from pathlib import Path
import sys

import pandas as pd
import streamlit as st


# =============================================================================
# PROJECT PATH
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# =============================================================================
# PROJECT IMPORTS
# =============================================================================

from config.settings import (
    Portfolio_Data_File,
    Classical_Result_File,
    Quantum_Result_File,
)

from src.generate_portfolio_data import main as generate_portfolio_data
from src.data_loader import load_portfolio_data

from src.classical_optimizer import (
    solve as solve_classical,
    save_results as save_classical_results,
)

from src.quantum_optimizer import (
    solve_quantum,
    save_results as save_quantum_results,
)

from src.compare_results import check_constraints


# =============================================================================
# HARD-CODED QUANTUM SETTINGS
# =============================================================================

# These are intentionally NOT exposed to the user.
# The user only controls the five investment preference sliders.

CVAR_ALPHA = 0.30
QAOA_REPS = 4
QAOA_SHOTS = 1024


# =============================================================================
# STREAMLIT CONFIGURATION
# =============================================================================

st.set_page_config(
    page_title="Vanguard-WISER MultiAsset Portfolio Co-Pilot",
    layout="wide",
)

st.title("Vanguard-WISER Multi-Asset Portfolio Co-Pilot")

st.caption(
    "Investment preferences → Classical MIQP vs "
    "CVaR-QAOA + SLSQP → recommended portfolio"
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_pct(value):
    """Format a decimal value as a percentage."""

    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"
    except Exception:
        pass

    return f"{float(value) * 100:.2f}%"


def format_number(value):
    """Format a numeric value."""

    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"
    except Exception:
        pass

    return f"{float(value):.6f}"


def get_metric(metrics, *names):
    """
    Get a metric while supporting possible naming differences.

    Example:
        get_metric(metrics, "Expected Return", "expected_return")
    """

    for name in names:
        if name in metrics:
            return metrics[name]

    return None


# =============================================================================
# QUANTUM RESULT CONVERSION
# =============================================================================

def quantum_to_dict(quantum, portfolio_data):
    """
    Convert the QAOAResult dataclass returned by solve_quantum()
    into the dictionary structure used by this Streamlit application.

    QAOAResult contains:

        bitstring
        weights
        metrics
        selected_assets
        cvar
        gamma
        beta
        counts
        runtime_seconds
        feasible
    """

    allocation = pd.DataFrame(
        {
            "Ticker": portfolio_data["tickers"],
            "AssetClass": portfolio_data["asset_classes"],
            "Group": portfolio_data.get(
                "groups",
                [""] * len(quantum.weights),
            ),
            "Weight": quantum.weights,
        }
    )

    allocation = allocation[
        allocation["Weight"] > 1e-8
    ].copy()

    allocation = allocation.sort_values(
        "Weight",
        ascending=False,
    )

    return {
        "bitstring": quantum.bitstring,
        "weights": quantum.weights,
        "metrics": quantum.metrics,
        "selected_assets": quantum.selected_assets,
        "cvar": quantum.cvar,
        "gamma": quantum.gamma,
        "beta": quantum.beta,
        "counts": quantum.counts,
        "runtime_seconds": quantum.runtime_seconds,
        "feasible": quantum.feasible,
        "allocation": allocation,
    }


# =============================================================================
# CLASSICAL / QUANTUM COMPARISON TABLE
# =============================================================================

def build_comparison_table(
    classical,
    quantum,
    classical_constraints,
    quantum_constraints,
):
    """
    Build the main Classical vs Quantum comparison table.
    """

    classical_metrics = classical["metrics"]
    quantum_metrics = quantum["metrics"]

    classical_assets = classical.get(
        "selected_assets",
        [],
    )

    quantum_assets = quantum.get(
        "selected_assets",
        [],
    )

    rows = [
        {
            "Metric": "Selected Assets",
            "Classical": ", ".join(classical_assets),
            "Quantum": ", ".join(quantum_assets),
        },
        {
            "Metric": "Expected Return",
            "Classical": format_pct(
                get_metric(
                    classical_metrics,
                    "Expected Return",
                    "expected_return",
                )
            ),
            "Quantum": format_pct(
                get_metric(
                    quantum_metrics,
                    "Expected Return",
                    "expected_return",
                )
            ),
        },
        {
            "Metric": "Risk / Volatility",
            "Classical": format_pct(
                get_metric(
                    classical_metrics,
                    "Risk / Volatility",
                    "risk",
                )
            ),
            "Quantum": format_pct(
                get_metric(
                    quantum_metrics,
                    "Risk / Volatility",
                    "risk",
                )
            ),
        },
        {
            "Metric": "Income / Dividend Yield",
            "Classical": format_pct(
                get_metric(
                    classical_metrics,
                    "Income / Dividend Yield",
                    "income",
                )
            ),
            "Quantum": format_pct(
                get_metric(
                    quantum_metrics,
                    "Income / Dividend Yield",
                    "income",
                )
            ),
        },
        {
            "Metric": "Drawdown",
            "Classical": format_pct(
                get_metric(
                    classical_metrics,
                    "Drawdown",
                    "drawdown",
                )
            ),
            "Quantum": format_pct(
                get_metric(
                    quantum_metrics,
                    "Drawdown",
                    "drawdown",
                )
            ),
        },
        {
            "Metric": "Transaction Cost",
            "Classical": format_pct(
                get_metric(
                    classical_metrics,
                    "Transaction Cost",
                    "transaction_cost",
                    "cost",
                )
            ),
            "Quantum": format_pct(
                get_metric(
                    quantum_metrics,
                    "Transaction Cost",
                    "transaction_cost",
                    "cost",
                )
            ),
        },
        {
            "Metric": "Objective / Cost Function",
            "Classical": format_number(
                get_metric(
                    classical_metrics,
                    "Objective / Cost Function",
                    "objective",
                )
            ),
            "Quantum": format_number(
                get_metric(
                    quantum_metrics,
                    "Objective / Cost Function",
                    "objective",
                )
            ),
        },
        {
            "Metric": "Feasible",
            "Classical": (
                "Yes"
                if classical_constraints["feasible"]
                else "No"
            ),
            "Quantum": (
                "Yes"
                if quantum_constraints["feasible"]
                else "No"
            ),
        },
        {
            "Metric": "Hard-Constraint Breaches",
            "Classical": classical_constraints["breach_count"],
            "Quantum": quantum_constraints["breach_count"],
        },
        {
            "Metric": "Selected Asset Count",
            "Classical": classical_constraints["selected_count"],
            "Quantum": quantum_constraints["selected_count"],
        },
        {
            "Metric": "Technology Exposure",
            "Classical": format_pct(
                classical_constraints["technology_weight"]
            ),
            "Quantum": format_pct(
                quantum_constraints["technology_weight"]
            ),
        },
    ]

    return pd.DataFrame(rows)


# =============================================================================
# CONSTRAINT COMPARISON TABLE
# =============================================================================

def build_constraint_table(
    classical_constraints,
    quantum_constraints,
):
    """Build a compact hard-constraint comparison."""

    return pd.DataFrame(
        [
            {
                "Constraint Check": "Feasible",
                "Classical": (
                    "Yes"
                    if classical_constraints["feasible"]
                    else "No"
                ),
                "Quantum": (
                    "Yes"
                    if quantum_constraints["feasible"]
                    else "No"
                ),
            },
            {
                "Constraint Check": "Hard-constraint breaches",
                "Classical": classical_constraints["breach_count"],
                "Quantum": quantum_constraints["breach_count"],
            },
            {
                "Constraint Check": "Selected assets",
                "Classical": classical_constraints["selected_count"],
                "Quantum": quantum_constraints["selected_count"],
            },
            {
                "Constraint Check": "Technology exposure",
                "Classical": format_pct(
                    classical_constraints["technology_weight"]
                ),
                "Quantum": format_pct(
                    quantum_constraints["technology_weight"]
                ),
            },
        ]
    )


# =============================================================================
# RECOMMENDATION LOGIC
# =============================================================================

def choose_recommendation(
    classical,
    quantum,
    classical_constraints,
    quantum_constraints,
):
    """
    Recommendation priority:

    1. Zero hard-constraint breaches
    2. Better preference-weighted objective
    3. Lower risk
    4. Higher return
    5. Lower transaction cost
    """

    c_feasible = classical_constraints["feasible"]
    q_feasible = quantum_constraints["feasible"]

    # -----------------------------------------------------------------
    # Hard constraints have absolute priority.
    # -----------------------------------------------------------------

    if q_feasible and not c_feasible:
        return (
            "Quantum",
            "Quantum is recommended because it satisfies all "
            "hard constraints while the classical solution has "
            "a hard-constraint breach.",
        )

    if c_feasible and not q_feasible:
        return (
            "Classical",
            "Classical is recommended because it satisfies all "
            "hard constraints while the quantum solution has "
            "a hard-constraint breach.",
        )

    if not c_feasible and not q_feasible:
        return (
            "None",
            "Neither portfolio is recommended because both "
            "have hard-constraint breaches.",
        )

    # -----------------------------------------------------------------
    # Both feasible.
    # -----------------------------------------------------------------

    c_metrics = classical["metrics"]
    q_metrics = quantum["metrics"]

    c_risk = float(
        get_metric(
            c_metrics,
            "Risk / Volatility",
            "risk",
        )
    )

    q_risk = float(
        get_metric(
            q_metrics,
            "Risk / Volatility",
            "risk",
        )
    )

    c_return = float(
        get_metric(
            c_metrics,
            "Expected Return",
            "expected_return",
        )
    )

    q_return = float(
        get_metric(
            q_metrics,
            "Expected Return",
            "expected_return",
        )
    )

    c_objective = float(
        get_metric(
            c_metrics,
            "Objective / Cost Function",
            "objective",
        )
    )

    q_objective = float(
        get_metric(
            q_metrics,
            "Objective / Cost Function",
            "objective",
        )
    )

    c_cost = float(
        get_metric(
            c_metrics,
            "Transaction Cost",
            "transaction_cost",
            "cost",
        )
    )

    q_cost = float(
        get_metric(
            q_metrics,
            "Transaction Cost",
            "transaction_cost",
            "cost",
        )
    )

    # -----------------------------------------------------------------
    # Primary comparison: objective.
    # -----------------------------------------------------------------

    if q_objective > c_objective + 1e-10:
        return (
            "Quantum",
            "Both portfolios are feasible. Quantum has the "
            "higher preference-weighted objective.",
        )

    if c_objective > q_objective + 1e-10:
        return (
            "Classical",
            "Both portfolios are feasible. Classical has the "
            "higher preference-weighted objective.",
        )

    # -----------------------------------------------------------------
    # Tie-break 1: lower risk.
    # -----------------------------------------------------------------

    if q_risk < c_risk - 1e-10:
        return (
            "Quantum",
            "Both portfolios are feasible with similar objective "
            "values. Quantum has lower risk.",
        )

    if c_risk < q_risk - 1e-10:
        return (
            "Classical",
            "Both portfolios are feasible with similar objective "
            "values. Classical has lower risk.",
        )

    # -----------------------------------------------------------------
    # Tie-break 2: higher return.
    # -----------------------------------------------------------------

    if q_return > c_return + 1e-10:
        return (
            "Quantum",
            "Both portfolios are feasible with similar objective "
            "and risk. Quantum has higher expected return.",
        )

    if c_return > q_return + 1e-10:
        return (
            "Classical",
            "Both portfolios are feasible with similar objective "
            "and risk. Classical has higher expected return.",
        )

    # -----------------------------------------------------------------
    # Tie-break 3: lower cost.
    # -----------------------------------------------------------------

    if q_cost < c_cost - 1e-10:
        return (
            "Quantum",
            "The portfolios are effectively tied on the main "
            "metrics. Quantum has lower transaction cost.",
        )

    return (
        "Classical",
        "The portfolios are effectively tied on the main "
        "metrics. Classical is selected as the default tie-break.",
    )


# =============================================================================
# SAVE RESULTS
# =============================================================================

def save_pipeline_results(
    classical,
    quantum,
    portfolio_data,
):
    """Save both optimizer results."""

    save_classical_results(classical)

    save_quantum_results(
        quantum_result_object,
        portfolio_data=portfolio_data,
    )


# =============================================================================
# RUN COMPLETE OPTIMIZATION PIPELINE
# =============================================================================

def run_pipeline(
    preferences,
    regenerate_data,
):
    """
    Execute the complete portfolio workflow.

    Step 1: Generate data
    Step 2: Classical MIQP
    Step 3: CVaR-QAOA + SLSQP
    Step 4: Save results
    """

    # -----------------------------------------------------------------
    # STEP 1 — DATA GENERATION
    # -----------------------------------------------------------------

    with st.spinner("Step 1/4 — Generating portfolio data..."):

        if regenerate_data:
            generate_portfolio_data()

        if not Portfolio_Data_File.exists():
            raise FileNotFoundError(
                f"Portfolio data file not found: "
                f"{Portfolio_Data_File}"
            )

        portfolio_data = load_portfolio_data()

    # -----------------------------------------------------------------
    # STEP 2 — CLASSICAL MIQP
    # -----------------------------------------------------------------

    with st.spinner(
        "Step 2/4 — Running Classical MIQP optimization..."
    ):

        classical = solve_classical(
            user_preferences=preferences
        )

    # -----------------------------------------------------------------
    # STEP 3 — CVaR-QAOA + SLSQP
    # -----------------------------------------------------------------

    with st.spinner(
        "Step 3/4 — Running CVaR-QAOA + SLSQP optimization..."
    ):

        quantum_result_object = solve_quantum(
            user_preferences=preferences,
            p=QAOA_REPS,
            tau=CVAR_ALPHA,
            shots=QAOA_SHOTS,
        )

    # Convert QAOAResult → dictionary for the UI.
    quantum = quantum_to_dict(
        quantum_result_object,
        portfolio_data,
    )

    # -----------------------------------------------------------------
    # STEP 4 — SAVE RESULTS
    # -----------------------------------------------------------------

    with st.spinner("Step 4/4 — Saving optimization results..."):

        save_classical_results(classical)

        save_quantum_results(
            quantum_result_object,
            portfolio_data=portfolio_data,
        )

    return (
        portfolio_data,
        classical,
        quantum,
    )


# =============================================================================
# SIDEBAR — FIVE USER SLIDERS ONLY
# =============================================================================

with st.sidebar:

    st.header("Investment Goals")

    growth = st.slider(
        "Growth",
        min_value=0,
        max_value=100,
        value=25,
        help="Preference for expected portfolio growth.",
    )

    income = st.slider(
        "Income",
        min_value=0,
        max_value=100,
        value=25,
        help="Preference for dividend/income generation.",
    )

    drawdown = st.slider(
        "Drawdown Control",
        min_value=0,
        max_value=100,
        value=20,
        help="Preference for controlling drawdown.",
    )

    cost = st.slider(
        "Cost Sensitivity",
        min_value=0,
        max_value=100,
        value=15,
        help="Penalty assigned to transaction/portfolio costs.",
    )

    risk = st.slider(
        "Risk Aversion",
        min_value=0,
        max_value=20,
        value=10,
        help="Penalty assigned to portfolio variance.",
    )

    st.divider()

    st.caption(
        "QAOA depth, CVaR alpha and shots are fixed "
        "in the code and are not user inputs."
    )

    regenerate_data = st.checkbox(
        "Regenerate Portfolio_Data.xlsx",
        value=True,
        help=(
            "Enable this to generate a fresh synthetic/anonymized "
            "portfolio dataset before optimization."
        ),
    )

    start_optimization = st.button(
        "Start Optimization",
        type="primary",
        use_container_width=True,
    )


# =============================================================================
# BUILD USER PREFERENCES
# =============================================================================

preferences = {
    "alpha": growth,
    "beta": income,
    "gamma": cost,
    "delta": drawdown,
    "lambda": risk,
}


# =============================================================================
# RUN PIPELINE
# =============================================================================

if start_optimization:

    try:

        (
            portfolio_data,
            classical,
            quantum,
        ) = run_pipeline(
            preferences=preferences,
            regenerate_data=regenerate_data,
        )

        # Save everything in Streamlit session state.
        st.session_state["portfolio_data"] = portfolio_data
        st.session_state["classical"] = classical
        st.session_state["quantum"] = quantum
        st.session_state["preferences"] = preferences.copy()

        st.success(
            "Optimization completed successfully."
        )

    except Exception as exc:

        st.error(
            "Optimization pipeline failed."
        )

        st.exception(exc)

        st.stop()


# =============================================================================
# NO RESULT YET
# =============================================================================

if "classical" not in st.session_state:

    st.info(
        "Set the five investment goals on the left and click "
        "**Start Optimization**."
    )

    st.stop()


# =============================================================================
# RESTORE RESULTS
# =============================================================================

portfolio_data = st.session_state["portfolio_data"]
classical = st.session_state["classical"]
quantum = st.session_state["quantum"]
preferences_used = st.session_state["preferences"]


# =============================================================================
# CONSTRAINT CHECKS
# =============================================================================

classical_constraints = check_constraints(
    classical["weights"],
    portfolio_data,
)

quantum_constraints = check_constraints(
    quantum["weights"],
    portfolio_data,
)


# =============================================================================
# RECOMMENDATION
# =============================================================================

recommendation, recommendation_reason = choose_recommendation(
    classical,
    quantum,
    classical_constraints,
    quantum_constraints,
)


# =============================================================================
# RECOMMENDED PORTFOLIO
# =============================================================================

st.header("Recommended Portfolio")

if recommendation == "Quantum":

    st.success(
        "Recommended portfolio: CVaR-QAOA + SLSQP"
    )

elif recommendation == "Classical":

    st.info(
        "Recommended portfolio: Classical MIQP"
    )

else:

    st.warning(
        "No feasible portfolio recommendation."
    )

st.write(recommendation_reason)


# =============================================================================
# RECOMMENDED PORTFOLIO DETAILS
# =============================================================================

if recommendation == "Quantum":

    recommended_result = quantum

else:

    recommended_result = classical


recommended_metrics = recommended_result["metrics"]

recommended_assets = recommended_result.get(
    "selected_assets",
    [],
)


left, right = st.columns([1, 2])


# -----------------------------------------------------------------------------
# LEFT — SUMMARY
# -----------------------------------------------------------------------------

with left:

    st.subheader("Selected Assets")

    if recommended_assets:

        st.write(
            ", ".join(recommended_assets)
        )

    else:

        st.write("No assets selected.")

    st.metric(
        "Expected Return",
        format_pct(
            get_metric(
                recommended_metrics,
                "Expected Return",
                "expected_return",
            )
        ),
    )

    st.metric(
        "Risk / Volatility",
        format_pct(
            get_metric(
                recommended_metrics,
                "Risk / Volatility",
                "risk",
            )
        ),
    )

    st.metric(
        "Income",
        format_pct(
            get_metric(
                recommended_metrics,
                "Income / Dividend Yield",
                "income",
            )
        ),
    )

    st.metric(
        "Transaction Cost",
        format_pct(
            get_metric(
                recommended_metrics,
                "Transaction Cost",
                "transaction_cost",
                "cost",
            )
        ),
    )

    st.metric(
        "Objective",
        format_number(
            get_metric(
                recommended_metrics,
                "Objective / Cost Function",
                "objective",
            )
        ),
    )

    if recommendation == "Quantum":

        st.metric(
            "CVaR",
            format_number(
                quantum["cvar"]
            ),
        )


# -----------------------------------------------------------------------------
# RIGHT — RECOMMENDED ALLOCATION
# -----------------------------------------------------------------------------

with right:

    st.subheader(
        "Recommended Allocation"
    )

    allocation = recommended_result[
        "allocation"
    ].copy()

    st.dataframe(
        allocation,
        use_container_width=True,
        hide_index=True,
    )


# =============================================================================
# CLASSICAL VS QUANTUM
# =============================================================================

st.divider()

st.header(
    "Classical vs Quantum Comparison"
)

comparison_table = build_comparison_table(
    classical,
    quantum,
    classical_constraints,
    quantum_constraints,
)

st.dataframe(
    comparison_table,
    use_container_width=True,
    hide_index=True,
)


# =============================================================================
# HARD CONSTRAINT COMPARISON
# =============================================================================

st.subheader(
    "Hard-Constraint Comparison"
)

constraint_table = build_constraint_table(
    classical_constraints,
    quantum_constraints,
)

st.dataframe(
    constraint_table,
    use_container_width=True,
    hide_index=True,
)

# =============================================================================
# EXPLAINABILITY
# =============================================================================

st.divider()
st.header("Portfolio Co-Pilot Explanation")

if recommendation == "Quantum":

    st.success(
        "The Co-Pilot recommends the CVaR-QAOA + SLSQP portfolio."
    )

    st.write(
        "The Quantum portfolio was selected because it satisfies the "
        "hard constraints and provides the better preference-weighted "
        "optimization outcome."
    )

elif recommendation == "Classical":

    st.info(
        "The Co-Pilot recommends the Classical MIQP portfolio."
    )

    st.write(
        "The Classical portfolio was selected because it provides the "
        "better feasible outcome under the selected investment preferences."
    )

else:

    st.warning(
        "The Co-Pilot cannot recommend either portfolio because "
        "both portfolios violate hard constraints."
    )


# -----------------------------------------------------------------------------
# Investment preference explanation
# -----------------------------------------------------------------------------

st.subheader("Investment Objective")

preference_explanation = []

if preferences_used["alpha"] > 0:
    preference_explanation.append(
        f"Growth preference = {preferences_used['alpha']}. "
        "Higher values place more emphasis on expected return."
    )

if preferences_used["beta"] > 0:
    preference_explanation.append(
        f"Income preference = {preferences_used['beta']}. "
        "Higher values place more emphasis on dividend/income yield."
    )

if preferences_used["delta"] > 0:
    preference_explanation.append(
        f"Drawdown-control preference = {preferences_used['delta']}. "
        "Higher values place more emphasis on controlling drawdown."
    )

if preferences_used["gamma"] > 0:
    preference_explanation.append(
        f"Cost-sensitivity preference = {preferences_used['gamma']}. "
        "Higher values penalize portfolio costs more strongly."
    )

if preferences_used["lambda"] > 0:
    preference_explanation.append(
        f"Risk-aversion preference = {preferences_used['lambda']}. "
        "Higher values penalize portfolio variance more strongly."
    )

for explanation in preference_explanation:
    st.write("• " + explanation)


# -----------------------------------------------------------------------------
# Constraint explanation
# -----------------------------------------------------------------------------

st.subheader("Why the Portfolio Is Feasible")

if recommendation == "Quantum":

    selected_constraints = quantum_constraints

else:

    selected_constraints = classical_constraints


if selected_constraints["feasible"]:

    st.success(
        "The recommended portfolio satisfies all hard constraints."
    )

    st.write(
        f"Selected assets: "
        f"{selected_constraints['selected_count']}"
    )

    st.write(
        f"Hard-constraint breaches: "
        f"{selected_constraints['breach_count']}"
    )

    st.write(
        f"Technology exposure: "
        f"{format_pct(selected_constraints['technology_weight'])}"
    )

else:

    st.error(
        "The selected portfolio has hard-constraint breaches."
    )


# -----------------------------------------------------------------------------
# Trade-off explanation
# -----------------------------------------------------------------------------

st.subheader("Classical vs Quantum Trade-offs")

c_metrics = classical["metrics"]
q_metrics = quantum["metrics"]

c_return = get_metric(
    c_metrics,
    "Expected Return",
    "expected_return",
)

q_return = get_metric(
    q_metrics,
    "Expected Return",
    "expected_return",
)

c_risk = get_metric(
    c_metrics,
    "Risk / Volatility",
    "risk",
)

q_risk = get_metric(
    q_metrics,
    "Risk / Volatility",
    "risk",
)

c_cost = get_metric(
    c_metrics,
    "Transaction Cost",
    "transaction_cost",
    "cost",
)

q_cost = get_metric(
    q_metrics,
    "Transaction Cost",
    "transaction_cost",
    "cost",
)

tradeoff_table = pd.DataFrame(
    {
        "Measure": [
            "Expected Return",
            "Risk / Volatility",
            "Transaction Cost",
            "Hard-Constraint Breaches",
        ],
        "Classical": [
            format_pct(c_return),
            format_pct(c_risk),
            format_pct(c_cost),
            classical_constraints["breach_count"],
        ],
        "Quantum": [
            format_pct(q_return),
            format_pct(q_risk),
            format_pct(q_cost),
            quantum_constraints["breach_count"],
        ],
    }
)

st.dataframe(
    tradeoff_table,
    use_container_width=True,
    hide_index=True,
)


# -----------------------------------------------------------------------------
# Selected asset explanation
# -----------------------------------------------------------------------------

st.subheader("Selected Assets and Allocation")

recommended_allocation = recommended_result["allocation"].copy()

st.dataframe(
    recommended_allocation,
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "The recommended allocation is produced by the optimization process "
    "subject to the portfolio constraints and the investment preferences "
    "selected on the left."
)

# =============================================================================
# FEASIBILITY STATUS
# =============================================================================

if (
    classical_constraints["feasible"]
    and quantum_constraints["feasible"]
):

    st.success(
        "Both Classical and Quantum portfolios satisfy "
        "all hard constraints."
    )

elif quantum_constraints["feasible"]:

    st.success(
        "Quantum portfolio satisfies all hard constraints."
    )

elif classical_constraints["feasible"]:

    st.info(
        "Classical portfolio satisfies all hard constraints, "
        "but the Quantum portfolio does not."
    )

else:

    st.error(
        "Neither portfolio satisfies all hard constraints."
    )


# =============================================================================
# ASSET-BY-ASSET COMPARISON
# =============================================================================

st.subheader(
    "Asset Allocation Comparison"
)

classical_weights = classical["weights"]
quantum_weights = quantum["weights"]

allocation_comparison = pd.DataFrame(
    {
        "Ticker": portfolio_data["tickers"],
        "AssetClass": portfolio_data["asset_classes"],
        "Classical Weight": classical_weights,
        "Quantum Weight": quantum_weights,
        "Difference": (
            quantum_weights
            - classical_weights
        ),
    }
)

allocation_comparison = allocation_comparison[
    (
        allocation_comparison["Classical Weight"].abs()
        > 1e-8
    )
    |
    (
        allocation_comparison["Quantum Weight"].abs()
        > 1e-8
    )
].copy()

allocation_comparison = allocation_comparison.sort_values(
    "Quantum Weight",
    ascending=False,
)

allocation_display = allocation_comparison.copy()

allocation_display["Classical Weight"] = (
    allocation_display["Classical Weight"]
    .map(format_pct)
)

allocation_display["Quantum Weight"] = (
    allocation_display["Quantum Weight"]
    .map(format_pct)
)

allocation_display["Difference"] = (
    allocation_display["Difference"]
    .map(format_pct)
)

st.dataframe(
    allocation_display,
    use_container_width=True,
    hide_index=True,
)


# =============================================================================
# QUANTUM DIAGNOSTICS
# =============================================================================

st.divider()

st.subheader(
    "Quantum Optimization Diagnostics"
)

q1, q2, q3, q4 = st.columns(4)

q1.metric(
    "CVaR Alpha",
    f"{CVAR_ALPHA:.2f}",
)

q2.metric(
    "QAOA Depth",
    str(QAOA_REPS),
)

q3.metric(
    "Shots",
    str(QAOA_SHOTS),
)

q4.metric(
    "Quantum Runtime",
    f"{quantum['runtime_seconds']:.3f} s",
)

if quantum["feasible"]:

    st.success(
        "CVaR-QAOA selected a feasible portfolio "
        "after SLSQP weight refinement."
    )

else:

    st.warning(
        "The Quantum portfolio is not feasible."
    )


# =============================================================================
# INVESTMENT PREFERENCES USED
# =============================================================================

st.divider()

st.subheader(
    "Investment Preferences Used"
)

preferences_table = pd.DataFrame(
    {
        "Goal": [
            "Growth",
            "Income",
            "Drawdown Control",
            "Cost Sensitivity",
            "Risk Aversion",
        ],
        "Value": [
            preferences_used["alpha"],
            preferences_used["beta"],
            preferences_used["delta"],
            preferences_used["gamma"],
            preferences_used["lambda"],
        ],
    }
)

st.dataframe(
    preferences_table,
    use_container_width=True,
    hide_index=True,
)


# =============================================================================
# OUTPUT FILES
# =============================================================================

st.divider()

st.subheader(
    "Generated Result Files"
)

for file_path in [
    Portfolio_Data_File,
    Classical_Result_File,
    Quantum_Result_File,
]:

    if file_path.exists():

        st.success(
            f"{file_path.name} generated"
        )

    else:

        st.warning(
            f"{file_path.name} not found"
        )
