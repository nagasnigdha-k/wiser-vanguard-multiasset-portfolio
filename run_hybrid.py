"""Run the hybrid CVaR-QAOA portfolio optimizer."""

from config.settings import (
    QAOA_P, QAOA_TAU, QAOA_SHOTS, QAOA_FINAL_SHOTS,
    QAOA_MAXITER, QAOA_ETA2,
)
from config.user_inputs import DEFAULT_USER_INPUTS
from src.data_loader import load_portfolio_data
from src.quantum_optimizer import solve_quantum, save_results


def main():
    data = load_portfolio_data()
    print(f"Assets: {data['N']}")
    print(f"Cardinality K: {__import__('config.constraints', fromlist=['MAX_ASSETS']).MAX_ASSETS}")
    print(f"QAOA depth p: {QAOA_P}")
    print(f"CVaR tau: {QAOA_TAU}")

    result = solve_quantum(
        user_preferences=DEFAULT_USER_INPUTS,
        p=QAOA_P,
        tau=QAOA_TAU,
        shots=QAOA_SHOTS,
        final_shots=QAOA_FINAL_SHOTS,
        maxiter=QAOA_MAXITER,
        eta2=QAOA_ETA2,
    )

    save_results(result, data)

    print("\n" + "=" * 72)
    print("HYBRID CVaR-QAOA RESULT")
    print("=" * 72)
    print("Bitstring       :", result.bitstring)
    print("Selected assets :", ", ".join(result.selected_assets))
    print("CVaR            :", f"{result.cvar:.6f}")
    print("Feasible        :", result.feasible)
    print("Runtime (sec)   :", f"{result.runtime_seconds:.3f}")
    print("\nAllocation:")
    for ticker, weight in zip(data["tickers"], result.weights):
        if weight > 1e-8:
            print(f"  {ticker:8s} {weight:.6f}")
    print("\nMetrics:")
    for key, value in result.metrics.items():
        print(f"  {key:22s}: {value}")


if __name__ == "__main__":
    main()
