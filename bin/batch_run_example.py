# =============================================================================
# This script demonstrates how to do trigger multiple simulation runs at once.
# This is typically useful when you want to do a batch of simulations varying
# one parameter
#
# For this script to work, Python's working directory must be the top folder
# where DtnSim is installed (i.e., the folder that contains setup.py)
#
# The general working flow for a batch run is as follows:
#   1) Create a reference input file. This contains the simulation elements
#      you want to run, although some of its elements will be modified for
#      each specific run.
#   2) Defined which reports should be merged when all simulations are
#      completed. Example: Consider a batch run with 2 simulations. The first
#      one generates a report A stored as a pandas DataFrame df1. Similarly,
#      the second one also generates report A stored as a pandas DataFrame df2.
#      Then, if you indicate A should be merged, df1 and df2 will be merged into
#      a single DataFrame using the simulation index. This facilitates later data
#      via typical pandas commands such as ``groupby``.
#   2) Define a ``build_inputs`` function. It takes as input a dictionary
#      representing the configuration you provided in step (1). In turn, the
#      function must return a list of all the configurations you want to
#      simulate
#   3) Call ``run_simulations`` passing in the file defined in (1) as well
#      the function defined in (2)
#
# Author: Marc Sanchez Net
# Date:   10/30/2019
# Copyright (c) 2019, California Institute of Technology ("Caltech").
# U.S. Government sponsorship acknowledged.
# =============================================================================

from copy import deepcopy
from bin.main import run_simulations

# =============================================================================================
# === Global variables
# =============================================================================================

# Number of CPUs to use
Ncpu = 2

# Define configuration file (relative to working directory = <path_to>\dtnsim-public)
config_file = './tests/test_1.yaml'

# Indicate which reports should be merged upon completing all simulations.
# NOTE: test_1.yaml has only one report, DtnArrivedBundlesReport, which is identified by the
#       id ``arrived``.
to_merge = ['arrived']

# =============================================================================================
# === Build configuration files for all simulations
# =============================================================================================

def build_inputs(ref_config):
    # Initialize variables
    configs = []

    for i in range(5):
        # Make a copy of the reference configuration so that you do not
        # squash any changes
        d = deepcopy(ref_config)

        # Set the seed
        d['scenario']['seed'] = i

        # MAKE ANY OTHER DESIRED CHANGES TO d

        # Save data
        configs.append(d)

    return configs

# =============================================================================================
# === MAIN
# =============================================================================================

# NOTE: If running on Windows, multiprocessing requires running inside the __main__ if.
if __name__ == '__main__':
    run_simulations(config_file, build_inputs, sheets=to_merge, ncpu=Ncpu)