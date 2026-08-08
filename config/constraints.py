"""
constraints.py
Portfolio constraints

This file defines the constraints used for multi-asset portfolio optimization.

The constraints are defined in a dictionary format, where each key represents a 
specific constraint and its corresponding  value defines the constraint's parameters.
The constraints include budget, cardinality, asset allocation bounds, and sector exposure limits.

"""

#CONSTRAINTS

# Budget
BUDGET = 1.0

# Cardinality
MAX_ASSETS = 10

# Asset allocation bounds
MIN_WEIGHT = 0.01
MAX_WEIGHT = 0.40

# Sector exposure limits
MAX_TECHNOLOGY = 0.30
