from argparse import ArgumentParser, HelpFormatter
import itertools
import sys
from pathlib import Path

# ============================================================================================================
# === DTN ARGUMENT PARSER CLASSES
# ============================================================================================================

class DtnArgumentParser(ArgumentParser):
    ''' Subclass of Python's native ArgumentParser that incorporates a function to display warning messages related
        to the arguments.
    '''

    def __init__(self, *args, **kwargs):
        ''' Constructor simply calls ArgumentParser constructor '''
        super().__init__(*args, **kwargs)

    def warning(self, message):
        ''' Display a warning message related to one of the arguments. The format is consistent with that of errors

            :param str message: Warning message to display
        '''
        print('{}: WARNING: {}\n'.format(self.prog, message))

    def error(self, message):
        print('{}: ERROR: {}\n'.format(self.prog, message))
        self.print_help()
        sys.exit(-1)

# ============================================================================================================
# === DTN ARGUMENT PARSE FUNCTIONS
# ============================================================================================================
        
def get_argument_parser():
    ''' Parse the command-line arguments for this program

        :return ArchNetArgumentParser: The argument parser
    '''
    formatter = lambda prog: HelpFormatter(prog, max_help_position=50, width=200)
    parser    = DtnArgumentParser(prog='Dtn Simulator', formatter_class=formatter, description='DTN Network Simulator')

    # Add required arguments for running in config file mode
    parser.add_argument('-cf', '--configfile', help='configuration file path',
                        type=str, default=None, nargs='?')

    # Add optional arguments
    parser.add_argument('-v', '--validate', help='run unit tests',
                        action='store_true')

    return parser

def dict_to_args_list(args):
    argnames, argvals = zip(*args.items())
    argnames = ['--' + name for name in argnames]
    return itertools.chain.from_iterable(zip(argnames, argvals))

def process_arguments(args=None):
    ''' Process the arguments of the application and run ArchNet in batch or GUI mode depending on what is specified

        :param None or dict:
    '''
    # Get argument parser
    parser = get_argument_parser()
    
    # If no arguments provided, use argument parser
    if not args:
        args = parser.parse_args()
    elif isinstance(args, dict):
        args = parser.parse_args(dict_to_args_list(args))
    elif args != None:
        raise RuntimeError('process_arguments: args can only be None or a dictionary')

    if not args.configfile: return args

    # Check the validity of the configuration file
    configfile = Path(args.configfile)
    if not configfile.exists():
        raise FileExistsError(f'Configuration file {configfile} does not exist')
    if configfile.suffix not in ['.yaml', '.yml']:
        raise ValueError(f'The configuration file {configfile} is not a YAML file')

    return args
