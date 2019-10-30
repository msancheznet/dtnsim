from .DtnAbstractParser import DtnAbstractParser
from pydantic import validator

class DtnConfigFileParser(DtnAbstractParser):
    """ Parser for the entire YAML configuration file. It is applied
        after individual configurations and checks the consistency of
        the file as a whole
    """
    # Dictionary with global configuration parameters
    # See also ``DtnGlobalsParser``
    globals : dict

    # Dictionary with scenario parameters
    # See also ``DtnScenarioParser``
    scenario : dict

    # Dictionary with network configuration parameters
    network : dict