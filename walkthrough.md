# WISER / Vanguard Multi-Asset Portfolio — Walkthrough

This walkthrough helps to understand what to run, what each stage does, and how the implementation maps to the portfolio-optimization agenda.

---

## 1. What this project demonstrates

The project is a multi-asset portfolio construction prototype with two optimization paths:

- **Classical MIQP** using Gurobi.
- **Hybrid CVaR-QAOA + SLSQP** for binary asset selection followed by continuous portfolio-weight optimization.

A Streamlit **Portfolio Co-Pilot** sits on top of both paths and explains the recommended allocation and the trade-offs between the classical and quantum approaches.

The key idea is:

```text
Investment preferences
        ↓
Portfolio objective
        ↓
Asset selection + portfolio constraints
        ↓
 ┌───────────────────────┐
 │ Classical MIQP        │
 └───────────────────────┘
        vs
 ┌───────────────────────┐
 │ QUBO → Ising → QAOA   │
 │        ↓              │
 │     SLSQP weights     │
 └───────────────────────┘
        ↓
Constraint validation
        ↓
Classical vs Quantum comparison
        ↓
Portfolio Co-Pilot recommendation
```

---

# 2. Prerequisites

Use Python 3.10+ in a virtual environment.

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

The classical path requires a working **Gurobi** installation and license.

The data-generation step requires internet access because the current implementation downloads market data from Yahoo Finance.

---

# 3. Run the complete command-line pipeline

From the repository root:

```bash
python run.py
```

`run.py` is the master execution script.

It executes four stages in order:

```text
STEP 1 → Generate portfolio data
STEP 2 → Run classical MIQP
STEP 3 → Run CVaR-QAOA
STEP 4 → Compare results
```

At the end, the following files should exist in `data/`:

```text
Portfolio_Data.xlsx
Classical_Result.xlsx
Quantum_Result.xlsx
```

---

# 4. Step 1 — Generate portfolio data

The first stage runs:

```text
src/generate_portfolio_data.py
```

### What it does

The repository contains a master universe of 20 assets in:

```text
config/assets.py
```

The data-generation script currently selects:

```text
N_ASSETS = 12
RANDOM_SEED = 42
```

It then downloads market data for the selected assets and calculates the inputs required by the optimizers.

The generated Excel file is:

```text
data/Portfolio_Data.xlsx
```

### Main data components

The workbook contains:

- asset information,
- historical prices,
- daily returns,
- covariance matrix,
- expected returns,
- volatility,
- dividend yield,
- drawdown,
- transaction cost.

### Why this stage matters

This is the bridge between raw market information and the mathematical optimization model.

The optimizer does not consume raw price data directly. It consumes the processed portfolio statistics.

---

# 5. Step 2 — Understand the mathematical portfolio model

The portfolio uses two types of decision variables.

## Continuous weight

For every asset:

```text
wᵢ ∈ [0, 1]
```

`wᵢ` is the percentage of portfolio capital allocated to asset `i`.

## Binary selection

For every asset:

```text
xᵢ ∈ {0,1}
```

`xᵢ = 1` means the asset is selected.

This allows the model to answer two different questions:

```text
Which assets should I hold?
        +
How much should I allocate to each selected asset?
```

---

# 6. Objective function

The common portfolio objective is:

```text
maximize

α μᵀw
+ β yᵀw
− λ wᵀΣw
− γ dᵀw
− δ cᵀw
```

Interpretation:

| Term | Meaning |
|---|---|
| `μᵀw` | Expected portfolio return |
| `yᵀw` | Income / dividend contribution |
| `wᵀΣw` | Portfolio variance |
| `dᵀw` | Drawdown contribution |
| `cᵀw` | Transaction-cost contribution |

The user preference parameters control the relative importance of these terms.

In the Streamlit app the user can change:

```text
Growth
Income
Drawdown Control
Cost Sensitivity
Risk Aversion
```

These map to:

```text
Growth            → α
Income            → β
Cost Sensitivity  → γ
Drawdown Control  → δ
Risk Aversion     → λ
```

---

# 7. Hard constraints

The current portfolio guardrails are defined in:

```text
config/constraints.py
```

### Budget

```text
Σ wᵢ = 1
```

All capital must be allocated.

### Cardinality

```text
Σ xᵢ = 10
```

Exactly 10 assets must be selected.

### Linking constraints

```text
0.01 xᵢ ≤ wᵢ ≤ 0.40 xᵢ
```

This creates the connection between selection and allocation:

- if `xᵢ = 0`, then `wᵢ = 0`;
- if `xᵢ = 1`, then the weight must be between 1% and 40%.

### Technology exposure

```text
Σ Technology weights ≤ 30%
```

This is a continuous portfolio exposure constraint.

---

# 8. Step 3 — Classical MIQP

The classical optimizer is:

```text
src/classical_optimizer.py
```

It creates:

```text
wᵢ = continuous variables
xᵢ = binary variables
```

and solves the mixed-integer quadratic optimization problem directly.

The model contains:

```text
Quadratic objective
        +
Budget constraint
        +
Cardinality constraint
        +
Minimum/maximum weight constraints
        +
Technology exposure constraint
```

Gurobi then searches for the best feasible portfolio.

The output is saved to:

```text
data/Classical_Result.xlsx
```

---

# 9. Step 4 — Quantum formulation

The quantum path starts from the binary asset-selection problem.

The main implementation is:

```text
src/quantum_optimizer.py
```

The workflow is:

```text
Portfolio statistics
        ↓
Binary selection model
        ↓
QUBO coefficients
        ↓
Ising Hamiltonian
        ↓
QAOA statevector simulation
        ↓
CVaR objective
        ↓
Powell parameter optimization
        ↓
Candidate bitstrings
```

---

# 10. QUBO formulation

The binary selection vector is:

```text
x = [x₁, x₂, ..., xₙ]
```

The implementation constructs a QUBO of the form:

```text
F(x) = xᵀQx + C
```

The cardinality requirement is incorporated as a penalty based on:

```text
(Σ xᵢ − K)²
```

where:

```text
K = 10
```

This encourages the quantum search to find bitstrings containing the required number of selected assets.

---

# 11. QUBO → Ising

The implementation uses the standard mapping:

```text
xᵢ = (1 − zᵢ) / 2
```

which transforms the QUBO into an Ising Hamiltonian:

```text
H_C = Σ hᵢ Zᵢ + Σ Jᵢⱼ ZᵢZⱼ + constant
```

The resulting Hamiltonian supplies the energy landscape used by QAOA.

This is the key mathematical bridge from the classical binary formulation to the quantum optimization formulation.

---

# 12. QAOA + CVaR

The current implementation uses an in-repository statevector simulator.

QAOA prepares a parameterized state using:

```text
γ = cost-Hamiltonian parameters
β = mixer parameters
```

The implementation then samples candidate bitstrings.

Instead of optimizing only the average sampled energy, the workflow evaluates a CVaR objective over the lower-cost portion of the sampled results.

The outer parameter optimizer is:

```text
Powell
```

The process is:

```text
QAOA parameters
        ↓
Sample bitstrings
        ↓
Calculate Hamiltonian energies
        ↓
Select CVaR tail
        ↓
Return CVaR value
        ↓
Powell updates γ and β
```

---

# 13. Continuous weight refinement

A quantum bitstring only tells us which assets were selected.

It does not by itself determine the final continuous allocation.

Therefore the selected assets are passed to:

```text
SLSQP
```

SLSQP optimizes their continuous weights subject to:

```text
Σ wᵢ = 1
0.01 ≤ wᵢ ≤ 0.40
Technology exposure ≤ 0.30
```

This produces the final portfolio weights.

The architecture is therefore genuinely hybrid:

```text
Quantum:
asset selection

        +

Classical:
continuous weight optimization
```

---

# 14. Hard-constraint validation

After the continuous optimization stage, the portfolio is checked again.

The final feasibility check verifies:

- budget,
- cardinality,
- minimum weight,
- maximum weight,
- Technology exposure.

The goal is:

```text
Hard-constraint breaches = 0
```

This check is important because the challenge scoring prioritizes feasible portfolios.

---

# 15. Step 5 — Compare classical vs quantum

The comparison script is:

```text
src/compare_results.py
```

It reads:

```text
data/Classical_Result.xlsx
data/Quantum_Result.xlsx
```

and compares the portfolios using the same portfolio data.

The important metrics are:

```text
Expected Return
Risk / Volatility
Income / Dividend Yield
Drawdown
Transaction Cost
Objective / Cost Function
Selected Asset Count
Technology Exposure
Hard-Constraint Breaches
```

The comparison is intended to answer:

```text
Which approach gives the better risk-adjusted result
while maintaining zero hard-constraint breaches?
```

---

# 16. Launch the Portfolio Co-Pilot

Run:

```bash
streamlit run portfolio_copilot.py
```

The application exposes five investment preference controls:

```text
Growth
Income
Drawdown Control
Cost Sensitivity
Risk Aversion
```

There is also an option to regenerate the portfolio dataset.

Click:

```text
Start Optimization
```

The app runs:

```text
1. Data generation/loading
2. Classical MIQP
3. CVaR-QAOA + SLSQP
4. Result saving
```

---

# 17. What the Co-Pilot shows

After optimization, the application presents:

### Recommended portfolio

- recommended method,
- selected assets,
- expected return,
- risk,
- income,
- transaction cost,
- objective,
- CVaR when the quantum portfolio is recommended.

### Recommended allocation

A table showing:

```text
Ticker
Asset Class
Group
Weight
```

### Classical vs Quantum comparison

A side-by-side comparison of the two solutions.

### Hard-constraint comparison

The application explicitly shows:

```text
Feasible
Hard-constraint breaches
Selected assets
Technology exposure
```

### Explanation

The Co-Pilot explains why one solution was selected and describes the trade-offs.

---

# 18. Recommendation logic

The application follows this priority:

```text
Priority 1: Zero hard-constraint breaches
Priority 2: Higher preference-weighted objective
Priority 3: Lower risk
Priority 4: Higher expected return
Priority 5: Lower transaction cost
```

This is important for the challenge objective.

A solution with a better numerical objective but a hard-constraint breach should not automatically win.

---

# 19. How this maps to the project agenda

## 1. Mathematical formulation

Implemented through:

```text
wᵢ continuous
xᵢ binary
linear constraints
quadratic risk objective
```

Primary files:

```text
config/constraints.py
src/objective_functions.py
src/classical_optimizer.py
```

## 2. Quantum-compatible formulation

Implemented through:

```text
binary formulation
→ QUBO
→ Ising Hamiltonian
→ QAOA
```

Primary file:

```text
src/quantum_optimizer.py
```

## 3. Portfolio data

Implemented through:

```text
src/generate_portfolio_data.py
src/data_loader.py
```

Output:

```text
data/Portfolio_Data.xlsx
```

## 4. Classical baseline + constraints

Implemented in:

```text
src/classical_optimizer.py
```

## 5. Tunable investment goals

Implemented in:

```text
portfolio_copilot.py
config/user_inputs.py
```

## 6. Comparison metrics

Implemented in:

```text
src/compare_results.py
portfolio_copilot.py
```

## 7. Classical validation

The classical MIQP provides the benchmark and the final portfolio checks are performed explicitly.

## 8. Presentation/demo

The recommended demo sequence is:

```text
python run.py
        ↓
show generated results
        ↓
streamlit run portfolio_copilot.py
        ↓
change investment preferences
        ↓
show recommendation
        ↓
show comparison
        ↓
show zero-breach validation
```

## 9. Portfolio Co-Pilot

Implemented in:

```text
portfolio_copilot.py
```

## 10. Scoring objective

The implementation explicitly prioritizes:

```text
feasibility first
then preference-weighted portfolio quality
```

The target outcome is:

```text
Best risk-adjusted outcome
+
Zero hard-constraint breaches
```

---

# 20. Important repository notes

### Current data source

The current implementation downloads market data from Yahoo Finance.

It is therefore not a purely synthetic dataset.

If the challenge submission requires synthetic/anonymized data, replace the data-generation logic while keeping the generated Excel schema unchanged.

### Current quantum implementation

The current QAOA path is a dependency-light statevector implementation.

It is limited to:

```text
N ≤ 22
```

because the statevector grows exponentially with the number of assets.

### Qiskit

Qiskit dependencies are retained for the project's intended quantum-computing direction, but the current `quantum_optimizer.py` executes its own statevector simulation rather than a Qiskit backend.

### Gurobi

The classical optimizer requires Gurobi and a valid license.

---

# 21. What each folder means

```text
config/
    Problem configuration and user/default inputs.

src/
    Core optimization and data-processing implementation.

data/
    Input dataset and generated optimizer results.

docs/
    Technical quantum-method documentation.

portfolio_copilot.py
    Interactive demonstration layer.

run.py
    End-to-end command-line runner.
```

---

