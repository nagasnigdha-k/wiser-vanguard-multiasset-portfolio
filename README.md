# wiser-vanguard-multiasset-portfolio
WISER Vanguard 2026 challenge repository for multi-asset portfolio construction using classical, quantum, and hybrid optimization techniques with benchmarking and financial analytics.


Materials covered-
- 'config/assets.py' - This file defines the assets used for multi-asset portfolio optimization.
- 'config/constraints.py' - This file defines the constraints used for multi-asset portfolio optimization.
- 'config/init.py' - This file initializes the configuration package for the multi-asset portfolio optimization project.
- 'config/settings.py' - This file contains general settings for the portfolio optimization project, including the date range for data retrieval, the number of trading days in a year, 
the risk-free rate, the initial portfolio value, transaction costs, the output file path, and a random seed for reproducibility.
- 'config/user_inputs.py' - This file defines the user inputs for multi-asset portfolio optimization.



'src/generate_portfolio_data.py' - This file downloads historical market data from Yahoo Finance, calculates portfolio statistics, and stores everything in 'data/Portfolio_Data.xlsx'.


# wiser-vanguard-multiasset-portfolio

## Multi-Asset Portfolio Optimization using Classical, Quantum, and Hybrid CVaR-QAOA

This repository contains the implementation developed for the **WISER Vanguard 2026 Challenge**, focusing on **multi-asset portfolio optimization** using classical optimization, quantum optimization (QAOA), and a proposed **Hybrid CVaR-QAOA** framework.

The project combines traditional financial portfolio construction techniques with quantum optimization to investigate how hybrid quantum-classical algorithms can improve combinatorial asset selection while maintaining practical portfolio optimization workflows.

---

# Project Objectives

The project aims to:

- Retrieve historical financial market data
- Compute portfolio statistics from historical prices
- Formulate the portfolio selection problem as a binary optimization problem
- Construct a Quadratic Unconstrained Binary Optimization (QUBO) model
- Convert the QUBO into an Ising Hamiltonian
- Solve the asset selection problem using QAOA
- Optimize continuous portfolio weights using classical optimization
- Benchmark classical and quantum optimization approaches
- Evaluate portfolio performance using financial metrics

---

# Repository Structure

```
wiser-vanguard-multiasset-portfolio/
│
├── config/
│   ├── assets.py
│   ├── constraints.py
│   ├── settings.py
│   ├── user_inputs.py
│   └── __init__.py
│
├── src/
│   ├── classical_optimizer.py
│   ├── compare_results.py
│   ├── data_loader.py
│   ├── generate_portfolio_data.py
│   ├── objective_functions.py 
│   ├── quantum_optimizer.py
│
├── data/
│   └── Classical_Result_Filea.xlsx (Generated:src/classical_optimizer.py)
│   └── Portfolio_Data.xlsx         (Generated:src/generate_portfolio_data.py)
│   └── Quantum_Result_File.xlsx    (Generated:src/quantum_optimizer.py)
│
│
├── requirements.txt
└── README.md
```

---

# Configuration Files

## config/assets.py

Defines the investment universe used throughout the project.

This file contains:

- Asset tickers
- Asset classes
- Portfolio universe
- Asset metadata

---

## config/constraints.py

Defines all portfolio optimization constraints.

Examples include:

- Budget constraints
- Position limits
- Cardinality constraints
- Asset allocation constraints
- User-defined portfolio restrictions

---

## config/settings.py

Contains the general project settings, including:

- Historical data date range
- Number of trading days per year
- Risk-free rate
- Initial portfolio value
- Transaction costs
- Output directory
- Random seed for reproducibility

---

## config/user_inputs.py

Contains configurable user inputs used throughout the optimization workflow.

Typical parameters include:

- Number of assets
- Target return
- Risk aversion coefficient
- Optimization settings
- Quantum experiment parameters

---

## config/__init__.py

Initializes the configuration package and enables importing configuration modules across the project.

---

# Source Files

## src/generate_portfolio_data.py

This module downloads historical market data from Yahoo Finance and generates the dataset used throughout the optimization pipeline.

Main tasks include:

- Download historical asset prices
- Calculate daily returns
- Compute expected returns
- Estimate covariance matrix
- Calculate annualized volatility
- Generate portfolio statistics
- Export the processed data to:

```
data/Portfolio_Data.xlsx
```

This Excel file serves as the primary input for the optimization pipeline.

---

# Portfolio Optimization Workflow

```
Historical Market Data
          │
          ▼
Portfolio Statistics
(Expected Returns, Covariance, Risk)
          │
          ▼
Binary Portfolio Formulation
          │
          ▼
QUBO Construction
          │
          ▼
Ising Hamiltonian
          │
          ▼
QAOA Optimization
          │
          ▼
Selected Assets
          │
          ▼
Continuous Portfolio Weight Optimization
          │
          ▼
Final Optimized Portfolio
```

---

# Proposed Hybrid CVaR-QAOA Framework

This repository proposes a **Hybrid CVaR-QAOA** optimization framework for portfolio optimization.

Unlike conventional QAOA implementations that incorporate all constraints directly into the Hamiltonian, this approach separates the unconstrained quantum optimization from the inequality constraint handling.

The workflow is as follows:

1. Construct the QUBO using only the unconstrained portfolio objective.
2. Convert the QUBO into an Ising Hamiltonian.
3. Build the QAOA cost Hamiltonian.
4. Execute the QAOA circuit.
5. Measure candidate bit strings.
6. Compute the Hamiltonian energy for each measured bit string.
7. Evaluate inequality constraint penalties classically.
8. Compute the Hybrid objective

```
F(x) = E_H(x) + ρ P_ineq(x)
```

where:

- `E_H(x)` is the Hamiltonian energy.
- `P_ineq(x)` is the classical inequality penalty.
- `ρ` is the configurable penalty coefficient.

9. Compute the CVaR using the Hybrid objective values.
10. Return the Hybrid CVaR to the classical optimizer.
11. Update only the QAOA parameters `(γ, β)`.
12. Execute the optimized circuit to obtain candidate portfolios.
13. Perform continuous portfolio weight optimization on the selected assets.

In this framework:

- The quantum evolution depends only on the unconstrained Hamiltonian.
- Inequality constraints influence only the classical optimization process.
- No slack variables are introduced.
- The Hamiltonian construction remains unchanged.

---

# Technologies Used

- Python
- NumPy
- Pandas
- SciPy
- yfinance
- Qiskit
- Matplotlib
- OpenPyXL

---

# Output

The project generates:

- Historical market datasets
- Portfolio statistics
- Candidate asset selections
- Optimized portfolio weights
- Portfolio return and risk metrics
- Performance comparison results
- Visualization plots

---

# Future Enhancements

Planned extensions include:

- Hybrid CVaR-QAOA implementation
- Additional quantum optimizers
- Hardware execution support
- Advanced financial benchmarking
- Constraint sensitivity analysis
- Comparative studies with classical optimization algorithms

---

# License

This project was developed as part of the **WISER Vanguard 2026 Challenge** for research and educational purposes.