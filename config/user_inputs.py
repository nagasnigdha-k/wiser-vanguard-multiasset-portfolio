"""
user_inputs.py

This file defines the user inputs for multi-asset portfolio optimization.

User inputs are defined in a dictionary format, where each key represents a specific input and its corresponding value defines the input's parameters.
User inputs include growth priority, income priority, risk priority, cost priority, and drawdown priority.

Note: If co-pilot is used, the user inputs are taken from json files in the data folder. 
      If co-pilot is not used, the user inputs are taken from the USER_INPUTS dictionary defined in this file.

"""


DEFAULT_USER_INPUTS = {

    "alpha": 70, #growth_priority

    "beta": 20, #income_priority

    "gamma": 30, #cost_priority

    "delta": 40,  #drawdown_priority

    "lambda": 5 #risk_priority 

}