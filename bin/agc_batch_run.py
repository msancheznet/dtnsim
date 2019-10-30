from copy import deepcopy
from pathlib import Path
import sys

# Fix path
if './bin' not in sys.path:
    sys.path.append('./bin')

import numpy as np

from bin.main import run_simulations, merge_results

# =============================================================================================
# === Global variables
# =============================================================================================

# Number of CPUs to use
Ncpu = 5

# Define global inputs
path        = Path('C:\\Users\\mnet\\Documents\\Repositories\\DtnSim\\inputs\\agile_constellations\\Jul 2019\\3planes_8sat')
input_file  = path/'constellation_config.yaml'

# =============================================================================================
# === Build inputs for this study
# =============================================================================================

def build_inputs_old(ref_config):
    # Initialize variables
    configs = []

    # List the traffic cases
    for i, traffic_dir in enumerate(path.glob('./**/example*'), start=1):
        # Make a copy of the reference configuration
        d = deepcopy(ref_config)
        
        # Replace folder
        d['globals']['id'] = f'Simulation {i}'
        parts = d['packet_generator']['file'].split('/')
        parts[1] = traffic_dir.name
        d['packet_generator']['file'] = '/'.join(parts)
        d['globals']['outfile'] = traffic_dir.name + '_' + d['globals']['outfile']
        
        # Store config
        configs.append(d)
        
    return configs

def build_inputs(ref_config):
    # Initialize variables
    configs = []

    # Modify data rate
    for i, dr in enumerate(np.logspace(3,9,50)[::-1], start=1):
        # Make a copy of the reference configuration
        d = deepcopy(ref_config)

        # Update properties
        d['globals']['id'] = f'Simulation {i}'
        d['basic_radio']['rate'] = dr
        d['globals']['outfile'] = f'{i} - ' + d['globals']['outfile']

        # Store config
        configs.append(d)

    return configs

if __name__ == '__main__':
    data = ['arrived', 'sent', 'dropped']
    run_simulations(input_file, build_inputs, sheets=data, ncpu=Ncpu)
    # merge_results(outpath/'merged_all_results.h5', outpath, ext='.h5', sheets=data)