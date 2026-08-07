# Hybrid CVaR-QAOA implementation

This repository now contains a dependency-light statevector implementation of the submitted hybrid formulation.

## Mathematical mapping

The implementation constructs

- `q_i` from the linear coefficient equation
- `q_ij` from the quadratic coefficient equation
- the symmetric QUBO matrix `Q`
- Ising coefficients `h_i`, `J_ij`
- `H_C = sum_i h_i Z_i + sum_{i<j} J_ij Z_i Z_j`

The binary equality/cardinality constraint is included through the `eta2` penalty in the QUBO/Hamiltonian.

Inequality constraints are not inserted into the Hamiltonian. The current repository's technology limit is a continuous-weight constraint, so it is enforced after a sampled bitstring is converted into continuous portfolio weights. No surrogate inequality penalty is invented where the mathematical specification does not provide one.

## QAOA and CVaR

The statevector simulator prepares

`|psi(gamma,beta)> = product_l exp(-i beta_l H_M) exp(-i gamma_l H_C) |+>^N`

with `H_M = sum_i X_i`.

Powell minimizes the sampled CVaR objective. For each set of parameters, the circuit is sampled, Hamiltonian energies are computed, sorted, and the mean of the lowest `ceil(tau*M)` values is returned to Powell.

## Continuous stage

For candidate bitstrings with exactly `K` selected assets, SLSQP solves the continuous weight problem with:

- budget = 1
- selected weights between `MIN_WEIGHT` and `MAX_WEIGHT`
- technology exposure <= `MAX_TECHNOLOGY` when group information is available

The final feasibility check requires zero hard-constraint breaches.

## Run

```bash
python run_hybrid.py
```

or:

```bash
python run.py.py
```

Default quantum settings are in `config/settings.py`:

- `QAOA_P = 1`
- `QAOA_TAU = 0.10`
- `QAOA_SHOTS = 256`
- `QAOA_FINAL_SHOTS = 2048`
- `QAOA_MAXITER = 30`
- `QAOA_ETA2 = 100.0`

For a quick local test, reduce shots and iterations, for example by calling `solve_quantum(p=1, shots=64, final_shots=512, maxiter=2)`.

## Important data-order correction

`data_loader.py` now reorders the covariance matrix to exactly match the `Asset_Data` ticker order. The original data-generation code sorts `Asset_Data` by asset class while the covariance sheet retains its own ticker order; aligning them is necessary before constructing the Hamiltonian.
