#========================================================================
#=== SET THE PYTHON WORKING DIRECTORY TO THE SIMULATOR
#========================================================================

__version__ = 'R2019'
__release__ = 'R2019b'

from concurrent.futures import ProcessPoolExecutor
import gc
import os
from pathlib import Path
import pandas as pd
import traceback
import warnings

from simulator.utils.basic_utils import profileit, hdf5_store
from simulator.environments.DtnSimEnvironment import DtnSimEnviornment
from simulator.utils.DtnArgumentParser import get_argument_parser, process_arguments
from simulator.utils.DtnConfigParser import load_configuration_file, parse_configuration_dict
from simulator.utils.DtnIO import export_dtn_results
from simulator.utils.time_utils import sec2hms

#========================================================================
#=== MAIN FUNCTION TO SIMULATE
#========================================================================

def run_simulation(config=None, profile=False, return_env=False):
    """ **Main function to trigger a simulation**.

        :param dict config: Configuration structure from a YAML file. Use ``pyyaml`` to
                            parse a configuration file.
        :param bool parallel: If False, the function returns 1) the simulation
                              environment, 2) the results, 3) True/False if errors
                              during the simulation validation process
                              If True, then it only returns True or False (3).
        :param bool profile: If True, the simulation will be profiled. This is incompatible
                             with parallel=True.

        .. Tip:: For parallel execution, the environment and results are not returned
                 because they cannot be pickled. Therefore, the inter-process communication
                 would fail.
        .. Tip:: If validate is true, then parallel and profile have no effect
    """
    # Check inputs consistency
    if profile and return_env:
        raise ValueError("Parallel and profile cannot be both True")

    # If the configuration is provided, run the simulation
    if not config:
        # Otherwise, you need to use argument parser
        args = process_arguments()

        # Load configuration file
        config = load_configuration_file(args.configfile)

    # Run the simulation
    return _run_simulation(config, profile, return_env)

def _run_simulation(config, profile, return_env):
    """ Do not call directly. Use ``run_simulation`` """
    # Ensure the configuration dictionary is ok
    config = parse_configuration_dict(config)

    # Create a simulation environment. From now on, ``config`` will be
    # a global variable available to everyone
    env = DtnSimEnviornment(config)

    # Initialize environment, create nodes/connections, start generators
    env.initialize()

    # Run simulation
    if profile:
        profileit(env.run)
    else:
        env.run()

    # Validate simulation
    ok = env.validate_simulation()

    # Create simulation outputs
    res = env.finalize_simulation()

    # Export the simulation results
    export_dtn_results(config, env)

    # Print the total simulation time
    print(env.end_msg.format(os.getpid(), env.sim_id, sec2hms(env.now)))

    # Delete environment to reset all static variables
    if not return_env:
        env.reset()
        del env
        gc.collect()

    # Return results
    return (env, res, ok) if return_env else ok

#========================================================================
#=== MAIN FUNCTIONS TO DO A BATCH ANALYSIS
#========================================================================

def _run_simulations(configs, ncpu=1):
    """ Run all simulations. Do not call directly.

        :param configs: List/tuple of dictionaries
    """
    # If only one CPU, run in serial. Signal parallel execution to ensure
    # sim environment gets deleted between simulations and static variables
    # are not polluting your results
    if ncpu == 1:
        return [run_simulation(config=c) for c in configs]

    # Run in parallel
    with ProcessPoolExecutor(max_workers=ncpu) as p:
        futures = [p.submit(run_simulation, config=c) for c in configs]
        results = [f.result() for f in futures]

    return results

def run_simulations(input_file, build_inputs, ncpu=1, sheets=None, **kwargs):
    """ Run a batch of simulations.

        :param input_file:   Initial config file path (as str or Path object)
        :param build_inputs: Function to build the inputs. It will be called
                             internally as ``configs = build_inputs(d, **kwargs)``
                             where d is the dict obtained from ``load_configuration_file``
                             (i.e. load the YAML into dict and apply parsers to validate it).
                             ``build_inputs`` **must** return a list/tuple of config dictionaries
        :param ncpu:   Number of CPUs to use. Default is 1 (serial execution)
        :param sheets: See ``sheets`` parameter in ``merge_results``
        :param **kwargs: Passed to ``build_inputs``
    """
    # Load basic configuration file
    d = load_configuration_file(input_file)

    # Build inputs
    configs = build_inputs(d, **kwargs)

    # Trigger computations
    _run_simulations(configs, ncpu=ncpu)

    # Get output directory
    outdir  = Path(d['globals']['outdir'])
    outfile = outdir/Path('merged_' + d['globals']['outfile'])
    ext     = outfile.suffix

    # Merge all results
    merge_results(outfile, outdir, ext=ext, sheets=sheets)

def merge_results(outfile, resdir, ext='.h5', sheets=None):
    """ Merge a set of simulation results into a single file containing all of them. The resulting
        file will be stored as an HDF5 file.

        :param outfile: File path (str or Path object) where the single file will be located
        :param resdir:  Directory where the results to merge are located
        :param ext:     Extension of the files in the ``resdir``. Options are '.h5' (default)
                        or '.xlsx'
        :param sheets:  List with the names of the tables to export. Defaults to ['sent', 'arrived'].
                        Valid names can be found in the ``DtnAbstractReport`` and its subclasses.
    """

    # Initialize variables
    outfile = Path(outfile)
    outfile = f'{outfile.parent/outfile.stem}.h5'

    # Get files to merge
    files = list(resdir.glob(f'./*{ext}'))

    # Select the function to read data
    if ext == '.xlsx':
        read_fun = lambda f, s: pd.read_excel(f, sheet_name=s)
    elif ext == '.h5':
        read_fun = lambda f, s: pd.read_hdf(f, key=s)
    else:
        print(f'Could not merge files. Extension {ext} is not valid')
        return

    # Get the default sheets to process
    if sheets is None:
        sheets = ['sent', 'arrived']

    # Create HDF5 store
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        with hdf5_store(outfile, mode='w') as store:
            for sheet in sheets:
                print(f'[Merge Results] Processing Report "{sheet}"')
                try:
                    store[sheet] = pd.concat({f.stem: read_fun(f, sheet).reset_index()
                                            for f in files}, names=['file'])
                except:
                    traceback.print_exc()

#========================================================================
#=== CLI HELPER FUNCTIONS
#========================================================================

def list_simulation_arguments():
    # Print parser the options
    get_argument_parser().print_help()

#========================================================================
#=== RUN SIMULATION USING COMMAND LINE ARGUMENTS
#========================================================================

if __name__ == '__main__':
    run_simulation(profile=False)