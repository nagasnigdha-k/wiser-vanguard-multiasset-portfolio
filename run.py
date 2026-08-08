"""
run.py

Master execution pipeline for the WISER/Vanguard
multi-asset portfolio optimization project.

Execution order:

1. Generate Portfolio_Data.xlsx
2. Run classical MIQP optimizer
3. Run hybrid CVaR-QAOA optimizer
4. Compare classical and quantum results
"""

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"


def run_step(description, script):
    print("\n" + "=" * 80)
    print(description)
    print("=" * 80)

    script_path = SRC_DIR / script

    if not script_path.exists():
        raise FileNotFoundError(
            f"Script not found: {script_path}"
        )

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{script} failed with exit code "
            f"{result.returncode}"
        )


def main():

    print("\n")
    print("=" * 80)
    print("WISER / VANGUARD MULTI-ASSET PORTFOLIO")
    print("FULL OPTIMIZATION PIPELINE")
    print("=" * 80)

    # ---------------------------------------------------------
    # STEP 1: Generate portfolio data
    # ---------------------------------------------------------

    run_step(
        "STEP 1: GENERATING PORTFOLIO DATA",
        "generate_portfolio_data.py",
    )

    # ---------------------------------------------------------
    # STEP 2: Classical optimization
    # ---------------------------------------------------------

    run_step(
        "STEP 2: RUNNING CLASSICAL MIQP OPTIMIZER",
        "classical_optimizer.py",
    )

    # ---------------------------------------------------------
    # STEP 3: Quantum / hybrid optimization
    # ---------------------------------------------------------

    run_step(
        "STEP 3: RUNNING CVaR-QAOA OPTIMIZER",
        "quantum_optimizer.py",
    )

    # ---------------------------------------------------------
    # STEP 4: Compare results
    # ---------------------------------------------------------

    run_step(
        "STEP 4: COMPARING CLASSICAL VS QUANTUM RESULTS",
        "compare_results.py",
    )

    # ---------------------------------------------------------
    # COMPLETE
    # ---------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("FULL PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 80)

    print("\nGenerated files:")

    data_dir = PROJECT_ROOT / "data"

    files = [
        "Portfolio_Data.xlsx",
        "Classical_Result.xlsx",
        "Quantum_Result.xlsx",
    ]

    for filename in files:

        filepath = data_dir / filename

        if filepath.exists():
            print(
                f"  [OK] {filepath}"
            )
        else:
            print(
                f"  [MISSING] {filepath}"
            )

    print()


if __name__ == "__main__":
    main()