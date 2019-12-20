from .DtnAbstractParser import DtnAbstractParser
from pathlib import Path
from pydantic import validator, PositiveFloat

class DtnGlobalsParser(DtnAbstractParser):
    """ Parser for tag ``globals`` in YAML configuration file """
    # Name of this simulation
    id: str = 'Simulation'

    # Config file
    config_file: str = ''

    # Directory where input files are located
    indir: str

    # Directory where output files are located
    outdir: str

    # File for logging
    logfile: str = 'Log.log'

    # If True, the file is logged
    log: bool = False

    # If True, queues are monitored for incoming/outgoing elements
    monitor: bool = True

    # If True, all the results from the monitors will be exported
    export_monitor: bool = False

    # If True, all validation tests are run
    run_tests: bool = False

    # If True, the simulation progress is tracked
    track: bool = False

    # Delta time in [seconds] between every tracking printout
    track_dt: PositiveFloat = 1

    @validator('indir')
    def validate_indir(cls, indir):
        # Create a path object
        path = Path(indir).absolute()

        # If this path does not exist, raise error
        if not path.exists():
            raise ValueError(f'Input directory {path} does not exist.')

        return path

    @validator('outdir')
    def validate_outdir(cls, outdir):
        # Create a path object
        path = Path(outdir).absolute()

        # If this path does not exist, raise error
        if not path.exists():
            raise ValueError(f'Output directory {path} does not exist.')

        return path
