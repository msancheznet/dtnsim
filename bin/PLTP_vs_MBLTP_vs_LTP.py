from basic_utils import hdf5_store
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import glob
from bin.main import simulate_dtn_network
import numpy as np
import os
import pandas as pd
from pathlib import Path
import shutil
from simulator import parse_configuration_file

# Define global inputs
path        = 'C:\\Users\\mnet\\Documents\\DTN\\Outduct Selection Research\\DtnSim Experiments'
input_file  = str(Path(path)/'Parallel_LTP.yaml')

# Define options
Niid = 30                                # Number of IID observations to run
BERs = list(np.logspace(-10, -4, 25))    # BER from 1e-10 to 1e-4 approx

def prepare_folders(d, reset=True):
    # Get the directory
    outdir = Path(d['globals']['outdir'])/'runs'
    if not reset: return outdir
    
    # Reset the folder
    if outdir.exists(): shutil.rmtree(outdir)
    os.makedirs(str(outdir))

    return outdir

def build_inputs(d, outdir):
    # Build options
    pd.DataFrame(BERs, columns=('BER',)).to_csv(outdir/'options.csv')

    # Create the configuration files
    configs = []
    for i, BER in enumerate(BERs):
        for j in range(Niid):
            c = deepcopy(d)
            c['globals']['id']      = f'Simulation {i}_{j}'
            c['globals']['outfile'] = f'{Path(d["globals"]["outfile"]).stem}_{i}_{j}.h5'
            c['globals']['outdir']  = str(outdir)
            c['x_radio']['BER']     = BER

            # For basic LTP, this is not defined
            try: c['ka_radio']['BER']    = 100*BER
            except: pass
            configs.append(c)

    return configs

def run_simulations(configs, ncpu=5):
    with ProcessPoolExecutor(max_workers=ncpu) as p:
        futures = [p.submit(simulate_dtn_network, config=c, parallel=True)
                   for c in configs]
        results = [f.result() for f in futures]

    return results

def merge_results(d, outdir):
    """ Create a unified data store for all scenarios and IID observations """
    # Initialize variables
    outfile = Path(d['globals']['outdir'])/d['globals']['outfile']

    # Create HDF5 store
    with hdf5_store(outfile, mode='w') as store:
        # load options
        opts = pd.read_csv(outdir/'options.csv')
        store['/options'] = opts

        # Get names of data frames to export
        with hdf5_store(glob.glob(str(outdir/'*_0_0.h5'))[0]) as s: names = s.keys()

        # Read all data
        data = {name: pd.concat({i: pd.concat({j: pd.read_hdf(file, name) 
                                for j, file in enumerate(glob.glob(str(outdir/f'*_{i}_*.h5')))})
                                for i in range(opts.shape[0])}) for name in names}

        # Correct index and store all data
        for name in names:
            try: data[name].index.set_names(('opt', 'sim'), level=(0, 1), inplace=True)
            except: pass
            store[name] = data[name]

    return data

def run_all():
    # Load basic configuration file
    d = parse_configuration_file(input_file)

    # Prepare folder structure
    outdir = prepare_folders(d, reset=True)

    # Build inputs
    configs = build_inputs(d, outdir)

    # Trigger computations
    run_simulations(configs, ncpu=4)

    # Merge all results
    return merge_results(d, outdir)

def run_merge():
    # Load basic configuration file
    d = parse_configuration_file(input_file)

    # Prepare folder structure
    outdir = prepare_folders(d, reset=False)

    # Merge all results
    return merge_results(d, outdir)

if __name__ == '__main__':
    # Run all
    data = run_all()

    # Merge results
    #data = run_merge()