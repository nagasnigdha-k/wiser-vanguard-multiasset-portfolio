"""
settings.py
General project settings

This file contains general settings for the portfolio optimization project, 
including the date range for data retrieval and the number of trading days in a year.

"""

from pathlib import Path
from datetime import datetime, timedelta

# Project root (one level above src)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Data folder
DATA_DIR = PROJECT_ROOT / "data"

# Portfolio Data Output Excel file
Portfolio_Data_File = DATA_DIR / "Portfolio_Data.xlsx"

# Classical Result Output Excel file
Classical_Result_File = DATA_DIR / "Classical_Result.xlsx"

# Quantum Result Output Excel file
Quantum_Result_File = DATA_DIR / "Quantum_Result.xlsx"

# Date range
end_date = datetime.now()
start_date = end_date - timedelta(days=365)

# Quantum optimizer defaults
QAOA_P = 1
QAOA_TAU = 0.10
QAOA_SHOTS = 256
QAOA_FINAL_SHOTS = 2048
QAOA_MAXITER = 30
QAOA_ETA2 = 100.0
