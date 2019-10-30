"""
# Batch simulation for the Networked Constellations R&TD
#
# Author: Marc Sanchez Net
# Date:   04/05/2019
# Copyright 2019, Jet Propulsion Laboratory
"""

# Fix path to find movement_builder functions
import sys
sys.path.append('C:\\Users\\mnet\\Documents\\Networked_Constellations')

from bin.main import run_simulations, merge_results
from movement_builder import create_scn_motion, compute_bw, create_contact_plan

from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from math_utils import combvec
from pathlib import Path
import yaml

# =============================================================================================
# === Global variables
# =============================================================================================

# Number of CPUs to use
Ncpu = 4

# Define global inputs
inpath      = Path('C:\\Users\\mnet\\Documents\\Repositories\\DtnSim\\inputs\\networked_constellations')
outpath     = Path('C:\\Users\\mnet\\Documents\\Repositories\\DtnSim\\results\\networked_constellations')
input_file  = inpath/'10_node_config.yaml'

# Define options
routers = ['cgr_router', 'ecgr_router', 'nwc_router1', 'nwc_router2']
Nobs    = list(range(10))

# Define input file names
cp_fname = '10_node_cave_contact_plan_{}.xlsx'
dr_fname = '10_node_cave_datarate_profile_{}.h5'

# =============================================================================================
# === Build inputs for this study
# =============================================================================================

def build_motion(i):
    # Create the random movement and comm mode
    pos = create_scn_motion(seed=i)
    bw  = compute_bw(pos)*1e20
    cp  = create_contact_plan(bw)

    # Store in inputs location
    cp.to_excel(inpath / cp_fname.format(i))
    bw.to_hdf(inpath / dr_fname.format(i), key='data_rate')

def build_inputs(ref_config):
    # Initialize variables
    configs = []

    # Create motion and data rate profiles
    with ProcessPoolExecutor(max_workers=Ncpu) as p:
        p.map(build_motion, Nobs)

    for i, rt in combvec(Nobs, routers):
        # Avoid numpy types
        i, rt = int(i), str(rt)

        # Make a copy of the reference configuration
        d = deepcopy(ref_config)

        # Change the id of the simulation
        d['globals']['id'] = f'{rt}_{i}'

        # Change name of output file
        outfile = Path(d['globals']['outfile']).stem
        d['globals']['outfile'] = f'{outfile}_{rt}_{i}.h5'

        # Set the seed
        d['scenario']['seed'] = i

        # Change the name of the input files
        d['planned_mobility']['contacts'] = cp_fname.format(i)
        d['variable_radio']['datarate_file'] = dr_fname.format(i)

        # Modify router being used
        d['base_station']['router'] = rt
        d['robot']['router'] = rt
        d['robot2']['router'] = rt

        # Save YAML file
        with (inpath/f'{input_file.stem}_{rt}_{i}.yaml').open('w') as f:
            yaml.dump(d, f)

        # Save data
        configs.append(d)

    return configs

# =============================================================================================
# === Main
# =============================================================================================

if __name__ == '__main__':
    data = ['arrived', 'sent', 'dropped', 'battery_left', 'routing_calls', 'death_time',
            'in_limbo', 'in_radio', 'stored', 'lost', 'in_outduct', 'node_in_queue']
    run_simulations(input_file, build_inputs, sheets=data, ncpu=Ncpu)
    #merge_results(outpath/'merged_all_results.h5', outpath, ext='.h5', sheets=data)


