# =============================================================================
# This script demonstrates how to do a single run with DtnSim. To run this file
# make sure that the Python working directory is the top folder where DtnSim is
# located (i.e., the folder that contains setup.py)
#
# Author: Marc Sanchez Net
# Date:   10/30/2019
# Copyright (c) 2019, California Institute of Technology ("Caltech").
# U.S. Government sponsorship acknowledged.
# =============================================================================

from bin.main import load_configuration_file, run_simulation

# Define configuration file (relative to working directory = <path_to>\dtnsim-public)
#config_file = './tests/test_1.yaml'
config_file = 'C:/Users/mnet/Documents/Projects/CDTN/openai/lunar_scenario.yaml'

# Load configuration file
config = load_configuration_file(config_file)

# Run the simulation and get the results
# env: DtnSimEnvironment after simulation ends
# res: Dictionary of pandas DataFrames, one per report requested in the configuration file
# ok:  Deprecated, do not use.
env, res, ok = run_simulation(config=config, return_env=True)